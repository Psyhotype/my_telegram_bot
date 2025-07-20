# send_daily_message.py
import logging
from config import config
from services.storage_service import StorageService
from services.schedule_service import ScheduleService
from bot_logic import SchedulerBot  # Мы импортируем класс, чтобы использовать его методы
import telebot
from datetime import datetime
from zoneinfo import ZoneInfo

# Настраиваем логирование, чтобы видеть результат в логах на хостинге
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def send_the_message():
    """
    Эта функция запускается один раз, отправляет сообщение и завершается.
    """
    logger = logging.getLogger(__name__)
    logger.info("Запущена задача по отправке ежедневного расписания...")

    storage = StorageService(config.active_topic_file, config.last_sent_date_file)
    schedule = ScheduleService(config.schedule_file)

    # Проверяем, не было ли уже отправлено сообщение сегодня
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    if storage.get_last_sent_date() == today_str:
        logger.warning(f"Сообщение на {today_str} уже было отправлено. Пропуск.")
        return

    active_topic = storage.get_active_topic()
    if not active_topic:
        logger.error("Не удалось отправить сообщение: бот не привязан к теме.")
        return

    chat_id = active_topic['chat_id']
    thread_id = active_topic['thread_id']
    day_index = now.weekday()
    message_text = schedule.get_schedule_for_day(day_index)

    if not message_text:
        message_text = "На сегодня расписание не найдено."

    try:
        bot = telebot.TeleBot(config.bot_token)
        bot.send_message(chat_id, message_text, message_thread_id=thread_id)
        storage.set_last_sent_date(today_str)
        logger.info(f"Сообщение успешно отправлено в тему {thread_id} чата {chat_id}.")
    except Exception as e:
        logger.exception(f"Критическая ошибка при отправке сообщения: {e}")


if __name__ == "__main__":
    send_the_message()