# send_daily_message.py
import logging
import telebot
from datetime import datetime
from zoneinfo import ZoneInfo
from config import config
from services.storage_service import StorageService
from services.schedule_service import ScheduleService

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

    # --- ИСПРАВЛЕНИЕ: Создаем объект бота ЗДЕСЬ, ДО блока try...except ---
    # Таким образом переменная `bot` будет доступна во всех блоках ниже.
    try:
        bot = telebot.TeleBot(config.bot_token)
    except Exception as e:
        logger.critical(f"Не удалось инициализировать бота. Возможно, проблема с токеном. Ошибка: {e}")
        return # Выходим, если даже бот не создался

    # --- НАЧАЛО ОСНОВНОГО БЛОКА ОБРАБОТКИ ---
    try:
        logger.info(f"Попытка отправки сообщения в тему {thread_id} чата {chat_id}.")
        bot.send_message(chat_id, message_text, message_thread_id=thread_id)

        # Записываем дату отправки ТОЛЬКО в случае успеха
        storage.set_last_sent_date(today_str)
        logger.info(f"Сообщение успешно отправлено.")

    except telebot.apihelper.ApiTelegramException as e:
        # Ловим конкретно ошибку API Telegram
        logger.error(f"Ошибка API Telegram при отправке в топик {thread_id}: {e}")

        # Проверяем, связана ли ошибка с проблемой в топике/доступе
        if e.error_code == 403 or "topic not found" in str(e).lower() or "topic closed" in str(e).lower():
            logger.warning("Топик недоступен. Попытка отправить сообщение в основную группу (без топика)...")
            try:
                # ЗАПАСНОЙ ПЛАН: Отправляем сообщение в общий чат, без thread_id
                fallback_text = (f"Внимание! Не удалось доставить сообщение в нужный топик (ID: {thread_id}). "
                                 f"Возможно, он был удален, закрыт или бот потерял к нему доступ.\n\n"
                                 "--- Сообщение на сегодня ---\n"
                                 f"{message_text}")
                bot.send_message(chat_id, fallback_text)

                # Сообщение доставлено (хоть и не идеально), так что можно засчитать отправку
                storage.set_last_sent_date(today_str)
                logger.info("Запасное сообщение успешно отправлено в основную группу.")

            except Exception as fallback_e:
                logger.critical(f"Не удалось выполнить даже запасную отправку в основную группу. Ошибка: {fallback_e}")

    except Exception as e:
        # Ловим все остальные возможные ошибки (проблемы с сетью и т.д.)
        logger.critical(f"Произошла непредвиденная критическая ошибка: {e}", exc_info=True)


# Этот блок должен быть здесь, с нулевым отступом
if __name__ == "__main__":
    send_the_message()