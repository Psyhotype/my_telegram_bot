# services/schedule_service.py
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ScheduleService:
    """
    Сервис для управления расписанием.
    Кэширует расписание в памяти и перезагружает при изменении файла.
    """
    def __init__(self, schedule_path: Path):
        self.schedule_path = schedule_path
        self._cache: Dict[str, Any] = {}
        self._mtime: float = 0
        self._load_schedule()

    def _load_schedule(self) -> None:
        """Внутренний метод для загрузки или перезагрузки расписания."""
        try:
            current_mtime = self.schedule_path.stat().st_mtime
            if current_mtime != self._mtime:
                logger.info(f"Обнаружены изменения в {self.schedule_path}. Перезагрузка...")
                with open(self.schedule_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                self._mtime = current_mtime
                logger.info("Расписание успешно перезагружено.")
        except FileNotFoundError:
            logger.error(f"Файл расписания {self.schedule_path} не найден. Кэш не обновлен.")
        except json.JSONDecodeError:
            logger.error(f"Ошибка декодирования JSON в {self.schedule_path}. Используется старый кэш.")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка при чтении расписания: {e}")

    def get_schedule_for_day(self, day_index: int) -> Optional[str]:
        """Возвращает текст расписания для конкретного дня недели."""
        self._load_schedule() # Проверяем обновления перед каждым доступом
        return self._cache.get(str(day_index))