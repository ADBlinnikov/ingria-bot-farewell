import asyncio
import json
import logging
import os
from ast import expr_context
from random import randint
from time import sleep
from typing import Callable, List

import boto3
import telebot
from botocore.errorfactory import ClientError
from dotenv import load_dotenv
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import ReplyKeyboardMarkup
from yaml import SafeLoader, load

# Logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)


def log_user_answer(point: str, answer: str) -> None:
    logger.info(f"Point: {point} Answer: {answer}")


# Environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# S3 client
session = boto3.session.Session()
s3 = session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
)

# Dataclasses
class UserInfo:
    @staticmethod
    def to_dict(data):
        return {
            "id": getattr(data, "id", None),
            "is_bot": getattr(data, "is_bot", None),
            "first_name": getattr(data, "first_name", None),
            "last_name": getattr(data, "last_name", None),
            "username": getattr(data, "username", None),
            "language_code": getattr(data, "language_code", None),
            "is_premium": getattr(data, "is_premium", None),
            "added_to_attachment_menu": getattr(data, "added_to_attachment_menu", None),
        }


def dump_s3(obj, f, rewrite=False):
    """
    Return None if file wasn't created
    """
    try:
        # Check if file exists
        s3.head_object(Bucket=BUCKET_NAME, Key=f)
        if rewrite:
            return s3.put_object(Bucket=BUCKET_NAME, Key=f, Body=json.dumps(obj, ensure_ascii=False))
        else:
            return
    except ClientError:
        # File not found - create new file
        return s3.put_object(Bucket=BUCKET_NAME, Key=f, Body=json.dumps(obj, ensure_ascii=False))


# Bot instance
class MyExceptionHandler(ExceptionHandler):
    def handle(self, exception):
        logger.error(exception)


bot = AsyncTeleBot(TOKEN, state_storage=StateMemoryStorage(), exception_handler=MyExceptionHandler())

markup = ReplyKeyboardMarkup(resize_keyboard=True)
markup.add("Идем дальше")

CONGRATS = ["Это правильный ответ", "Верно", "Правильно"]


async def send_messages(chat_id: str, messages: List[str], after_answer: bool = False):
    if after_answer:
        await bot.send_message(chat_id, CONGRATS[randint(0, len(CONGRATS) - 1)])
    for msg in messages:
        await bot.send_message(chat_id, msg, reply_markup=None)
    if after_answer:
        await bot.send_message(
            chat_id,
            "Нажми 'Идем дальше', когда будешь готов к следующему заданию",
            reply_markup=markup,
        )


# ===== Message handlers =====
@bot.message_handler(state="*", commands=["start"])
async def start_ex(message):
    """
    Первая команда бота.
    Инициализация состояния и знакомство.
    """
    # State
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.set_state(message.from_user.id, "start", message.chat.id)
    # Messages
    await bot.send_message(
        message.chat.id,
        "Привет! Это начало квеста. Вот тебе координаты первой точки",
        reply_markup=markup,
    )
    await bot.send_location(message.chat.id, latitude=59.9477864117122, longitude=30.256183737214254)
    # Сохранить данные пользователя в БД
    dump_s3(UserInfo.to_dict(message.from_user), f"users/started/{message.from_user.id}.json")
    logger.info(f"Saved user with id {message.from_user.id} to S3 bucket {BUCKET_NAME}")


# TODO Определить шаг на котором мы приходим к финишу
@bot.message_handler(state="Prang")
async def finish_ex(message):
    """
    Финиш экскурсии.
    Поздравляем героя и заносим его в список
    """
    await bot.set_state(message.from_user.id, "finish", message.chat.id)
    await bot.send_message(message.chat.id, "Поздравляю. Вот тебе подарок (ТУТ ДОЛЖЕН БЫТЬ ПОДАРОК)")
    # Сохранить данные о прохождении квеста в БД
    dump_s3(UserInfo.to_dict(message.from_user), f"users/finished/{message.from_user.id}.json")


@bot.message_handler(state="finish")
async def after_finish_ex(message):
    await bot.send_message(
        message.chat.id,
        "Ты уже прошел квест. Если хочешь начать сначала напиши /start",
    )


# Excursion points
with open("./text.yaml", "r") as f:
    texts = load(f, SafeLoader)

answer_checkers = {
    "Хосе": lambda m: "гесс" in m,
    "Массон": lambda m: "яковлев" in m,
    "Гримм": lambda m: "1933" in m,
    "Парланд": lambda m: "обп" in m or "о.б.п." in m or "облсовет" in m or "осоавиахим" in m,
}


class QuestionHandler:
    def __init__(self, step: str, prev_step: str, is_correct: Callable[[str], bool]):
        self.step = step
        self.is_correct = is_correct

        bot.register_message_handler(self.question, state=prev_step)
        bot.register_message_handler(self.answer, state=f"Спросил_{self.step}")

    async def question(self, message):
        await bot.set_state(message.from_user.id, f"Спросил_{self.step}", message.chat.id)
        await send_messages(message.chat.id, texts[self.step]["вопрос"])

    async def answer(self, message):
        log_user_answer(self.step, message.text)
        if self.is_correct(message.text.lower()):
            await bot.set_state(message.from_user.id, f"{self.step}", message.chat.id)
            await send_messages(message.chat.id, texts[self.step]["кстати"], True)
        else:
            await bot.send_message(message.chat.id, "Это неправильный ответ")

# Наполняем логику бота из файла с текстами
prev_step = "start"
for point in texts.keys():
    try:
        checker = answer_checkers[point]
    except KeyError:
        raise RuntimeError(f"Нет функции проверки ответа для {point}")
    QuestionHandler(step=point, prev_step=prev_step, is_correct=checker)
    prev_step = point


bot.add_custom_filter(asyncio_filters.StateFilter(bot))
bot.add_custom_filter(asyncio_filters.IsDigitFilter())

# Polling

while True:
    try:
        asyncio.run(bot.infinity_polling())
    except KeyboardInterrupt:
        break
    except Exception as ex:
        logger.exception("Ошибка при поллинге. Перезапускаю процесс.", exc_info=ex)
        sleep(10)
        continue
