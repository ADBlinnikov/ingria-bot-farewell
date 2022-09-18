import asyncio
import json
import logging
import os
from datetime import datetime
from random import randint, random
from time import sleep
from typing import Callable, List

import boto3
import sqlalchemy as sqla
import telebot
from botocore.errorfactory import ClientError
from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.sqlite import DATETIME
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler
from telebot.asyncio_storage import StatePickleStorage
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from yaml import SafeLoader, load

# Logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)


def log_user_answer(expected: str, answer: str) -> None:
    logger.info(f"Expected: {expected} Answer: {answer}")


# Message content
with open("./text.yaml", "r") as f:
    texts = load(f, SafeLoader)

# Environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")
PROMO_15 = os.getenv("PROMO_15")
EXCURSION_START = datetime(2022, 10, 1)

# S3 client
boto3_session = boto3.session.Session()
s3 = boto3_session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
)


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


# Local database logic
Base = declarative_base()


def telegram_user_as_dict(data):
    return {
        "id": getattr(data, "id", None),
        "first_name": getattr(data, "first_name", None),
        "last_name": getattr(data, "last_name", None),
        "username": getattr(data, "username", None),
    }


class User(Base):
    __tablename__ = "User"
    # Telegram data
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    # Our data
    try_count = Column(Integer, default=5)
    started_at = Column(DATETIME, nullable=True)
    finished_at = Column(DATETIME, nullable=True)
    is_winner = Column(Boolean, nullable=True)

    def __repr__(self):
        return f"""<User (id={self.id}
            first_name={self.first_name}
            last_name={self.last_name}
            username={self.username}
            try_count={self.try_count}
            started_at={self.started_at}
            finished_at={self.finished_at}
            is_winner={self.is_winner})>"""


def get_or_create(session, model, **kwargs):
    instance = session.query(model).get(kwargs["id"])
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance


# Initialize database and create tables
engine = sqla.create_engine("sqlite:///data.db", echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(engine)

# Bot instance
class MyExceptionHandler(ExceptionHandler):
    def handle(self, exception):
        logger.error(exception)


bot = AsyncTeleBot(
    TOKEN,
    parse_mode="Markdown",
    state_storage=StatePickleStorage(),
    exception_handler=MyExceptionHandler(),
)

remove_keyboard = ReplyKeyboardRemove()


def one_btn_keyboard(text: str):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(text)
    return markup


get_going_markup = one_btn_keyboard("Идем дальше")
farewell_markup = one_btn_keyboard("В добрый путь!")
giveup_markup = one_btn_keyboard("Пропустить вопрос")
luther_what_markup = one_btn_keyboard("Так Смоленское или Лютеранское?")

CONGRATS = ["Это правильный ответ!", "Верно!", "Правильно", "В точку!"]


def random_congrats():
    return CONGRATS[randint(0, len(CONGRATS) - 1)]


# Bot helpers
async def log_state(message):
    state = await bot.current_states.get_state(message.from_user.id, message.chat.id)
    logger.info(f"State: {state}")


async def send_messages(
    chat_id: str,
    messages: List[str],
    markup=None,
):
    for msg in messages:
        if isinstance(msg, str):
            await bot.send_message(chat_id, msg, reply_markup=markup)
        else:
            if msg["type"] == "photo":
                await bot.send_photo(
                    chat_id,
                    msg["file_id"],
                    reply_markup=markup,
                    caption=msg.get("caption", None),
                )
            elif msg["type"] == "location":
                await bot.send_location(
                    chat_id,
                    latitude=msg["lat"],
                    longitude=msg["lng"],
                    horizontal_accuracy=25,
                )
            elif msg["type"] == "audio":
                await bot.send_audio(chat_id, msg["file_id"], reply_markup=markup)


# ===== Message handlers =====
@bot.message_handler(state="*", commands=["stats"])
async def stats(message):
    with Session() as s:
        users_count = s.query(func.count(User.id)).scalar()
        users_finished = s.query(func.count(User.id)).filter(User.finished_at != None).scalar()
    msg = f"Пользователей всего: {users_count}\n" f"Пользователей закончили квест: {users_finished}\n"
    await bot.send_message(message.chat.id, msg)


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
    await send_messages(message.chat.id, texts["вводная"], markup=luther_what_markup)
    # Парсим данные пользователя
    user_dict = telegram_user_as_dict(message.from_user)
    # Сохраним основные данные в s3
    dump_s3(user_dict, f"users/started/{message.from_user.id}.json")
    logger.info(f"Saved user with id {message.from_user.id} to s3://{BUCKET_NAME}/users/started")
    # Сохраним данные пользователя в БД, если их ещё нет
    try:
        with Session() as s:
            user = get_or_create(s, User, **user_dict)
            if user.started_at == None:
                user.started_at = datetime.utcnow()
            s.commit()
    except Exception as e:
        logger.exception("Ошибка при записи пользователя в таблицу", exc_info=e)


@bot.message_handler(state="start")
async def about_luther(message):
    # State
    await log_state(message)
    await bot.set_state(message.from_user.id, "Лютер", message.chat.id)
    # Messages
    await send_messages(message.chat.id, texts["Лютер"], markup=farewell_markup)


@bot.message_handler(state="Лютер")
async def enterance(message):
    # State
    await log_state(message)
    await bot.set_state(message.from_user.id, "вход", message.chat.id)
    # Messages
    await send_messages(message.chat.id, texts["вход"], markup=get_going_markup)


@bot.message_handler(state="Чичагова")
async def finish_ex(message):
    """
    Финиш экскурсии.
    Поздравляем героя и заносим его в список
    """
    await log_state(message)
    await bot.set_state(message.from_user.id, "finish", message.chat.id)
    # Наше почтение
    await bot.send_message(message.chat.id, "Ура, ты сделал это! Мы же говорили, что ты сможешь")
    # Сохранить данные о прохождении квеста в s3
    user_dict = telegram_user_as_dict(message.from_user)
    dump_s3(user_dict, f"users/finished/{message.from_user.id}.json")
    logger.info(f"Saved user with id {message.from_user.id} to s3://{BUCKET_NAME}/users/finished")
    # Также сохраним информацию в БД
    with Session() as s:
        user = get_or_create(s, User, **user_dict)
        # Запишем время первого завершения
        if user.finished_at == None:
            user.finished_at = datetime.utcnow()
        s.commit()
    # Логика по выдаче промокода
    await bot.send_message(message.chat.id, texts["победа15"].format(PROMO_15))
    # Ссылка на экскурсию
    if datetime.now() < EXCURSION_START:
        await bot.send_message(message.chat.id, texts["победа30сен"])
    else:
        await bot.send_message(message.chat.id, texts["победа1окт"])
    # Приглашаем на ОХВ
    await send_messages(message.chat.id, texts["ОХВ"], markup=remove_keyboard)
    # Оставьте отзыв
    await bot.send_message(
        message.chat.id,
        "Это наш первый квест по кладбищу. Будем благодарны, если ты оставишь отзыв 🙏 Любой! Даже плохой, будем работать над собой",
    )


@bot.message_handler(state="finish")
async def after_finish_ex(message):
    await log_state(message)
    # Сохраним отзыв в s3
    if "идем дальше" not in message.text.lower():
        dump_s3(message.text, f"users/feedback/{message.from_user.id}/{message.message_id}.json")
    await bot.send_message(
        message.chat.id,
        "Спасибо за отзыв! В любой момент можешь дополнить его написав ещё пару ласковых",
    )


answer_checkers = {
    "Энгельгардт": lambda m: "13" in m,
    "Дерево": lambda m: "5" in m,
    "Хосе": lambda m: "гесс" in m,
    "Берд": lambda m: "тамара" in m,
    "Гримм": lambda m: "1933" in m,
    "Парланд": lambda m: "обп" in m or "о.б.п." in m or "облсовет" in m or "осоавиахим" in m,
    "Симанский": lambda m: "севкабель" in m,
    "Пророков": lambda m: "фандер" in m or "флит" in m,
    "Чинизелли": lambda m: "34" in m,
    "Горвиц": lambda m: "товарищи" in m,
    "Грейг": lambda m: "прасков" in m,
    "Бауэрмайстер": lambda m: "остров" in m or "мертвых" in m,
    "Бекман": lambda m: "xii" in m or "12" in m,
    "Вольф": lambda m: "песочные часы" in m,
    "Голгофа": lambda m: "череп" in m,
    "Чичагова": lambda m: "уроборос" in m,
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
        await send_messages(
            message.chat.id,
            texts["экскурсия"][self.step]["вопрос"],
            markup=remove_keyboard,
        )

    async def answer(self, message):
        await log_state(message)
        log_user_answer(texts["экскурсия"][self.step]["ответ"], message.text)
        with Session() as s:
            user_dict = telegram_user_as_dict(message.from_user)
            user = get_or_create(s, User, **user_dict)
            try_count = user.try_count
            user_gave_up = "пропустить вопрос" in message.text.lower() and try_count > 0
            user_answered = self.is_correct(message.text.lower())
            if user_gave_up or user_answered:
                await bot.set_state(message.from_user.id, f"{self.step}", message.chat.id)
                if self.is_correct(message.text.lower()):
                    await bot.send_message(message.chat.id, random_congrats())
                await send_messages(message.chat.id, texts["экскурсия"][self.step].get("кстати", []))
                await bot.send_message(
                    message.chat.id,
                    "Нажми 'Идем дальше', когда будешь готов к следующему заданию",
                    reply_markup=get_going_markup,
                )
                if user_gave_up:
                    user.try_count -= 1
            else:
                # У пользователя остались попытки
                if try_count > 0:
                    await bot.send_message(
                        message.chat.id,
                        f"Можешь попытаться ещё раз или пропустить. Ты можешь пропустить ещё {try_count} вопросов",
                        reply_markup=giveup_markup,
                    )
                # Следующие попытки
                else:
                    await bot.send_message(
                        message.chat.id, "Это неправильный ответ, попробуй ещё раз. Возможности пропустить больше нет"
                    )
            s.commit()
            s.close()


# Наполняем логику бота из файла с текстами
prev_step = "вход"
for point in texts["экскурсия"].keys():
    try:
        checker = answer_checkers[point]
    except KeyError:
        raise RuntimeError(f"Нет функции проверки ответа для {point}")
    QuestionHandler(step=point, prev_step=prev_step, is_correct=checker)
    prev_step = point


bot.add_custom_filter(asyncio_filters.StateFilter(bot))

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
