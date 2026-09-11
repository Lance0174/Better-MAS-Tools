"""保存当前运行的诊断记录；完整文件日志由统一日志出口负责滚动写入。"""

import threading
from collections import deque
from pathlib import Path

from app.models.schema import LogEntryInfo


class Diagnostics:
    capacity = 2000

    def __init__(self, directory: Path | None = None):
        self.directory = directory
        self.entries: deque[LogEntryInfo] = deque(maxlen=self.capacity)
        self.lock = threading.Lock()
        self.sequence = 0

    def write(self, message) -> None:
        # Loguru 已完成统一脱敏；仅从 record 取明确字段，不序列化请求或异常对象。
        record = message.record
        with self.lock:
            self.sequence += 1
            self.entries.append(
                LogEntryInfo(
                    id=self.sequence,
                    time=record["time"].isoformat(timespec="milliseconds"),
                    level=record["level"].name,
                    module=record["extra"]["module"],
                    requestId=record["extra"]["requestId"],
                    message=record["message"],
                )
            )

    def snapshot(self) -> list[LogEntryInfo]:
        with self.lock:
            return list(self.entries)

    def export(self) -> str:
        path = self.directory / "community.log" if self.directory else None
        if path and path.is_file():
            # 活跃文件最多约 5 MB；保留文件头与完整记录，历史分卷留在原目录。
            with path.open("rb") as file:
                return file.read(6_000_000).decode("utf-8", errors="replace")
        return "\n".join(
            f"{entry.time} | {entry.level} | {entry.module} | {entry.requestId} | {entry.message}"
            for entry in self.snapshot()
        )
