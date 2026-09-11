"""独立社区日志；脱敏逻辑沿用 AUTO-MAS，禁用局部变量诊断。"""

import logging
import sys
import traceback
from pathlib import Path

from loguru import logger

from .security import sanitize_log_message


def _sanitize_record(record):
    record["message"] = sanitize_log_message(str(record["message"]))
    record["extra"].setdefault("module", "社区工具")
    record["extra"]["module"] = sanitize_log_message(str(record["extra"]["module"]))
    record["extra"].setdefault("requestId", "-")
    if record["exception"] and record["exception"].type:
        # 保留完整调用位置，但不输出异常对象、源代码行或局部变量中的凭据。
        exception = record["exception"]
        frames = traceback.extract_tb(exception.traceback)
        root = Path(__file__).resolve().parents[2]
        locations = []
        for frame in frames:
            path = Path(frame.filename)
            name = (
                path.relative_to(root).as_posix()
                if path.is_relative_to(root)
                else path.name
            )
            locations.append(f"  {name}:{frame.lineno} in {frame.name}")
        record["message"] += "\nTraceback (调用栈):\n" + "\n".join(locations)
        record["message"] += f"\n{exception.type.__name__}"
    record["exception"] = None


LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {extra[requestId]} | {message}"


logger.remove()
logger.configure(patcher=_sanitize_record)
logger.add(
    sys.stderr,
    diagnose=False,
    backtrace=False,
    format=LOG_FORMAT,
)


def configure_file_logging(directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    return logger.add(
        directory / "community.log",
        diagnose=False,
        backtrace=False,
        rotation="5 MB",
        retention="7 days",
        encoding="utf-8",
        format=LOG_FORMAT,
    )


def intercept_standard_logging() -> None:
    """将 Uvicorn/asyncio 等标准日志送入同一脱敏出口，涵盖启动失败。"""

    class Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logger.bind(module=record.name).opt(exception=record.exc_info).log(
                record.levelname, record.getMessage()
            )

    logging.basicConfig(handlers=[Handler()], level=logging.INFO, force=True)


def get_logger(module_name: str):
    return logger.bind(module=module_name)
