"""全仓测试共用夹具。

SRA 客户端在进程内保留失败冷却与告警节流（见 `app/tools/sra_activity.py`）。这些状态
跨用例存活会让「先失败、后成功」的用例互相污染，也让重试退避把测试拖慢，所以每个用例
开始前复位。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import sra_activity  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_sra_state(monkeypatch):
    sra_activity.reset_failure_state()
    # 真实退避是 0.5s/1s；用例只关心「有没有重试」，不必真的等。
    monkeypatch.setattr(sra_activity, "RETRY_DELAY_SECONDS", 0.0)
    yield
    sra_activity.reset_failure_state()
