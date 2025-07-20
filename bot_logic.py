# bot_logic.py
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import telebot
from telebot import types

from config import Config
from services.schedule_service import ScheduleService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

COMMANDS_LIST = [
    ("start", "Привязать бота к текущей теме."),
    ("stop", "Отвязать бота от темы."),
    ("schedule", "Показать расписание на любой день."),
    ("help", "Показать список доступных команд.")
]


class SchedulerBot:
    """
    Основной класс бота, который связывает логику Telegram
    с сервисным слоем приложения.
    """
    def __init__(
        self,
        config: Config,
        bot: telebot.TeleBot,
        storage: StorageService,
        schedule: ScheduleService
    ):
        self.config = config
        self.telebot = bot
        self.storage = storage
        self.schedule = schedule
        self.tz = ZoneInfo(self.config.timezone)
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

    def _send_daily_schedule(self) -> None:
        """Отправляет ежедневное расписание в привязанную тему."""
        active_topic = self.storage.get_active_topic()
        if not active_topic:
            logger.warning("Пропуск ежедневной отправки: бот не привязан к теме.")
            return

        chat_id = active_topic['chat_id']
        thread_id = active_topic['thread_id']

        try:
            now = datetime.now(self.tz)
            day_index = now.weekday()
            message_text = self.schedule.get_schedule_for_day(day_index)
            if not message_text:
                message_text = "На сегодня расписание не найдено."

            self.telebot.send_message(chat_id, message_text, message_thread_id=thread_id)
            self.storage.set_last_sent_date(now.strftime("%Y-%m-%d"))
            logger.info(f"Расписание успешно отправлено в тему {thread_id} чата {chat_id}.")
        except Exception as e:
            logger.exception(f"Критическая ошибка при отправке сообщения в чат {chat_id}: {e}")

    def _schedule_checker(self) -> None:
        """Фоновый процесс, проверяющий время для отправки расписания."""
        logger.info(f"Планировщик запущен. Проверка каждую минуту на {self.config.target_time} {self.config.timezone}.")
        while not self._stop_event.is_set():
            try:
                now = datetime.now(self.tz)
                last_sent = self.storage.get_last_sent_date()
                is_time_to_send = now.strftime("%H:%M") == self.config.target_time
                is_not_sent_today = last_sent != now.strftime("%Y-%m-%d")

                if is_time_to_send and is_not_sent_today:
                    logger.info("Время отправки настало. Запускаю отправку.")
                    self._send_daily_schedule()
            except Exception as e:
                logger.exception("Ошибка в цикле планировщика.")

            # Ожидаем 60 секунд или до сигнала остановки
            self._stop_event.wait(60)
        logger.info("Планировщик остановлен.")

    def _register_handlers(self) -> None:
        """Регистрирует все обработчики команд и колбэков."""

        @self.telebot.message_handler(commands=['start'])
        def _cmd_start(message: types.Message):
            if message.is_topic_message and message.message_thread_id:
                topic_info = {'chat_id': message.chat.id, 'thread_id': message.message_thread_id}
                self.storage.save_active_topic(topic_info)
                self.telebot.reply_to(message,
                                      "✅ Бот успешно привязан к этой теме.\nЕжедневное расписание будет приходить сюда в 9:00 МСК.")
            else:
                self.telebot.reply_to(message,
                                      "⚠️ Пожалуйста, используйте эту команду внутри нужной темы (топика) в группе.")

        @self.telebot.message_handler(commands=['stop'])
        def _cmd_stop(message: types.Message):
            self.storage.save_active_topic(None)
            self.telebot.reply_to(message, "❌ Бот отвязан от темы. Автоматическая отправка расписания прекращена.")

        @self.telebot.message_handler(commands=['help'])
        def _cmd_help(message: types.Message):
            text = "ℹ️ *Доступные команды:*\n\n" + "\n".join([f"/{cmd} — {desc}" for cmd, desc in COMMANDS_LIST])
            self.telebot.reply_to(message, text, parse_mode="Markdown")

        @self.telebot.message_handler(commands=['schedule'])
        def _cmd_schedule(message: types.Message):
            markup = types.InlineKeyboardMarkup(row_width=3)
            buttons = [
                types.InlineKeyboardButton(f"📅 {day_name}", callback_data=f"day_{i}")
                for i, day_name in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])
            ]
            markup.add(*buttons)
            self.telebot.send_message(message.chat.id, "Выберите день недели:", reply_markup=markup,
                                      message_thread_id=message.message_thread_id)

        @self.telebot.callback_query_handler(func=lambda call: call.data.startswith("day_"))
        def _callback_schedule(call: types.CallbackQuery):
            try:
                day_index = int(call.data.split("_")[1])
                text = self.schedule.get_schedule_for_day(day_index)
                if not text:
                    text = "На этот день расписание отсутствует."

                self.telebot.answer_callback_query(call.id)
                self.telebot.send_message(call.message.chat.id, text, message_thread_id=call.message.message_thread_id)
            except Exception as e:
                logger.error(f"Ошибка при обработке callback'а расписания: {e}")
                self.telebot.answer_callback_query(call.id, "Произошла ошибка, попробуйте позже.", show_alert=True)

        logger.info("Обработчики команд зарегистрированы.")

    def run(self) -> None:
        """Запускает бота и все его компоненты."""
        logger.info("Запуск бота...")
        try:
            bot_commands = [types.BotCommand(cmd, desc) for cmd, desc in COMMANDS_LIST]
            self.telebot.set_my_commands(bot_commands)
            logger.info("Команды бота установлены в меню.")
        except Exception as e:
            logger.error(f"Не удалось установить команды бота: {e}")

        self._register_handlers()

        # daemon=True важно, чтобы основной поток не ждал этот поток при завершении,
        # но мы все равно делаем .join() в методе stop() для чистого завершения.
        self._scheduler_thread = threading.Thread(target=self._schedule_checker, daemon=True)
        self._scheduler_thread.start()

        logger.info("Бот готов к работе и ожидает сообщений.")
        self.telebot.infinity_polling(skip_pending=True)
        logger.info("Бот прекратил работу.")

    def stop(self) -> None:
        """Останавливает бота и его фоновые процессы."""
        logger.info("Получен сигнал на остановку бота...")
        self._stop_event.set()
        self.telebot.stop_polling()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        logger.info("Бот успешно остановлен.")