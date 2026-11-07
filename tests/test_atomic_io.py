"""原子写盘工具的回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.utils.atomic_io import atomic_write_text


def test_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "cache.json"

    atomic_write_text(target, '{"a": 1}')

    assert target.read_text(encoding="utf-8") == '{"a": 1}'


def test_overwrites_existing_file_without_leaving_temp(tmp_path: Path) -> None:
    target = tmp_path / "cache.json"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "新的内容")

    assert target.read_text(encoding="utf-8") == "新的内容"
    assert not (tmp_path / "cache.json.tmp").exists()


def test_failed_replace_keeps_original_and_cleans_temp(tmp_path: Path) -> None:
    # 目标是目录时 replace 必然失败，用来验证 finally 里清理了临时文件。
    target = tmp_path / "occupied"
    target.mkdir()

    with pytest.raises(OSError):
        atomic_write_text(target, "data")

    assert target.is_dir()
    assert not (tmp_path / "occupied.tmp").exists()


def test_serialised_payload_round_trips(tmp_path: Path) -> None:
    import json

    target = tmp_path / "arknights.json"
    payload = {"version": "1.6.3", "activities": [{"name": "危机合约"}]}

    atomic_write_text(target, json.dumps(payload, ensure_ascii=False))

    assert json.loads(target.read_text(encoding="utf-8")) == payload
