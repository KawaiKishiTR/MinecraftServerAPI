import os
import logging
import logging.config
from pathlib import Path
from typing import ClassVar

from app.config import AppConfig


# Log dosyalarının toplanacağı dizin
ROOT_DIR = Path(os.environ["APP_ROOT_DIR"])
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Renkli Terminal Çıktısı İçin Özel Formatter
# ------------------------------------------------------------------
class BasicFormatter(logging.Formatter):
    """Basit renklendirilmemiş formatter"""

    datefmt:ClassVar[str] = "%H:%M:%S"
    "%H:%M:%S"

    FORMATS = {
        logging.DEBUG: "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s",
        logging.INFO: "[%(asctime)s] [%(levelname)-8s] [%(name)s] - %(message)s",
        logging.WARNING: "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s",
        logging.ERROR: "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s",
        logging.CRITICAL: "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)

class ColoredConsoleFormatter(BasicFormatter):
    """Terminalde seviyelere göre renklendirme yapan formatlayıcı."""
    
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG:      GREY        + BasicFormatter.FORMATS[logging.DEBUG]     + RESET,
        logging.INFO:       BLUE        + BasicFormatter.FORMATS[logging.INFO]      + RESET,
        logging.WARNING:    YELLOW      + BasicFormatter.FORMATS[logging.WARNING]   + RESET,
        logging.ERROR:      RED         + BasicFormatter.FORMATS[logging.ERROR]     + RESET,
        logging.CRITICAL:   BOLD_RED    + BasicFormatter.FORMATS[logging.CRITICAL]  + RESET,
    }


# ------------------------------------------------------------------
# dictConfig Konfigürasyon Sözlüğü
# ------------------------------------------------------------------
console_log_level = "DEBUG" if AppConfig.get_instance().server.debug else "INFO"
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    
    # 1. Biçimlendiriciler (Formatters)
    "formatters": {
        "colored_console": {
            "()": ColoredConsoleFormatter,
        },
        "detailed_file": {
            "format": "%(asctime)s | %(levelname)-8s | process:%(process)d | thread:%(threadName)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "()": BasicFormatter
        },
    },

    # 2. İşleyiciler (Handlers)
    "handlers": {
        # Konsola basan işleyici (Renkli)
        "console": {
            "class": "logging.StreamHandler",
            "level": console_log_level,
            "formatter": "colored_console",
            "stream": "ext://sys.stdout",
        },
        # Boyut bazlı dönen genel log dosyası (Örn: 5 MB olunca yenisini açar, 5 yedek tutar)
        "rotating_app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed_file",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
        # Sadece hata (ERROR & CRITICAL) seviyesini ayrı toplayan dosya
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed_file",
            "filename": LOG_DIR / "errors.log",
            "maxBytes": 10 * 1024 * 1024, # 10 MB
            "backupCount": 3,
            "encoding": "utf-8",
        },
    },

    # 3. Kök Logger (Root Logger)
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "rotating_app_file", "error_file"],
    },

    # 4. Modül Bazlı Özelleştirme (Gürültülü 3. parti kütüphaneleri kısmak için)
    "loggers": {
        "urllib3": {
            "level": "WARNING",
            "propagate": True,
        },
        "asyncio": {
            "level": "WARNING",
            "propagate": True,
        },
    },
}

def setup_logging():
    """Uygulama girişinde bu fonksiyonu bir kez çağırmanız yeterlidir."""
    logging.config.dictConfig(LOGGING_CONFIG)