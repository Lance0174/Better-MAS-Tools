"""持久状态写入语义测试：空变更不写盘、临时状态不篡改全局代理。"""

import pytest

from app.core.state import CommunityState
from app.core.state import state as global_state
from app.models.config import SavedState, SettingsData
from app.services.network import network


class _RecordingStore:
    """记录落盘次数的假存储；不接触真实文件。"""

    def __init__(self) -> None:
        self.saves: list[SavedState] = []

    async def save_async(self, candidate: SavedState) -> None:
        self.saves.append(candidate)


@pytest.fixture
def temp_state() -> CommunityState:
    candidate = CommunityState()
    candidate.storage = _RecordingStore()
    candidate.data = SavedState()
    return candidate


@pytest.mark.asyncio
async def test_mutate_skips_write_when_nothing_changed(temp_state: CommunityState):
    await temp_state.mutate(lambda _candidate: None)

    assert temp_state.storage.saves == []
    assert temp_state.revision == 0


@pytest.mark.asyncio
async def test_forced_mutate_still_writes_for_commit_path(temp_state: CommunityState):
    await temp_state.mutate(lambda _candidate: None, force=True)

    assert len(temp_state.storage.saves) == 1
    assert temp_state.revision == 1


@pytest.mark.asyncio
async def test_mutate_publishes_proxy_only_for_global_state(
    temp_state: CommunityState, monkeypatch
):
    monkeypatch.setattr(network, "proxy", "http://127.0.0.1:7890")
    # 云端同步构造的临时状态 Proxy 为空；它不能把本进程的代理清掉。
    await temp_state.mutate(
        lambda candidate: setattr(
            candidate, "settings", SettingsData(Proxy="")
        )
    )
    assert network.proxy == "http://127.0.0.1:7890"

    monkeypatch.setattr(global_state, "storage", _RecordingStore())
    monkeypatch.setattr(global_state, "data", SavedState())
    await global_state.mutate(
        lambda candidate: setattr(
            candidate, "settings", SettingsData(Proxy="http://10.0.0.1:1080")
        )
    )
    assert network.proxy == "http://10.0.0.1:1080"
