"""加载项目根目录环境文件；文件值优先于系统环境，空值视为未设置。"""

import os
import re
from pathlib import Path

_ASSIGNMENT = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def load_project_environment(root: Path | None = None) -> None:
    """将项目根目录 `.env` 加载到进程环境，非空文件值覆盖系统值。"""
    directory = root or Path(__file__).resolve().parents[2]
    path = directory / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = _ASSIGNMENT.match(line.strip())
        if not match or match.group(1).startswith("#"):
            continue
        value = _parse_value(match.group(2))
        if value:
            os.environ[match.group(1)] = value
