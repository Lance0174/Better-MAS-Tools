"""原子写盘：先写同目录临时文件再 replace，中断不会留下半份文件。

多处缓存（资料库索引、活动日历、解包游戏表）原本各写了一份同形实现，改成共用
这一个；放在 utils 里是因为 services 之间互相调用，谁做"提供方"都会引入循环导入。
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["atomic_write_text"]


def atomic_write_text(path: Path, text: str) -> None:
    """把文本原子地写到 path，失败时原文件保持可用。

    临时文件与目标同目录，保证 replace 在同一文件系统内完成；不留残骸。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
