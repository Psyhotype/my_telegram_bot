# config.py
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Определяем путь к .env файлу явно
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)


@dataclass(frozen=True)
class Config:
    """Централизованный класс для всех настроек приложения."""
    bot_token: str
    timezone: str
    target_time: str
    base_dir: Path

    # Пути к файлам данных
    @property
    def active_topic_file(self) -> Path:
        return self.base_dir / "active_topic.json"

    @property
    def last_sent_date_file(self) -> Path:
        return self.base_dir / "last_sent_date.txt"

    @property
    def schedule_file(self) -> Path:
        return self.base_dir / "schedule_texts.json"


def load_config() -> Config:
    """Загружает и валидирует конфигурацию из переменных окружения."""
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("Токен бота (BOT_TOKEN) не найден в .env или переменных окружения.")

    # Используем Path(__file__).parent для определения базовой директории
    # base_dir будет путем к папке, где лежит сам config.py
    base_dir = Path(__file__).resolve().parent

    return Config(
        bot_token=token,
        timezone='Europe/Moscow',
        target_time="09:00",
        base_dir=base_dir,
    )


# Создаем один экземпляр конфигурации для импорта в другие модули
config = load_config()