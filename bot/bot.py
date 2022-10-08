import logging
import os
from datetime import datetime, timedelta
from random import randint
from typing import Callable, List

import telebot
from sqlalchemy import func, desc
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot, ExceptionHandler
from telebot.asyncio_storage import StatePickleStorage
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from yaml import SafeLoader, load

from .db import Session, User
from .s3 import dump_s3

PROMO_15 = os.getenv("PROMO_15")
EXCURSION_START = datetime(2022, 10, 1)

# Logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)


def log_user_answer(expected: str, answer: str) -> None:
    logger.info(f"Expected: {expected} Answer: {answer}")


# Message content
with open("./text.yaml", "r") as f:
    texts = load(f, SafeLoader)


# Bot instance
class MyExceptionHandler(ExceptionHandler):
    def handle(self, exception):
        logger.error(exception)


bot = AsyncTeleBot(
    os.getenv("TELEGRAM_TOKEN"),
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

GET_GOING_TEXT = "Нажми 'Идем дальше', когда будешь готов к следующему заданию"
WRONG_ANSWER_TEXT = "Это неправильный ответ, попробуй ещё раз. Возможности пропустить больше нет"
TRY_AGAIN_TEXT = "Можешь попытаться ещё раз или пропустить. Ты можешь пропустить ещё {}"
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
            elif msg["type"] == "document":
                await bot.send_document(
                    chat_id,
                    msg["file_id"],
                    reply_markup=markup,
                    caption=msg.get("caption", None),
                )
            elif msg["type"] == "media_group":
                logger.debug(f"Media: {msg['media']}")
                media = [InputMediaPhoto(media=m["media"], caption=m.get("caption", None)) for m in msg["media"]]
                await bot.send_media_group(chat_id, media)


# ===== Message handlers =====
@bot.message_handler(state="*", commands=["setstate"])
async def set_state(message):
    new_state = message.text.split(" ")[1]
    msg = f"Состояние обновлено на: {new_state}"
    await bot.set_state(message.from_user.id, new_state, message.chat.id)
    await bot.send_message(message.chat.id, msg)


@bot.message_handler(state="*", commands=["stats"])
async def stats(message):
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_ago = today_midnight - timedelta(days=7)
    with Session.begin() as s:
        users_count = s.query(func.count(User.id)).scalar()
        users_finished = s.query(func.count(User.id)).filter(User.finished_at != None).scalar()
        users_per_day = (
            s.query(func.strftime("%Y-%m-%d", User.finished_at), func.count(User.id))
            .group_by(func.strftime("%Y-%m-%d", User.finished_at))
            .order_by(desc(func.strftime("%Y-%m-%d", User.finished_at)))
            .filter(User.finished_at >= days_ago)
            .all()
        )
    daily_stats = "\n".join([f"{i[0]} {i[1]}" for i in users_per_day])
    msg = (
        f"Пользователей всего: {users_count}\n"
        + f"Пользователей закончили квест: {users_finished}\n"
        + f"За последние 7 дней:\n{daily_stats}\n"
    )
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
    user = User(message.from_user)
    # Сохраним основные данные в s3
    dump_s3(user.to_dict(), f"users/started/{message.from_user.id}.json")
    # Сохраним данные пользователя в БД, если их ещё нет
    try:
        with Session.begin() as s:
            user = user.get_or_create(s)
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
    await send_messages(message.chat.id, texts["победа"], markup=remove_keyboard)
    # Приглашаем на ОХВ
    await send_messages(message.chat.id, texts["ОХВ"], markup=remove_keyboard)
    # Оставьте отзыв
    await bot.send_message(
        message.chat.id,
        "Это наш первый квест по кладбищу. Будем благодарны, если ты оставишь отзыв 🙏 Любой! Даже плохой, будем работать над собой. Отзыв можно написать прямо здесь 👇",
    )
    # Сохранить данные о прохождении квеста в s3
    user = User(message.from_user)
    dump_s3(user.to_dict(), f"users/finished/{message.from_user.id}.json")
    # Также сохраним информацию в БД
    with Session.begin() as s:
        user = user.get_or_create(s)
        # Запишем время первого завершения
        if user.finished_at == None:
            user.finished_at = datetime.utcnow()
            s.commit()


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
    "Горвиц": lambda m: "эх" in m or "товарищи" in m,
    "Грейг": lambda m: "прасков" in m,
    "Бауэрмайстер": lambda m: "остров" in m or "мертвых" in m,
    "Бекман": lambda m: "xii" in m or "12" in m,
    "Вольф": lambda m: "песочные" in m or "часы" in m,
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
        with Session.begin() as s:
            user = User(message.from_user).get_or_create(s)
            user_gave_up = "пропустить" in message.text.lower() and user.try_count > 0
            user_answered = self.is_correct(message.text.lower())
            if user_gave_up or user_answered:
                await bot.set_state(message.from_user.id, f"{self.step}", message.chat.id)
                if user_gave_up:
                    user.try_count -= 1
                elif user_answered:
                    await bot.send_message(message.chat.id, random_congrats())
                await send_messages(message.chat.id, texts["экскурсия"][self.step].get("кстати", []))
                await bot.send_message(message.chat.id, GET_GOING_TEXT, reply_markup=get_going_markup)
            else:
                # У пользователя остались попытки
                if user.try_count > 0:
                    await bot.send_message(
                        message.chat.id,
                        TRY_AGAIN_TEXT.format(user.try_count),
                        reply_markup=giveup_markup,
                    )
                else:
                    await bot.send_message(message.chat.id, WRONG_ANSWER_TEXT)
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
