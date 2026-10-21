"""打包数据文件回归测试：随包分发的非 Python 文件必须被显式收集。

背景：PyInstaller 只跟随 import 收集 .py，Pyodide 侧的 prepare-android 也只
打包 *.py；两者都会漏掉 app/tools/data/endfield_aliases.json。漏掉不会崩，
但资料库检索会静默退化成"只能按索引里的正式名搜索"，昵称/简称/同音字全部
失效——用户看到的是"搜不到"，日志里什么都没有。这里把"必须显式收集"钉住。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "app" / "tools" / "data"
ALIASES = DATA_DIR / "endfield_aliases.json"


def test_aliases_file_exists_and_is_complete():
    """昵称表必须存在且内容可用：空表等同于检索能力失效。"""

    assert ALIASES.is_file(), "缺少昵称表 app/tools/data/endfield_aliases.json"
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))
    assert payload.get("operators"), "昵称表缺少 operators"
    assert payload.get("weapons"), "昵称表缺少 weapons"


def test_windows_build_bundles_tool_data():
    """Windows 打包脚本必须用 --add-data 带上数据目录。"""

    script = (ROOT / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")
    assert "--add-data" in script, "build-desktop.ps1 未使用 --add-data 收集数据文件"
    assert "app/tools/data" in script or "app\\tools\\data" in script, (
        "build-desktop.ps1 的 --add-data 未指向 app/tools/data"
    )


def test_android_build_bundles_tool_data():
    """Android 打包脚本不能只收集 *.py。"""

    script = (ROOT / "scripts" / "prepare-android.py").read_text(encoding="utf-8")
    assert 'rglob("*.json")' in script, (
        "prepare-android.py 只打包了 *.py，数据文件不会进入 Python 源码包"
    )


def test_desktop_verifier_checks_bundled_data():
    """发行校验要能在打包漏文件时失败，而不是等用户发现搜不到。"""

    script = (ROOT / "scripts" / "verify-desktop.py").read_text(encoding="utf-8")
    assert "endfield_aliases.json" in script, (
        "verify-desktop.py 未校验随包数据文件"
    )
