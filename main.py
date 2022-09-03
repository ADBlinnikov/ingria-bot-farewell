import asyncio
import json
import logging
import os
from random import randint, random
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
telebot.logger.setLevel(logging.DEBUG)


def log_user_answer(expected: str, answer: str) -> None:
    logger.info(f"Expected: {expected} Answer: {answer}")

# Excursion points
with open("./texts/text.yaml", "r") as f:
    texts = load(f, SafeLoader)

# Intro
with open("./texts/intro.yaml", "r") as f:
    intro_text = load(f, SafeLoader)

# Environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")
PROMO_15 = os.getenv("PROMO_15")
PROMO_100 = os.getenv("PROMO_100")
WIN_RATE = 0.33

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

async def log_state(message):
    state = await bot.current_states.get_state(message.from_user.id, message.chat.id)
    logger.info(f"State: {state}")

async def send_messages(chat_id: str, messages: List[str], after_answer: bool = False):
    if after_answer:
        await bot.send_message(chat_id, CONGRATS[randint(0, len(CONGRATS) - 1)])
    for msg in messages:
        if isinstance(msg, str):
            await bot.send_message(chat_id, msg, reply_markup=None)
        else:
            if msg["type"] == "photo":
                await bot.send_photo(chat_id, msg["file_id"])
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
    await log_state(message)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.set_state(message.from_user.id, "start", message.chat.id)
    # Messages
    await send_messages(message.chat.id, intro_text["data"], True)
    # Сохранить данные пользователя в БД
    dump_s3(UserInfo.to_dict(message.from_user), f"users/started/{message.from_user.id}.json")
    logger.info(f"Saved user with id {message.from_user.id} to S3 bucket {BUCKET_NAME}")


# TODO Определить шаг на котором мы приходим к финишу
@bot.message_handler(state="Энгельгардт")
async def finish_ex(message):
    """
    Финиш экскурсии.
    Поздравляем героя и заносим его в список
    """
    await log_state(message)
    await bot.set_state(message.from_user.id, "finish", message.chat.id)
    # Логика по определению промокода
    if random() < WIN_RATE:
        # Выиграл промокод на бесплатную экскурсию
        # TODO Проверка наличия бесплатных билетов (уже выдано менее 100)
        promo_100_available = TRUE
        if promo_100_available:
            await bot.send_message(message.chat.id, "Поздравляю. Вот тебе экскурсия бесплатно(ТУТ ДОЛЖЕН БЫТЬ ПОДАРОК)")
        else:
            await bot.send_message(message.chat.id, "Поздравляю. Вот тебе скидка на экскурсию (ТУТ ДОЛЖЕН БЫТЬ ПОДАРОК)")
    else:
        await bot.send_message(message.chat.id, "Поздравляю. Вот тебе скидка на экскурсию (ТУТ ДОЛЖЕН БЫТЬ ПОДАРОК)")
    # Сохранить данные о прохождении квеста в БД
    dump_s3(UserInfo.to_dict(message.from_user), f"users/finished/{message.from_user.id}.json")


@bot.message_handler(state="finish")
async def after_finish_ex(message):
    await log_state(message)
    await bot.send_message(
        message.chat.id,
        "Ты уже прошел квест. Если хочешь начать сначала напиши /start",
    )




answer_checkers = {
    "Хосе": lambda m: "гесс" in m,
    "Массон": lambda m: "яковлев" in m,
    "Гримм": lambda m: "1933" in m,
    "Парланд": lambda m: "обп" in m or "о.б.п." in m or "облсовет" in m or "осоавиахим" in m,
    "Чинизелли": lambda m: "34" in m,
    "Горвиц": lambda m: "товарищи" in m,
    "Грейг": lambda m: "прасков" in m,
    "Бекман": lambda m: "XIII.3" in m,
    "Бауэрмайстер": lambda m: "остров" in m or "мертвых" in m,
    "Вольф": lambda m: "песочные часы" in m,
    "Голгофа": lambda m: "череп" in m,
    "Чичагова": lambda m: "уроборос" in m,
    "Берд": lambda m: "тамара" in m,
    "Докучаев": lambda m: "могила посещается" in m,
    "Люгебиль": lambda m: "большой проспект в.о., дом. 31" in m,
    "Коваленко": lambda m: "коваленко" in m,
    "Флит": lambda m: "флит" in m,
    "Сюзор": lambda m: "сюзор" in m,
    "Энгельгардт": lambda m: "13" in m,
}


class QuestionHandler:
    def __init__(self, step: str, prev_step: str, is_correct: Callable[[str], bool]):
        self.step = step
        self.is_correct = is_correct

        bot.register_message_handler(self.question, state=prev_step)
        bot.register_message_handler(self.answer, state=f"Спросил_{self.step}")

    async def question(self, message):
        await log_state(message)
        await bot.set_state(message.from_user.id, f"Спросил_{self.step}", message.chat.id)
        await send_messages(message.chat.id, texts[self.step]["вопрос"])

    async def answer(self, message):
        await log_state(message)
        log_user_answer(texts[self.step]["ответ"], message.text)
        if "дальше" in message.text.lower() or self.is_correct(message.text.lower()):
            await bot.set_state(message.from_user.id, f"{self.step}", message.chat.id)
            await send_messages(message.chat.id, texts[self.step]["кстати"] if hasattr(texts[self.step], "кстати") else [], True)
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
