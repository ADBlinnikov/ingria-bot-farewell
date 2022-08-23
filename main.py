import logging
import os
import boto3
from botocore.errorfactory import ClientError
import json
from dotenv import load_dotenv
import telebot
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import ReplyKeyboardMarkup

# Logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

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


bot = AsyncTeleBot(
    TOKEN, state_storage=StateMemoryStorage(), exception_handler=MyExceptionHandler()
)

markup = ReplyKeyboardMarkup(resize_keyboard=True)
markup.add("Идем дальше")

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
    await bot.send_location(
        message.chat.id, latitude=59.9477864117122, longitude=30.256183737214254
    )
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
    await bot.send_message(
        message.chat.id, "Поздравляю. Вот тебе подарок (ТУТ ДОЛЖЕН БЫТЬ ПОДАРОК)"
    )
    # Сохранить данные о прохождении квеста в БД
    dump_s3(UserInfo.to_dict(message.from_user), f"users/finished/{message.from_user.id}.json")


@bot.message_handler(state="finish")
async def after_finish_ex(message):
    await bot.send_message(
        message.chat.id,
        "Ты уже прошел квест. Если хочешь начать сначала напиши /start",
    )

# Excursion points
@bot.message_handler(state="start")
async def pointHose(message):
    """
    1. Хосе де Рибас (Рядом надгробия Е.Е.Гессъ 1796-1850, описать тип надгробия)
    """
    if "дальше" in message.text.lower():
        await bot.set_state(message.from_user.id, "Хосе", message.chat.id)
        await bot.send_message(message.chat.id, "Это Хосе де Рибас")
        await bot.send_message(
            message.chat.id, "Тут должен быть вопрос для перехода к следующему шагу"
        )
    else:
        await bot.send_message(
            message.chat.id, "Напиши 'Идем дальше' чтобы перейти к следующей точке"
        )
        await bot.send_message(message.chat.id, "Ты написал:")
        await bot.send_message(message.chat.id, message.text)


@bot.message_handler(state="Хосе")
async def pointMason(message):
    """
    2. “Масонская” могила в форме дерева.
    """
    if message.text:
        await bot.set_state(message.from_user.id, "Масонская", message.chat.id)
        await bot.send_message(
            message.chat.id,
            "Я должен проверить, что ты мне написал, но пока не знаю что именно. Поэтому просто смотри что ты написал:",
        )
        await bot.send_message(message.chat.id, message.text)
        await bot.send_message(message.chat.id, "А могила очевидно массонская")


@bot.message_handler(state="Масонская")
async def pointGrimm(message):
    """
    3. Гриммы (рядом могила Г.Ю.Лаан. 1933)
    """
    if message.text:
        await bot.set_state(message.from_user.id, "Гриммы", message.chat.id)
        await bot.send_message(
            message.chat.id, "Это могила семейства Гримм. Рядом могила Г.Ю. Лаан"
        )


@bot.message_handler(state="Гриммы")
async def pointParland(message):
    """
    4. Парланд  (рядом Львов Ст. Инспектор О.Б.П. Облсовета Осоавиахима
    """
    if message.text:
        await bot.set_state(message.from_user.id, "Парланд", message.chat.id)
        await bot.send_message(message.chat.id, "Это Парланд")


@bot.message_handler(state="Парланд")
async def pointPrang(message):
    """
    5. Johann Prang (1848) ??
    """
    if message.text:
        await bot.set_state(message.from_user.id, "Prang", message.chat.id)
        await bot.send_message(message.chat.id, "Это Prang")


bot.add_custom_filter(asyncio_filters.StateFilter(bot))
bot.add_custom_filter(asyncio_filters.IsDigitFilter())

# Polling
import asyncio

asyncio.run(bot.polling())
