"""库街区鸣潮结晶波片便笺离线测试：固定 JSON 样本，不访问真实网络。"""

from __future__ import annotations

import time
from collections.abc import Mapping

import httpx
import pytest

from app.tools.community_activity_parser import (
    ACTIVITY_GAME_DEFINITIONS,
    parse_activity_snapshot,
)
from app.tools.community_activity_roles import normalize_kuro_roles
from app.tools.community_activity_transport import (
    CommunityActivityTarget,
    build_community_activity_requests,
)
from app.tools.kuro import (
    WAVES_SERVER_TIME_TOLERANCE_SECONDS,
    parse_kuro_waves_widget,
)

# 已确认的鸣潮小组件响应形状（值全部为离线编造，不含任何真实角色或凭据）。
SERVER_TIME = 1_760_000_000
WAVES_SAMPLE = {
    "code": 200,
    "msg": "OK",
    "data": {
        "serverTime": SERVER_TIME,
        "energyData": {
            "cur": 120,
            "total": 240,
            "refreshTimeStamp": SERVER_TIME + 3_600,
        },
    },
}


def _target() -> CommunityActivityTarget:
    return CommunityActivityTarget(
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
        role_uid="role-1",
        server="server-1",
        role_name="漂泊者",
    )


# ==================== 纯解析函数 ====================


def test_parse_widget_reads_confirmed_fields():
    parsed = parse_kuro_waves_widget(WAVES_SAMPLE, local_timestamp=SERVER_TIME)

    assert parsed["current"] == 120
    assert parsed["total"] == 240
    assert parsed["refresh_time"] == SERVER_TIME + 3_600
    assert parsed["server_time"] == SERVER_TIME
    assert parsed["clock_skew"] == 0
    assert parsed["server_time_corrected"] is False
    assert parsed["reason"] == ""


def test_parse_widget_accepts_string_numbers():
    payload = {
        "data": {
            "serverTime": str(SERVER_TIME),
            "energyData": {"cur": "12", "total": "240", "refreshTimeStamp": "1760003600"},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["current"] == 12
    assert parsed["total"] == 240
    assert parsed["refresh_time"] == 1_760_003_600


@pytest.mark.parametrize("sentinel", [-1, 0])
def test_parse_widget_treats_non_positive_refresh_timestamp_as_no_countdown(sentinel):
    """真实响应核对（2026-10-16）：体力已满时上游返回 refreshTimeStamp=0。

    0 与负数都是"无需刷新"的哨兵，不是时间戳；解析结果必须给出
    refresh_time=None 且 refresh_pending=False，否则会显示荒谬的倒计时。
    """

    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": 240, "total": 240, "refreshTimeStamp": sentinel},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["refresh_time"] is None
    assert parsed["refresh_pending"] is False
    assert parsed["reason"] == ""


def test_sentinel_is_not_shifted_by_clock_correction():
    """哨兵必须在时间纠正之前判定。

    实测库洛服务器时间可偏差数百天；若先纠正再判定，0 会被平移到本机
    时间轴上，变成"1971 年回满"的假倒计时（修复前就是这个表现）。
    """

    local = SERVER_TIME + 500 * 86400  # 与服务器时间相差约 500 天
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": 240, "total": 240, "refreshTimeStamp": 0},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=local)

    assert parsed["server_time_corrected"] is True
    assert parsed["refresh_time"] is None
    assert parsed["refresh_pending"] is False


def test_shifted_refresh_time_in_the_past_drops_the_countdown():
    """真实时间戳在纠正后若已落到过去，不应再显示倒计时。

    平移后 refresh_time <= 本地现在，说明按本地时间轴它已经该回满了；
    此时保留一个过去的时间戳会让前端一直显示 00:00，改为不给倒计时。
    """

    local = SERVER_TIME + 7_200  # 本地比服务器时间晚 2 小时
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {
                "cur": 100,
                "total": 240,
                # 服务器时间轴上 1 小时前就该回满；平移后仍在本地时间的过去。
                "refreshTimeStamp": SERVER_TIME - 3_600,
            },
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=local)

    assert parsed["refresh_pending"] is True  # 上游给的是真实时间戳
    assert parsed["refresh_time"] is None  # 但平移后已过期，不显示倒计时


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "not json",
        {},
        {"data": None},
        {"data": []},
    ],
)
def test_parse_widget_never_raises_on_broken_payload(payload):
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["current"] is None
    assert parsed["total"] is None
    assert parsed["refresh_time"] is None
    assert parsed["server_time"] is None
    assert parsed["server_time_corrected"] is False
    assert isinstance(parsed["reason"], str) and parsed["reason"]


def test_parse_widget_reports_missing_fields_readably():
    parsed = parse_kuro_waves_widget({"data": {"serverTime": SERVER_TIME}}, local_timestamp=SERVER_TIME)

    assert parsed["current"] is None
    assert parsed["total"] is None
    assert parsed["refresh_time"] is None
    assert "energyData.cur" in parsed["reason"]
    assert "energyData.total" in parsed["reason"]
    assert "energyData.refreshTimeStamp" in parsed["reason"]


def test_parse_widget_reports_missing_single_field():
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": 5, "refreshTimeStamp": SERVER_TIME + 60},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["current"] == 5
    assert parsed["total"] is None
    assert "energyData.total" in parsed["reason"]


def test_parse_widget_falls_back_to_action_data_with_note():
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "actionData": {"cur": 7, "total": 240, "refreshTimeStamp": SERVER_TIME + 60},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["current"] == 7
    assert parsed["total"] == 240
    assert "actionData" in parsed["reason"]


def test_parse_widget_ignores_boolean_values():
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": True, "total": False, "refreshTimeStamp": None},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["current"] is None
    assert parsed["total"] is None
    assert parsed["refresh_time"] is None


# ==================== 服务器时间纠正 ====================


def test_clock_skew_within_tolerance_is_kept():
    local = SERVER_TIME + WAVES_SERVER_TIME_TOLERANCE_SECONDS
    parsed = parse_kuro_waves_widget(WAVES_SAMPLE, local_timestamp=local)

    assert parsed["clock_skew"] == WAVES_SERVER_TIME_TOLERANCE_SECONDS
    assert parsed["server_time_corrected"] is False
    assert parsed["server_time"] == SERVER_TIME
    assert parsed["refresh_time"] == SERVER_TIME + 3_600


def test_clock_skew_beyond_tolerance_shifts_refresh_time_forward():
    skew = WAVES_SERVER_TIME_TOLERANCE_SECONDS + 1
    local = SERVER_TIME + skew
    parsed = parse_kuro_waves_widget(WAVES_SAMPLE, local_timestamp=local)

    assert parsed["server_time_corrected"] is True
    assert parsed["clock_skew"] == skew
    assert parsed["server_time"] == local
    # 回满时间平移同样的偏差，相对倒计时保持不变。
    assert parsed["refresh_time"] == SERVER_TIME + 3_600 + skew
    assert parsed["refresh_time"] - parsed["server_time"] == 3_600
    assert "纠正" in parsed["reason"]


def test_clock_skew_beyond_tolerance_shifts_refresh_time_backward():
    skew = -(WAVES_SERVER_TIME_TOLERANCE_SECONDS + 1)
    local = SERVER_TIME + skew
    parsed = parse_kuro_waves_widget(WAVES_SAMPLE, local_timestamp=local)

    assert parsed["server_time_corrected"] is True
    assert parsed["clock_skew"] == skew
    assert parsed["refresh_time"] == SERVER_TIME + 3_600 + skew
    assert parsed["refresh_time"] - parsed["server_time"] == 3_600


def test_clock_skew_never_returns_negative_refresh_time():
    # 本地时钟远落后于上游时，平移后的回满时间戳会落到过去。
    # 既不能变成负数，也不该硬夹成 0 —— 后者会让界面断言"即将回满"，
    # 而实际上游给的是真实时间戳、只是已过期，真实剩余量无从得知。
    payload = {
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": 1, "total": 240, "refreshTimeStamp": 50},
        }
    }
    parsed = parse_kuro_waves_widget(payload, local_timestamp=100)

    assert parsed["server_time_corrected"] is True
    assert parsed["refresh_pending"] is True
    assert parsed["refresh_time"] is None


def test_missing_server_time_uses_local_reference():
    payload = {"data": {"energyData": {"cur": 1, "total": 240, "refreshTimeStamp": None}}}
    parsed = parse_kuro_waves_widget(payload, local_timestamp=SERVER_TIME)

    assert parsed["server_time"] == SERVER_TIME
    assert parsed["server_time_corrected"] is False
    assert "serverTime" in parsed["reason"]


def test_missing_local_reference_keeps_upstream_clock():
    parsed = parse_kuro_waves_widget(WAVES_SAMPLE)

    assert parsed["server_time"] == SERVER_TIME
    assert parsed["clock_skew"] is None
    assert parsed["server_time_corrected"] is False


# ==================== 便笺快照 ====================


def test_snapshot_exposes_waves_resource_with_recovery_status():
    snapshot = parse_activity_snapshot(
        WAVES_SAMPLE,
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
        role={"name": "漂泊者", "roleId": "role-1", "serverName": "server-1"},
    )

    assert snapshot.status == "success"
    assert snapshot.platform == "库街区"
    assert snapshot.game == "鸣潮"
    assert snapshot.source == "/gamer/widget/game3/getData"
    assert snapshot.tasks == ()
    assert len(snapshot.resources) == 1

    resource = snapshot.resources[0]
    assert resource["name"] == "结晶波片"
    assert resource["current"] == 120
    assert resource["target"] == 240
    assert resource["status"].endswith("后回满")
    assert snapshot.role_uid == "role-1"
    assert snapshot.role_name == "漂泊者"
    assert snapshot.server == "server-1"


def test_snapshot_marks_full_stamina():
    payload = {
        "code": 200,
        "data": {
            "serverTime": SERVER_TIME,
            "energyData": {"cur": 240, "total": 240, "refreshTimeStamp": -1},
        },
    }
    snapshot = parse_activity_snapshot(
        payload,
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
    )

    assert snapshot.status == "success"
    assert snapshot.resources[0]["status"] == "已满"


def test_snapshot_surfaces_missing_fields_as_unavailable():
    snapshot = parse_activity_snapshot(
        {"code": 200, "data": {"serverTime": SERVER_TIME}},
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
    )

    assert snapshot.status == "unavailable"
    assert snapshot.resources == ()
    assert "energyData" in snapshot.reason


@pytest.mark.parametrize(
    ("code", "expected"),
    [(220, "limited"), (1513, "limited"), (1001, "unavailable")],
)
def test_snapshot_maps_kuro_business_codes(code, expected):
    snapshot = parse_activity_snapshot(
        {"code": code, "msg": "失败"},
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
    )

    assert snapshot.status == expected
    assert snapshot.reason


def test_snapshot_explains_corrected_server_time():
    skewed = WAVES_SERVER_TIME_TOLERANCE_SECONDS + 30
    sample = {
        "code": 200,
        "data": {
            "serverTime": int(time.time()) - skewed,
            "energyData": {
                "cur": 10,
                "total": 240,
                "refreshTimeStamp": int(time.time()) + 600,
            },
        },
    }
    snapshot = parse_activity_snapshot(
        sample,
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
    )

    assert snapshot.status == "success"
    assert "纠正" in snapshot.reason


def test_waves_definition_is_registered():
    match = [
        definition
        for definition in ACTIVITY_GAME_DEFINITIONS
        if definition.platform == "库街区" and definition.game == "鸣潮"
    ]

    assert len(match) == 1
    assert match[0].parser is not None
    assert match[0].source == "/gamer/widget/game3/getData"


# ==================== 请求构造 ====================


def test_build_request_targets_waves_widget():
    requests = build_community_activity_requests(_target())

    assert len(requests) == 1
    request = requests[0]
    assert request.source == "https://api.kurobbs.com/gamer/widget/game3/getData"
    assert request.method == "POST"
    assert request.form_data == {
        "gameId": "3",
        "roleId": "role-1",
        "serverId": "server-1",
        "type": "2",
        "sizeType": "1",
    }
    assert request.auth_scope == "kuro"
    assert request.signature_profile == "kuro_widget"


def test_build_request_headers_match_kuro_game_headers():
    from app.tools.kuro import GAME_HEADERS

    request = build_community_activity_requests(_target())[0]
    headers = request.header_map

    assert headers["Origin"] == GAME_HEADERS["Origin"]
    assert headers["source"] == "android"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert headers["User-Agent"] == GAME_HEADERS["User-Agent"]
    # 认证与设备字段只能由 provider 执行时注入，规格本身必须保持脱敏。
    assert "token" not in headers
    assert "devcode" not in headers
    assert "distinct_id" not in headers


def test_build_request_requires_server():
    target = CommunityActivityTarget(
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="鸣潮",
        role_uid="role-1",
    )

    with pytest.raises(ValueError):
        build_community_activity_requests(target)


def test_build_request_rejects_unsupported_kuro_game():
    target = CommunityActivityTarget(
        account_uid="uid-1",
        account_name="测试账号",
        platform="库街区",
        game="战双帕弥什",
        role_uid="role-1",
        server="server-1",
    )

    with pytest.raises(ValueError):
        build_community_activity_requests(target)


# ==================== provider 分支 ====================


class _StubResponse:
    def __init__(self, payload: Mapping[str, object], status_code: int = 200):
        self._payload = dict(payload)
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300

    def json(self) -> Mapping[str, object]:
        return self._payload


def test_kuro_provider_serializes_post_form(monkeypatch):
    """provider 分支必须发出 POST 表单，并在执行时注入认证头。"""

    from app.tools import community_activity_provider as provider_module

    captured: dict[str, object] = {}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, url, **options):
            captured["url"] = url
            captured.update(options)
            return _StubResponse(WAVES_SAMPLE)

    monkeypatch.setattr(
        provider_module,
        "network",
        type("N", (), {"client": staticmethod(lambda **_kw: _Client())}),
    )

    provider = provider_module.CommunityActivityProvider(
        platform="库街区",
        raw_credential='{"token":"offline-token","userId":"1"}',
    )
    request = build_community_activity_requests(_target())[0]
    payload = _run(provider.request(request))

    assert captured["url"] == request.source
    assert captured["data"] == request.form_data
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["token"] == "offline-token"
    assert headers["devcode"]
    assert "distinct_id" not in headers or headers["distinct_id"]
    assert payload == WAVES_SAMPLE


def test_kuro_provider_reports_auth_failure_as_limited(monkeypatch):
    from app.tools import community_activity_provider as provider_module

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return _StubResponse({"code": 220, "msg": "登录已过期"})

    monkeypatch.setattr(
        provider_module,
        "network",
        type("N", (), {"client": staticmethod(lambda **_kw: _Client())}),
    )

    provider = provider_module.CommunityActivityProvider(
        platform="库街区",
        raw_credential='{"token":"offline-token"}',
    )
    request = build_community_activity_requests(_target())[0]

    with pytest.raises(provider_module.CommunityActivityTransportError) as error:
        _run(provider.request(request))

    assert error.value.status == "limited"
    assert "offline-token" not in error.value.reason


def test_kuro_provider_maps_network_error(monkeypatch):
    from app.tools import community_activity_provider as provider_module

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        provider_module,
        "network",
        type("N", (), {"client": staticmethod(lambda **_kw: _Client())}),
    )

    provider = provider_module.CommunityActivityProvider(
        platform="库街区",
        raw_credential='{"token":"offline-token"}',
    )
    request = build_community_activity_requests(_target())[0]

    with pytest.raises(provider_module.CommunityActivityTransportError) as error:
        _run(provider.request(request))

    assert error.value.status == "failed"


def test_build_requester_accepts_kuro_platform():
    from app.tools.community_activity_provider import (
        build_community_activity_requester,
    )

    requester = build_community_activity_requester("库街区", '{"token":"offline"}')

    assert callable(requester)


# ==================== 角色发现 ====================


def test_normalize_kuro_roles_reads_waves_binding():
    payload = {
        "code": 200,
        "data": [
            {
                "gameId": "3",
                "roleId": "role-1",
                "serverId": "server-1",
                "roleName": "漂泊者",
                "serverName": "亚服",
            }
        ],
    }
    discovery = normalize_kuro_roles(payload, game_id="3")

    assert discovery.platform == "库街区"
    assert len(discovery.roles) == 1
    role = discovery.roles[0]
    assert role.game == "鸣潮"
    assert role.role_uid == "role-1"
    assert role.server == "server-1"
    assert role.role_name == "漂泊者"


def test_normalize_kuro_roles_ignores_other_games():
    payload = {"data": [{"gameId": "2", "roleId": "pns-1", "serverId": "1"}]}

    assert normalize_kuro_roles(payload, game_id="3").roles == ()


def test_normalize_kuro_roles_returns_empty_without_binding():
    assert normalize_kuro_roles({"data": []}, game_id="3").roles == ()
    assert normalize_kuro_roles({}, game_id="3").roles == ()


def test_normalize_kuro_roles_deduplicates_roles():
    payload = {
        "data": [
            {"gameId": "3", "roleId": "role-1", "serverId": "server-1"},
            {"gameId": "3", "roleId": "role-1", "serverId": "server-1"},
        ]
    }

    assert len(normalize_kuro_roles(payload, game_id="3").roles) == 1


# ==================== 未绑定分支 ====================


def test_unbound_kuro_account_reports_empty_snapshot(monkeypatch):
    """凭据未绑定鸣潮角色时给出可读状态，而不是抛错。"""

    import app.core.community_activity as core_module
    from app.core import state as state_module
    from app.tools.community_activity_provider import CommunityActivityProvider
    from app.tools.community_activity_roles import CommunityActivityRoleDiscovery

    async def _discover(self, *, account_uid, account_name):
        return CommunityActivityRoleDiscovery("库街区")

    monkeypatch.setattr(
        CommunityActivityProvider, "discover_roles", _discover, raising=True
    )
    # 账号对象只需满足 Enabled/Name 读取；凭据读取用桩替换，不触碰真实配置。
    monkeypatch.setattr(
        core_module,
        "_selected_accounts",
        lambda _ids: (("uid-1", object()),),
    )
    monkeypatch.setattr(
        core_module,
        "_account_value",
        lambda _account, name, default="": (
            True if name == "Enabled" else "测试账号" if name == "Name" else default
        ),
    )
    monkeypatch.setattr(
        state_module, "state", type("S", (), {"proxy": None})(), raising=False
    )
    monkeypatch.setattr(
        "app.tools.community_sign_provider.read_community_token",
        lambda _account, _field: '{"token":"offline-token"}',
    )

    snapshots = _run(
        core_module.collect_configured_community_activity(("uid-1",))
    )

    waves = [item for item in snapshots if item.platform == "库街区"]
    assert len(waves) == 1
    assert waves[0].game == "鸣潮"
    assert waves[0].status == "empty"
    assert waves[0].reason == "未发现已绑定角色"


def _run(coroutine):
    """在同步测试里驱动协程，不启动事件循环外的真实 IO。"""

    import asyncio

    return asyncio.run(coroutine)
