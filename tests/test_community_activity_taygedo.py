"""塔吉多（异环）便笺：能力登记、名片请求与解析。"""

import json

import pytest

from app.tools import community_activity_provider as provider_module
from app.tools.community_activity_parser import _parse_taygedo_role_home
from app.tools.community_activity_provider import CommunityActivityProvider
from app.tools.community_activity_roles import (
    ACTIVITY_COMMUNITY_DEFINITIONS,
    TAYGEDO_PARTIAL_ROLES_REASON,
    CommunityActivityRole,
    normalize_taygedo_roles,
)
from app.tools.community_activity_transport import (
    CommunityActivityTransportError,
    build_community_activity_requests,
)


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


def _target():
    return CommunityActivityRole(
        platform="塔吉多", game="异环", role_uid="1001"
    ).to_target(account_uid="uid-1", account_name="测试账号")


def _provider(raw: str = "") -> CommunityActivityProvider:
    credential = json.dumps(
        {"accessToken": "token", "uid": "uid-1", "deviceId": "device-1"}
    )
    return CommunityActivityProvider(platform="塔吉多", raw_credential=raw or credential)


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


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


def test_normalize_taygedo_roles_marks_capability_ready():
    discovery = normalize_taygedo_roles(_roles())

    # 名片接口能给出真实数值，能力必须是 ready，否则上层会直接短路不请求。
    assert discovery.activity_capability.status == "ready"
    assert discovery.activity_capability.reason == ""


def test_normalize_taygedo_roles_accepts_custom_reason():
    discovery = normalize_taygedo_roles(_roles(), reason=TAYGEDO_PARTIAL_ROLES_REASON)
    assert discovery.activity_capability.status == "ready"
    assert discovery.activity_capability.reason == TAYGEDO_PARTIAL_ROLES_REASON


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
    assert discovery.activity_capability.status == "ready"


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

    # 角色没读全时仍然是 ready（能查到的角色照常查），只是把提示挂在能力上。
    assert discovery.activity_capability.status == "ready"
    assert discovery.activity_capability.reason == TAYGEDO_PARTIAL_ROLES_REASON


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


def test_build_taygedo_request_targets_role_home():
    request = build_community_activity_requests(_target())[0]

    assert request.method == "GET"
    assert request.source == "https://bbs-api.tajiduo.com/apihub/awapi/yh/roleHome"
    assert request.query["roleId"] == "1001"
    assert request.auth_scope == "taygedo"
    assert request.signature_profile == "taygedo_role_home"
    headers = request.header_map
    assert headers["Origin"] == "https://webstatic.tajiduo.com"
    assert headers["Referer"] == "https://webstatic.tajiduo.com/"


@pytest.mark.asyncio
async def test_request_taygedo_returns_role_home_payload(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(
        access_token, role_id, *, uid, device_id="", client=None, proxy=None
    ):
        captured.update(
            {
                "access_token": access_token,
                "role_id": role_id,
                "uid": uid,
                "device_id": device_id,
            }
        )
        return {"code": 0, "data": {"level": 45}}

    monkeypatch.setattr("app.tools.taygedo.fetch_role_home", fake_fetch)
    monkeypatch.setattr(
        provider_module.network, "client", lambda **_kwargs: _FakeClient()
    )

    payload = await _provider().request(build_community_activity_requests(_target())[0])

    assert payload["data"] == {"level": 45}
    assert captured == {
        "access_token": "token",
        "role_id": "1001",
        "uid": "uid-1",
        "device_id": "device-1",
    }


@pytest.mark.asyncio
async def test_request_taygedo_requires_access_token():
    provider = CommunityActivityProvider(
        platform="塔吉多", raw_credential=json.dumps({"uid": "uid-1"})
    )
    with pytest.raises(CommunityActivityTransportError, match="访问令牌") as excinfo:
        await provider.request(build_community_activity_requests(_target())[0])
    # 凭据缺失是用户要处理的失败，不能当成"上游没数据"降级。
    assert excinfo.value.status == "failed"


@pytest.mark.asyncio
async def test_request_taygedo_reports_expired_session(monkeypatch):
    async def expired(*_args, **_kwargs):
        raise ValueError("异环名片失败（HTTP 401，code=401）：未登录")

    monkeypatch.setattr("app.tools.taygedo.fetch_role_home", expired)
    monkeypatch.setattr(
        provider_module.network, "client", lambda **_kwargs: _FakeClient()
    )

    with pytest.raises(CommunityActivityTransportError, match="重新登录塔吉多") as excinfo:
        await _provider().request(build_community_activity_requests(_target())[0])
    assert excinfo.value.status == "failed"


@pytest.mark.asyncio
async def test_request_taygedo_keeps_business_error_as_unavailable(monkeypatch):
    async def refused(*_args, **_kwargs):
        raise ValueError("异环名片失败（code=500）：服务繁忙")

    monkeypatch.setattr("app.tools.taygedo.fetch_role_home", refused)
    monkeypatch.setattr(
        provider_module.network, "client", lambda **_kwargs: _FakeClient()
    )

    with pytest.raises(CommunityActivityTransportError) as excinfo:
        await _provider().request(build_community_activity_requests(_target())[0])
    assert excinfo.value.status == "unavailable"
    assert "服务繁忙" in str(excinfo.value)


_ROLE_HOME_PAYLOAD = {
    "code": 0,
    "data": {
        "level": 45,
        "worldLevel": 3,
        "tycoonLevel": 12,
        "roleloginDays": 30,
        "characters": [{"id": 1}, {"id": 2}],
        "staminaValue": 100,
        "staminaMaxValue": 240,
        "citystaminaValue": 20,
        "citystaminaMaxValue": 100,
        "dayvalue": 60,
        "weekcopiesremainCnt": 1,
    },
}


def test_parse_role_home_builds_snapshot():
    snapshot = _parse_taygedo_role_home(
        _ROLE_HOME_PAYLOAD,
        "uid-1",
        "测试账号",
        {"name": "角色A", "roleId": "1001"},
    )

    assert snapshot.status == "success"
    assert snapshot.platform == "塔吉多"
    assert snapshot.game == "异环"
    assert snapshot.role_name == "角色A"
    assert snapshot.role_uid == "1001"
    assert snapshot.source == "/apihub/awapi/yh/roleHome"
    assert {
        (resource["name"], resource["current"], resource["target"])
        for resource in snapshot.resources
    } == {("本性像素", 100, 240), ("都市活力", 20, 100)}

    tasks = {task["name"]: task for task in snapshot.tasks}
    assert tasks["活跃度"]["completed"] == 60
    assert tasks["活跃度"]["target"] == 100
    assert tasks["活跃度"]["period"] == "daily"
    # 周本次数按周重置，不能混进每日活跃度的分母。
    assert tasks["周本次数"]["period"] == "weekly"
    assert (snapshot.completed, snapshot.target) == (60, 100)

    # 名片没有倒计时，说明里必须写清楚原因，而不是编一个时间。
    assert "官方名片接口不含恢复倒计时与每日任务明细" in snapshot.reason
    assert "等级45" in snapshot.reason


def test_parse_role_home_keeps_zero_values():
    payload = {
        "code": 0,
        "data": {"staminaValue": 0, "staminaMaxValue": 240, "dayvalue": 0},
    }
    snapshot = _parse_taygedo_role_home(payload, "uid-1", "测试账号", None)

    # 0 是真实数值，不能当缺字段丢掉。
    assert snapshot.status == "success"
    assert [(resource["name"], resource["current"]) for resource in snapshot.resources] == [
        ("本性像素", 0)
    ]
    assert snapshot.completed == 0
    assert snapshot.target == 100


def test_parse_role_home_marks_unavailable_without_fields():
    snapshot = _parse_taygedo_role_home({"code": 0, "data": {}}, "uid-1", "测试账号", None)

    assert snapshot.status == "unavailable"
    assert "异环名片未返回可识别的资源或活跃度字段" == snapshot.reason
