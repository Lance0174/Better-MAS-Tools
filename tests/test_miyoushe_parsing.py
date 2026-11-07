"""米游社 / 米游币协议解析健壮性的离线回归。

覆盖上游字段类型漂移（retcode 字符串、data 为 null、进度字段为 null、数组里混入
非对象元素）时的行为。全部用 httpx.MockTransport 注入假传输层，不产生真实请求。
"""

import httpx
import pytest

from app.services.network import CommunityNetwork, network
from app.tools import miyoushe, miyoushe_bbs

GAME_CFG = miyoushe.GAME_CONFIG["hk4e_cn"]


def _install_transport(monkeypatch, handler) -> None:
    """把社区网络单例换成离线 MockTransport，测试期间不可能发出真实请求。"""

    transport = httpx.MockTransport(handler)

    def client(**options):
        options.pop("proxy", None)
        return CommunityNetwork.client(network, transport=transport, **options)

    monkeypatch.setattr(network, "client", client)


def _json_handler(payload: object, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, request=request)

    return handler


def test_coerce_retcode_accepts_type_drift():
    assert miyoushe._coerce_retcode(0) == 0
    assert miyoushe._coerce_retcode("0") == 0
    assert miyoushe._coerce_retcode(" -5003 ") == -5003
    assert miyoushe._coerce_retcode(1034.0) == 1034
    # bool 是 int 的子类，不能当成业务码
    assert miyoushe._coerce_retcode(True) is None
    assert miyoushe._coerce_retcode(None) is None
    assert miyoushe._coerce_retcode("风控") is None
    assert miyoushe._coerce_retcode(float("inf")) is None


@pytest.mark.asyncio
async def test_get_game_roles_tolerates_null_data(monkeypatch):
    _install_transport(
        monkeypatch, _json_handler({"retcode": "0", "message": "OK", "data": None})
    )

    assert await miyoushe._get_game_roles("ltuid=1; cookie_token=x") == []


@pytest.mark.asyncio
async def test_get_game_roles_skips_non_object_entries(monkeypatch):
    payload = {
        "retcode": 0,
        "data": {
            "list": [
                None,
                "broken",
                {"game_biz": "unknown_biz", "region": "cn_gf01"},
                {
                    "game_biz": "hk4e_cn",
                    "region": "cn_gf01",
                    "game_uid": "100000001",
                    "nickname": "旅行者",
                },
            ]
        },
    }
    _install_transport(monkeypatch, _json_handler(payload))

    roles = await miyoushe._get_game_roles("ltuid=1; cookie_token=x")

    assert [role["game_biz"] for role in roles] == ["hk4e_cn"]


@pytest.mark.asyncio
async def test_get_game_roles_handles_nested_list_with_broken_items(monkeypatch):
    payload = {
        "retcode": 0,
        "data": {
            "list": [
                {
                    "list": [
                        None,
                        {
                            "game_biz": "hkrpg_cn",
                            "region": "prod_gf_cn",
                            "game_uid": "200000002",
                            "nickname": "开拓者",
                        },
                    ]
                },
                None,
                {"list": "broken"},
            ]
        },
    }
    _install_transport(monkeypatch, _json_handler(payload))

    roles = await miyoushe._get_game_roles("ltuid=1; cookie_token=x")

    assert [role["game_biz"] for role in roles] == ["hkrpg_cn"]


@pytest.mark.asyncio
async def test_derive_cookie_token_rejects_null_data(monkeypatch):
    _install_transport(
        monkeypatch, _json_handler({"retcode": 0, "message": "OK", "data": None})
    )

    with pytest.raises(ValueError, match="返回数据格式无效"):
        await miyoushe.derive_miyoushe_cookie_token("v2_stoken", "mid", "100")


@pytest.mark.asyncio
async def test_derive_cookie_token_accepts_string_retcode(monkeypatch):
    _install_transport(
        monkeypatch,
        _json_handler(
            {"retcode": "0", "message": "OK", "data": {"cookie_token": "tok", "uid": 100}}
        ),
    )

    assert await miyoushe.derive_miyoushe_cookie_token("v2_stoken", "mid", "100") == (
        "tok",
        "100",
    )


@pytest.mark.asyncio
async def test_do_sign_treats_string_retcode_as_success(monkeypatch):
    _install_transport(
        monkeypatch,
        _json_handler(
            {"retcode": "0", "message": "OK", "data": {"award": {"name": "原石", "cnt": 20}}}
        ),
    )

    result, _ = await miyoushe._do_sign(
        "ltuid=1; cookie_token=x", GAME_CFG, "cn_gf01", "100000001", "旅行者/旅行者(100000001)"
    )

    assert result["status"] == "成功"
    assert result["reward"] == "原石x20"


@pytest.mark.asyncio
async def test_do_sign_detects_already_signed_with_null_message(monkeypatch):
    _install_transport(
        monkeypatch, _json_handler({"retcode": "-5003", "message": None, "data": None})
    )

    result, _ = await miyoushe._do_sign(
        "ltuid=1; cookie_token=x", GAME_CFG, "cn_gf01", "100000001", "旅行者/旅行者(100000001)"
    )

    assert result["status"] == "已签到"


@pytest.mark.asyncio
async def test_do_sign_reports_failure_with_null_message(monkeypatch):
    _install_transport(
        monkeypatch, _json_handler({"retcode": 10001, "message": None, "data": None})
    )

    result, _ = await miyoushe._do_sign(
        "ltuid=1; cookie_token=x", GAME_CFG, "cn_gf01", "100000001", "旅行者/旅行者(100000001)"
    )

    assert result["status"] == "失败"
    assert "10001" in result["reason"]


@pytest.mark.asyncio
async def test_do_sign_verification_payload_uses_game_biz(monkeypatch):
    _install_transport(
        monkeypatch, _json_handler({"retcode": 0, "data": {"gt": "gt-1", "challenge": "ch-1"}})
    )

    result, _ = await miyoushe._do_sign(
        "ltuid=1; cookie_token=x",
        GAME_CFG,
        "cn_gf01",
        "100000001",
        "旅行者/旅行者(100000001)",
        game_biz="nap_cn",
    )

    assert result["status"] == "风控"
    assert result["_verification"]["gameBiz"] == "nap_cn"


@pytest.mark.asyncio
async def test_do_sign_unknown_game_cfg_does_not_raise(monkeypatch):
    # 不在 GAME_CONFIG 里的配置以前会让 next() 抛 StopIteration → RuntimeError。
    custom = {"name": "自定义游戏", "act_id": "e1", "sign_url": miyoushe.SIGN_URL}
    _install_transport(
        monkeypatch, _json_handler({"retcode": 0, "data": {"gt": "gt-1", "challenge": "ch-1"}})
    )

    result, _ = await miyoushe._do_sign(
        "ltuid=1; cookie_token=x", custom, "cn_gf01", "1", "别名/别名(1)"
    )

    assert result["status"] == "风控"
    assert result["_verification"]["gameBiz"] == ""


def test_mission_remaining_tolerates_null_progress_fields():
    definitions = [
        {"mission_key": "continuous_sign", "threshold": 4},
        {"mission_key": "view_post_0", "threshold": "3"},
    ]
    states = [
        {"mission_key": "continuous_sign", "is_get_award": True, "happened_times": 4},
        {"mission_key": "view_post_0", "is_get_award": False, "happened_times": None},
        None,
        "broken",
    ]

    assert miyoushe_bbs.mission_remaining(definitions, states) == {
        "continuous_sign": 0,
        "view_post_0": 3,
    }


def test_mission_remaining_rejects_null_threshold():
    with pytest.raises(ValueError, match="任务目标异常"):
        miyoushe_bbs.mission_remaining(
            [{"mission_key": "view_post_0", "threshold": None}], []
        )


def test_mission_remaining_rejects_unknown_definitions():
    with pytest.raises(ValueError, match="可识别"):
        miyoushe_bbs.mission_remaining(
            [{"mission_key": "unknown_task", "threshold": 5}, None], []
        )
