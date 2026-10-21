"""塔吉多（异环）便笺通道：只展示角色信息，不发资源便笺请求。"""

import json

import pytest

from app.tools import community_activity_roles as roles_module
from app.tools.community_activity_provider import CommunityActivityProvider
from app.tools.community_activity_roles import (
    ACTIVITY_COMMUNITY_DEFINITIONS,
    TAYGEDO_NOTES_UNAVAILABLE_REASON,
    normalize_taygedo_roles,
)
from app.tools.community_activity_transport import CommunityActivityTransportError


def _roles() -> list[dict[str, str]]:
    return [
        {"gameId": "1289", "gameName": "异环", "roleId": "1001", "roleName": "角色A"},
        {"gameId": "1289", "gameName": "异环", "roleId": "1002", "roleName": "角色B"},
        # 幻塔角色不属于本次登记的便笺游戏。
        {"gameId": "1256", "gameName": "幻塔", "roleId": "2001", "roleName": "角色C"},
        # 同一角色重复出现时只保留一条。
        {"gameId": "1289", "gameName": "异环", "roleId": "1001", "roleName": "角色A"},
        {"gameId": "1289", "gameName": "异环", "roleId": "", "roleName": "缺 ID"},
    ]


def test_taygedo_is_registered_for_nte_only():
    definitions = {
        definition.platform: definition.games
        for definition in ACTIVITY_COMMUNITY_DEFINITIONS
    }
    assert definitions["塔吉多"] == ("异环",)


def test_normalize_taygedo_roles_keeps_only_nte_roles():
    discovery = normalize_taygedo_roles(_roles())

    assert discovery.platform == "塔吉多"
    assert [role.role_uid for role in discovery.roles] == ["1001", "1002"]
    assert {role.game for role in discovery.roles} == {"异环"}
    assert discovery.roles[0].role_name == "角色A"


def test_normalize_taygedo_roles_marks_capability_limited():
    discovery = normalize_taygedo_roles(_roles())

    # 塔吉多没有资源便笺接口，能力必须是 limited，否则上层会去请求不存在的端点。
    assert discovery.activity_capability.status == "limited"
    assert discovery.activity_capability.reason == TAYGEDO_NOTES_UNAVAILABLE_REASON


def test_normalize_taygedo_roles_accepts_custom_reason():
    discovery = normalize_taygedo_roles(_roles(), reason="自定义说明")
    assert discovery.activity_capability.reason == "自定义说明"


def _provider(raw: str = "") -> CommunityActivityProvider:
    credential = json.dumps(
        {"accessToken": "token", "uid": "uid-1", "deviceId": "device-1"}
    )
    return CommunityActivityProvider(platform="塔吉多", raw_credential=raw or credential)


@pytest.mark.asyncio
async def test_discover_taygedo_roles_uses_role_cards(monkeypatch):
    captured = {}

    async def fake_roles(access_token, uid, device_id, *, proxy):
        captured.update(
            {"access_token": access_token, "uid": uid, "device_id": device_id}
        )
        return _roles(), True

    monkeypatch.setattr(
        "app.tools.taygedo._get_taygedo_game_roles_with_status", fake_roles
    )
    discovery = await _provider().discover_roles(
        account_uid="uid-1", account_name="测试账号"
    )

    assert captured == {
        "access_token": "token",
        "uid": "uid-1",
        "device_id": "device-1",
    }
    assert [role.role_uid for role in discovery.roles] == ["1001", "1002"]
    assert discovery.activity_capability.status == "limited"


@pytest.mark.asyncio
async def test_discover_taygedo_roles_flags_partial_failure(monkeypatch):
    async def partial_roles(*_args, **_kwargs):
        return _roles(), False

    monkeypatch.setattr(
        "app.tools.taygedo._get_taygedo_game_roles_with_status", partial_roles
    )
    discovery = await _provider().discover_roles(
        account_uid="uid-1", account_name="测试账号"
    )

    assert "部分角色读取失败" in discovery.activity_capability.reason


@pytest.mark.asyncio
async def test_discover_taygedo_roles_requires_access_token():
    provider = CommunityActivityProvider(
        platform="塔吉多", raw_credential=json.dumps({"refreshToken": "only-refresh"})
    )
    with pytest.raises(ValueError, match="访问令牌"):
        await provider.discover_roles(account_uid="uid-1", account_name="测试账号")


@pytest.mark.asyncio
async def test_discover_taygedo_roles_reports_expired_session(monkeypatch):
    async def expired(*_args, **_kwargs):
        raise ValueError("塔吉多角色卡失败：登录状态已失效（HTTP 401）")

    monkeypatch.setattr(
        "app.tools.taygedo._taygedo_reason_is_auth_failure", lambda _reason: True
    )
    monkeypatch.setattr(
        "app.tools.taygedo._get_taygedo_game_roles_with_status", expired
    )
    with pytest.raises(CommunityActivityTransportError, match="重新登录塔吉多"):
        await _provider().discover_roles(account_uid="uid-1", account_name="测试账号")


@pytest.mark.asyncio
async def test_taygedo_resource_request_is_rejected(monkeypatch):
    """即使有人误把塔吉多当普通平台调用，也只能得到明确错误。"""

    from app.tools.community_activity_transport import CommunityActivityRequest

    request = CommunityActivityRequest(
        target=roles_module.CommunityActivityRole(
            platform="塔吉多", game="异环", role_uid="1001"
        ).to_target(account_uid="uid-1", account_name="测试账号"),
        source="https://bbs-api.tajiduo.com/apihub/api/getGameRecordCard",
        method="GET",
        auth_scope="taygedo",
        signature_profile="taygedo_widget",
    )
    with pytest.raises(ValueError, match="未公开资源便笺"):
        await _provider().request(request)
