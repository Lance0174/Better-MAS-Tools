"""账号组标识归一与签到成功判据的回归测试。"""

import pytest

from app.core import community_activity
from app.core.state import (
    CommunityState,
    match_account_uid,
    normalize_account_uid,
)
from app.models.config import AccountData, SavedState


class _RecordingStore:
    """只记录落盘的假存储，不接触真实文件。"""

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


def test_normalize_account_uid_accepts_client_forms():
    canonical = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    assert normalize_account_uid(canonical) == canonical
    assert normalize_account_uid(canonical.upper()) == canonical
    assert normalize_account_uid("{" + canonical + "}") == canonical
    assert normalize_account_uid("  " + canonical.upper() + " ") == canonical
    assert normalize_account_uid("not-a-uuid") is None
    assert normalize_account_uid(None) is None


def test_match_account_uid_prefers_exact_then_normalized():
    uid = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    keys = {uid: object(), "legacy-name": object()}
    assert match_account_uid(keys, uid) == uid
    assert match_account_uid(keys, uid.upper()) == uid
    assert match_account_uid(keys, "legacy-name") == "legacy-name"
    assert match_account_uid(keys, "  " + uid.upper() + " ") == uid
    assert match_account_uid(keys, "missing") is None


def test_require_account_accepts_uppercase_uuid(temp_state: CommunityState):
    uid = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    temp_state.data.accounts[uid] = AccountData(Name="主号")

    assert temp_state.require_account(uid.upper()).Name == "主号"
    assert temp_state.require_account("{" + uid + "}").Name == "主号"
    with pytest.raises(ValueError):
        temp_state.require_account("00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_update_account_with_normalized_uid_writes_canonical_key(
    temp_state: CommunityState,
):
    uid = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    temp_state.data.accounts[uid] = AccountData(Name="旧名")

    await temp_state.update_account(uid.upper(), {"Name": "新名"}, reset_date=False)

    assert set(temp_state.data.accounts) == {uid}
    assert temp_state.data.accounts[uid].Name == "新名"


@pytest.mark.asyncio
async def test_delete_account_with_normalized_uid(temp_state: CommunityState):
    uid = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    temp_state.data.accounts[uid] = AccountData(Name="待删")

    await temp_state.delete_account("{" + uid.upper() + "}")

    assert temp_state.data.accounts == {}


class _FakeState:
    """只带 accounts 的假状态，供账号选择逻辑使用。"""

    def __init__(self, accounts: dict[str, object]) -> None:
        self.accounts = accounts


def test_selected_accounts_normalizes_requested_uids(monkeypatch):
    uid = "5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"
    other = "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d"
    fake = _FakeState({uid: object(), other: object()})
    monkeypatch.setattr("app.core.state.state", fake)

    selected = community_activity._selected_accounts([uid.upper()])

    assert [item[0] for item in selected] == [uid]


def test_selected_accounts_rejects_unknown_uid(monkeypatch):
    fake = _FakeState({"5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f": object()})
    monkeypatch.setattr("app.core.state.state", fake)

    with pytest.raises(ValueError):
        community_activity._selected_accounts(["6c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f"])
