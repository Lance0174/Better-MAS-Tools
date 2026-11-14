"""已登录账号的角色发现与名称候选不调用便笺或发送真实网络请求。"""

from unittest.mock import AsyncMock

import pytest

from app.api.community import list_account_roles
from app.core import accounts
from app.core.state import CommunityState
from app.models.config import AccountData, SavedState
from app.models.schema import AccountRolesIn
from app.tools.community_activity_roles import (
    CommunityActivityCapability,
    CommunityActivityRole,
    CommunityActivityRoleDiscovery,
)
from app.tools.community_activity_transport import CommunityActivityTransportError

UID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def local_state(monkeypatch):
    state = CommunityState()
    state.data = SavedState(
        accounts={UID: AccountData(Name="示例账号", MiyousheToken="offline-only")}
    )
    state.storage = type("Store", (), {"save_async": AsyncMock()})()
    monkeypatch.setattr(accounts, "state", state)
    return state


@pytest.mark.asyncio
async def test_roles_reuse_saved_session_without_daily_note_requests(
    local_state, monkeypatch
):
    async def discover(provider, **kwargs):
        assert provider.raw_credential == "offline-only"
        assert kwargs["account_uid"] == UID
        return CommunityActivityRoleDiscovery(
            "米游社",
            (CommunityActivityRole("米游社", "原神", "100001", "cn_gf01", "旅行者"),),
            CommunityActivityCapability(reason="部分角色暂未能读取"),
        )

    monkeypatch.setattr(accounts.CommunityActivityProvider, "discover_roles", discover)
    response = await list_account_roles(
        AccountRolesIn(accountId=UID, platform="米游社")
    )
    assert response.status == "partial"
    assert response.data[0].roleName == "旅行者"
    assert response.data[0].server == "cn_gf01"
    assert "offline-only" not in response.model_dump_json()
    local_state.storage.save_async.assert_not_called()


@pytest.mark.asyncio
async def test_unbound_community_does_not_request_or_change_account(
    local_state, monkeypatch
):
    discover = AsyncMock()
    monkeypatch.setattr(accounts.CommunityActivityProvider, "discover_roles", discover)
    with pytest.raises(ValueError, match="先登录"):
        await accounts.discover_roles(UID, "森空岛")
    discover.assert_not_awaited()
    assert local_state.require_account(UID).Name == "示例账号"


@pytest.mark.asyncio
async def test_role_upstream_failure_is_expected_business_error(
    local_state, monkeypatch
):
    monkeypatch.setattr(
        accounts.CommunityActivityProvider,
        "discover_roles",
        AsyncMock(
            side_effect=CommunityActivityTransportError("登录已失效", status="limited")
        ),
    )
    with pytest.raises(ValueError, match="登录已失效"):
        await accounts.discover_roles(UID, "米游社")


@pytest.mark.asyncio
async def test_new_accounts_have_distinct_names_without_renaming_existing(local_state):
    first = await local_state.create_account()
    second = await local_state.create_account()
    assert local_state.require_account(first).Name == "账号 1"
    assert local_state.require_account(second).Name == "账号 2"
    assert local_state.require_account(UID).Name == "示例账号"
