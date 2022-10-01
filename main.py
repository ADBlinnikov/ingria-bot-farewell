import asyncio
import logging
from time import sleep

from bot import bot

# Polling
while True:
    try:
        asyncio.run(bot.infinity_polling())
    except KeyboardInterrupt:
        break
    except Exception as ex:
        logging.exception("Ошибка при поллинге. Перезапускаю процесс.", exc_info=ex)
        sleep(10)
        continue
