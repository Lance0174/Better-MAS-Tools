"""独立社区日志；脱敏逻辑沿用 AUTO-MAS，禁用局部变量诊断。"""

import sys
from pathlib import Path

from loguru import logger

from .security import sanitize_log_message


def _sanitize_record(record):
    record["message"] = sanitize_log_message(str(record["message"]))
    record["extra"].setdefault("module", "社区工具")
    return True


logger.remove()
logger.add(
    sys.stderr,
    filter=_sanitize_record,
    diagnose=False,
    backtrace=False,
    format="{time:HH:mm:ss} | {level} | {extra[module]} | {message}",
)


def configure_file_logging(directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    return logger.add(
        directory / "community.log",
        filter=_sanitize_record,
        diagnose=False,
        backtrace=False,
        rotation="5 MB",
        retention=3,
        encoding="utf-8",
    )


def get_logger(module_name: str):
    return logger.bind(module=module_name)
