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
from typing import List
from random import randint

# Logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)


def log_user_answer(point: str, expected: str, answer: str) -> None:
    logger.info(f"Point: {point} Expected: {expected} Answer: {answer}")


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
QUESTION_HOSE = [
    "В первое время на территории Санкт-Петербурга неправославных христиан хоронили вместе.",
    "Например, первое католическое кладбище в Петербурге появилось только в 1856 году на Выборгской стороне. Поэтому на Смоленском Лютеранском кладбище,  действующее с 1747 года, периодически можно встретить захоронения католиков и иных представителей протестантских течений.",
    "Как раз здесь нашёл своё последние пристанище испанец, видный военный деятель и основатель города Одессы.",
    "Тем не менее независимо от принадлежности крест – это главный символ для христиан, часто устанавливаемый на захоронение. Вот и рядом с этим военным есть подобная могила.",
    "Напишите фамилию человека с крестом на надгробии.",
]

INFO_HOSE = [
    "Хосе де Рибас или Иосиф (Осип) Михайлович Дерибас родился 13 сентября 1751 г. в итальянском городе Неаполе. Отец Мигель де Рибас, принадлежавший к старинному каталонскому дворянскому роду, переселился туда из Испании..."
]


@bot.message_handler(state="start")
async def questionHose(message):
    await bot.set_state(message.from_user.id, "ВопросХосе", message.chat.id)
    await send_messages(message.chat.id, QUESTION_HOSE)


@bot.message_handler(state="ВопросХосе")
async def pointHose(message):
    log_user_answer("Hose", "Гессъ", message.text)
    if "гесс" in message.text.lower():
        await bot.set_state(message.from_user.id, "Хосе", message.chat.id)
        await send_messages(message.chat.id, INFO_HOSE, True)
    else:
        await bot.send_message(message.chat.id, "Это неправильный ответ")


QUESTION_MASSON = [
    "Прогуливаясь по историческим кладбищам, нередко можно встретить весьма необычные надгробия в форме дерева",
    "Найдите необычный памятник в данной области и введите фамилию покойного",
]

INFO_MASSON = [
    "В Средневековье в Европе появляются разные объединения цехов, в том числе и братство каменщиков. Благодаря востребованности данной специальности члены цеха пользовались привилегиями и льготами. Данную группу людей называли “вольными каменщиками” , на старофранцузский манер переводится как masson..."
]


@bot.message_handler(state="Хосе")
async def questionMasson(message):
    await bot.set_state(message.from_user.id, "ВопросМассон", message.chat.id)
    await send_messages(message.chat.id, QUESTION_MASSON)


@bot.message_handler(state="ВопросМассон")
async def pointMasson(message):
    log_user_answer("Masson", "Яковлева", message.text)
    if "яковлев" in message.text.lower():
        await bot.set_state(message.from_user.id, "Массон", message.chat.id)
        await send_messages(message.chat.id, INFO_MASSON, True)
    else:
        await bot.send_message(message.chat.id, "Это неправильный ответ")


QUESTION_GRIMM = [
    "На данном кладбище огромное количество деятелей культуры и искусства",
    "Например, представители одной очень известной династии архитекторов. Отец был автором историко-архитектурного исследования “Памятники византийской архитектуры в Грузии и Армении”, а сын являлся востребованным архитекторам как в Российской империи, так и при советской власти.",
    "Найдите их семейное захоронение, а для ответа укажите год смерти соседней могилы Г.Ю.Лаан",
]

INFO_GRIMM = [
    "Давида Ивановича Гримма родился в Санкт-Петербурге в 1823 году, учился в Немецкой школе святого Петра а затем  в Академии Художеств. За успехи в рисовании и зодчестве был награждён золотыми и серебряными медалями Академии."
]


@bot.message_handler(state="Массон")
async def questionGrimm(message):
    await bot.set_state(message.from_user.id, "ВопросГримм", message.chat.id)
    await send_messages(message.chat.id, QUESTION_GRIMM)


@bot.message_handler(state="ВопросГримм")
async def pointGrimm(message):
    log_user_answer("Grimm", "1933", message.text)
    if "1933" in message.text.lower():
        await bot.set_state(message.from_user.id, "Гримм", message.chat.id)
        await send_messages(message.chat.id, INFO_GRIMM, True)
    else:
        await bot.send_message(message.chat.id, "Это неправильный ответ")


QUESTION_PARLAND = [
    "Этот храм-мемориал в честь Воскресения Христова является шедевром архитектуры в русском стиле",
    "На данном кладбище покоится автор данного здания. Найдите захоронения этого архитектора",
    "Для ответа перепишите информацию с соседней могилы: полное название организации, где работал старший инспектор Львов",
]

INFO_PARLAND = [
    "Альфред Александрович Парланд, архитектор Спаса на Крови, родился в 1842 г. в купеческой семье",
    "Его дед, Джон Парланд, был преподавателем английского языка в семье императора Павла I",
]


@bot.message_handler(state="Гримм")
async def questionParland(message):
    await bot.set_state(message.from_user.id, "ВопросПарланд", message.chat.id)
    await send_messages(message.chat.id, QUESTION_PARLAND)


@bot.message_handler(state="ВопросПарланд")
async def pointParland(message):
    log_user_answer("Parland", "О.Б.П. Облсовета Осоавиахима", message.text)
    if (
        "о.б.п." in message.text.lower()
        or "обп" in message.text.lower()
        or "облсовет" in message.text.lower()
        or "осоавиахим" in message.text.lower()
    ):
        await bot.set_state(message.from_user.id, "Парланд", message.chat.id)
        await send_messages(message.chat.id, INFO_PARLAND, True)
    else:
        await bot.send_message(message.chat.id, "Это неправильный ответ")

QUESTION_CINISELLI = [
    "Принято считать, что в середине XVIII в. в Англии, Филипп Астлей основал первый в мире постоянный цирк",
    "Для этого в Лондоне появилось специальное здание для школы верховой езды, названное амфитеатром. Он также является основателем и первой цирковой династии",
    "На территории Смоленского Лютеранского кладбища покоится создатель цирка на Фонтанке",
    "Для ответа обратите внимание на соседнее небольшое семейное захоронение. Взгляните на него и посчитайте, сколько лет было  маленькой девочке Татьяне Дмитриевне."
]

INFO_CINISELLI = [
    "Цирк Чинизелли – это первый в России каменный стационарный цирк. Сам Гаэтано Чинизелли родился 1 марта 1815 года в Италии",
    "С двенадцати лет стал учеником в цирковой труппе Алессандро Гверра. В 1846 году по приглашению своего учителя приехал в Россию вместе с женой, наездницей Вильгельминой Гинне и шестилетним сыном Андреа. Гверра владел деревянным цирком в столице, но в 1847 заведение было закрыто из-за финансовых проблем.",
    "Таким образом, Гаэтано Чинизелли на несколько лет переезжает в Лондон"
]

@bot.message_handler(state="Парланд")
async def questionCiniselli(message):
    await bot.set_state(message.from_user.id, "ВопросЧинизелли", message.chat.id)
    await send_messages(message.chat.id, QUESTION_CINISELLI)


@bot.message_handler(state="ВопросЧинизелли")
async def pointCiniselli(message):
    log_user_answer("Ciniselli", "О.Б.П. Облсовета Осоавиахима", message.text)
    if "34" in message.text.lower():
        await bot.set_state(message.from_user.id, "Чинизелли", message.chat.id)
        await send_messages(message.chat.id, INFO_CINISELLI, True)
    else:
        await bot.send_message(message.chat.id, "Это неправильный ответ")



bot.add_custom_filter(asyncio_filters.StateFilter(bot))
bot.add_custom_filter(asyncio_filters.IsDigitFilter())

# Polling
import asyncio

asyncio.run(bot.polling())
