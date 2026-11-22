import logging
from utils.settings import settings


def setup_logger() -> logging.Logger:
    """Configures and returns the application logger for console and file output."""
    log = logging.getLogger("meme_bot")
    log.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S"
    )

    # Вывод логов в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Запись предупреждений и ошибок в файл
    file_handler = logging.FileHandler(settings.LOGGING_FILENAME, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    log.addHandler(console_handler)
    log.addHandler(file_handler)
    return log


logger = setup_logger()
