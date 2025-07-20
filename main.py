# main.py
import logging
import signal
import sys
import telebot
from config import config
from services.storage_service import StorageService
from services.schedule_service import ScheduleService
from bot_logic import SchedulerBot

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Уменьшаем "шум" от библиотеки telebot
logging.getLogger("telebot").setLevel(logging.WARNING)


def main():
    """Главная функция приложения."""
    logger = logging.getLogger(__name__)

    try:
        # 1. Инициализация сервисов (зависимостей)
        storage = StorageService(config.active_topic_file, config.last_sent_date_file)
        schedule = ScheduleService(config.schedule_file)

        # 2. Инициализация экземпляра telebot
        # threaded=False важно для корректной работы graceful shutdown
        bot_instance = telebot.TeleBot(config.bot_token, threaded=False)

        # 3. Создание и "внедрение" зависимостей в основной класс бота
        app = SchedulerBot(config, bot_instance, storage, schedule)

        # 4. Настройка изящного завершения (Graceful Shutdown)
        def shutdown_handler(signum, frame):
            logger.info(f"Получен сигнал {signal.Signals(signum).name}. Завершение работы...")
            app.stop()
            sys.exit(0)

        # SIGINT (Ctrl+C) работает везде
        signal.signal(signal.SIGINT, shutdown_handler)

        # SIGTERM не существует на Windows, поэтому добавляем его только для других систем
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, shutdown_handler)

        # 5. Запуск
        app.run()

    except (ValueError, FileNotFoundError) as e:
        logging.critical(f"Критическая ошибка при запуске: {e}")
        sys.exit(1)
    except Exception as e:
        logging.critical("Непредвиденная критическая ошибка в приложении.", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()