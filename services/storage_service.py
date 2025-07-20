# services/storage_service.py
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class StorageService:
    """
    Сервис для атомарного чтения и записи данных в файловую систему.
    Абстрагирует логику работы с файлами от остального приложения.
    """
    def __init__(self, active_topic_path: Path, last_sent_date_path: Path):
        self.active_topic_path = active_topic_path
        self.last_sent_date_path = last_sent_date_path

    def _safe_write(self, filepath: Path, content: str) -> None:
        """Атомарная запись в файл через временный файл."""
        temp_filepath = filepath.with_suffix(filepath.suffix + ".tmp")
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                f.write(content)
            # shutil.move является атомарной операцией в большинстве ОС
            shutil.move(str(temp_filepath), str(filepath))
        except Exception as e:
            logger.exception(f"Ошибка при безопасной записи в файл {filepath}: {e}")
            if temp_filepath.exists():
                os.remove(temp_filepath)

    def get_active_topic(self) -> Optional[Dict[str, Any]]:
        """
        Читает информацию о привязанной теме из JSON-файла.
        Возвращает None, если файл не найден или содержит ошибку.
        """
        if not self.active_topic_path.exists():
            return None
        try:
            with open(self.active_topic_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.exception(f"Ошибка при чтении файла активной темы: {e}")
            return None

    def save_active_topic(self, topic_info: Optional[Dict[str, Any]]) -> None:
        """
        Сохраняет информацию о теме. Если topic_info это None, удаляет файл.
        """
        if topic_info:
            self._safe_write(self.active_topic_path, json.dumps(topic_info, indent=4))
            logger.info(f"Информация о теме сохранена в {self.active_topic_path}")
        elif self.active_topic_path.exists():
            self.active_topic_path.unlink()
            logger.info(f"Файл {self.active_topic_path} удалён (бот отвязан).")

    def get_last_sent_date(self) -> Optional[str]:
        """
        Читает дату последней отправки расписания из файла.
        """
        if not self.last_sent_date_path.exists():
            return None
        try:
            return self.last_sent_date_path.read_text(encoding="utf-8").strip()
        except IOError as e:
            logger.error(f"Не удалось прочитать файл последней отправки: {e}")
            return None

    def set_last_sent_date(self, date_str: str) -> None:
        """
        Записывает дату последней отправки расписания.
        """
        self._safe_write(self.last_sent_date_path, date_str)