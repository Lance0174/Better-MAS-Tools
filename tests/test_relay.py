"""转发层与执行层单元测试：不访问真实 MAS，不发送真实消息。"""

import asyncio
import time

import pytest
from pydantic import ValidationError

from app.core.relay import relay_executor
from app.core.state import state
from app.models.schema import RelayCommandIn
from app.services.relay import (
    COMMAND_TTL_SECONDS,
    MemoryRelayStore,
    NODE_ONLINE_SECONDS,
    RESULT_RETENTION_SECONDS,
)


def test_relay_command_rejects_unknown_type():
    with pytest.raises(ValidationError):
        RelayCommandIn.model_validate({"type": "shell.exec", "payload": {}})


def test_relay_command_accepts_whitelisted_types():
    for command_type in ("mas.snapshot", "mas.start", "mas.stop", "sign.run"):
        RelayCommandIn.model_validate({"type": command_type, "payload": {}})


@pytest.mark.asyncio
async def test_memory_store_enqueue_take_result_cycle():
    store = MemoryRelayStore()
    command_id = await store.enqueue("mas.snapshot", {})
    command = await store.take_wait("node-a", 0.1)
    assert command is not None and command["id"] == command_id
    assert command["type"] == "mas.snapshot"
    assert command["version"] == 1

    # 已领取的指令不会被重复下发。
    assert await store.take_wait("node-a", 0.1) is None

    await store.submit_result("node-a", command_id, True, {"queues": []}, "")
    status = await store.command_status(command_id)
    assert status["status"] == "done"
    assert status["result"] == {"data": {"queues": []}, "error": ""}


@pytest.mark.asyncio
async def test_memory_store_failed_result_keeps_error():
    store = MemoryRelayStore()
    command_id = await store.enqueue("mas.stop", {"taskId": "t1"})
    await store.take_wait("node-a", 0.1)
    await store.submit_result("node-a", command_id, False, {}, "MAS 未完成该操作")
    status = await store.command_status(command_id)
    assert status["status"] == "failed"
    assert status["result"]["error"] == "MAS 未完成该操作"


@pytest.mark.asyncio
async def test_memory_store_rejects_result_for_unknown_command():
    store = MemoryRelayStore()
    await store.submit_result("node-a", "missing", True, {}, "")
    assert await store.command_status("missing") is None


@pytest.mark.asyncio
async def test_memory_store_take_wait_times_out_on_empty_queue():
    store = MemoryRelayStore()
    assert await store.take_wait("node-a", 0.2) is None
    nodes = await store.nodes()
    assert nodes == [
        {"nodeId": "node-a", "online": True, "lastSeenAt": nodes[0]["lastSeenAt"]}
    ]


@pytest.mark.asyncio
async def test_memory_store_expires_stale_pending_command():
    store = MemoryRelayStore()
    command_id = await store.enqueue("mas.snapshot", {})
    # 白盒：把过期时间拨回 TTL 之外，模拟指令无人领取。
    store._commands[command_id]["expire_at"] = time.time() - COMMAND_TTL_SECONDS - 1
    assert await store.take_wait("node-a", 0.1) is None
    status = await store.command_status(command_id)
    assert status["status"] == "expired"


@pytest.mark.asyncio
async def test_memory_store_sweeps_retention_period():
    store = MemoryRelayStore()
    command_id = await store.enqueue("mas.snapshot", {})
    await store.take_wait("node-a", 0.1)
    await store.submit_result("node-a", command_id, True, {}, "")
    item = store._commands[command_id]
    item["finished_at"] = time.time() - RESULT_RETENTION_SECONDS - 1
    await store.command_status(command_id)
    assert await store.command_status(command_id) is None


@pytest.mark.asyncio
async def test_memory_store_node_online_status():
    store = MemoryRelayStore()
    await store.take_wait("node-a", 0.1)
    assert (await store.nodes())[0]["online"] is True
    store._nodes["node-b"] = time.time() - NODE_ONLINE_SECONDS - 1
    status = {item["nodeId"]: item["online"] for item in await store.nodes()}
    assert status == {"node-a": True, "node-b": False}


@pytest.mark.asyncio
async def test_executor_runs_mas_snapshot(monkeypatch):
    captured = {}

    async def fake_snapshot(base_url):
        captured["base_url"] = base_url
        return {"baseUrl": base_url, "queues": [], "tasks": []}

    monkeypatch.setattr("app.core.relay.mas.snapshot", fake_snapshot)
    data = await relay_executor._execute("mas.snapshot", {})
    assert data["queues"] == []
    assert captured["base_url"] == state.data.settings.MasBaseUrl


@pytest.mark.asyncio
async def test_executor_mas_start_requires_task_id(monkeypatch):
    async def fail_request(*args, **kwargs):
        raise AssertionError("不应发起 MAS 请求")

    monkeypatch.setattr("app.core.relay.mas.request", fail_request)
    with pytest.raises(ValidationError):
        await relay_executor._execute("mas.start", {})


@pytest.mark.asyncio
async def test_executor_mas_start_dispatches_payload(monkeypatch):
    captured = {}

    async def fake_request(base_url, path, *, payload=None):
        captured.update({"path": path, "payload": payload})
        return {"taskId": "task-1", "code": 200}

    monkeypatch.setattr("app.core.relay.mas.request", fake_request)
    data = await relay_executor._execute(
        "mas.start", {"taskId": "task-1", "mode": "CycleRun"}
    )
    assert data == {"taskId": "task-1"}
    assert captured["path"] == "/api/dispatch/start"
    assert captured["payload"] == {"taskId": "task-1", "mode": "CycleRun"}


@pytest.mark.asyncio
async def test_executor_mas_stop_dispatches_payload(monkeypatch):
    captured = {}

    async def fake_request(base_url, path, *, payload=None):
        captured.update({"path": path, "payload": payload})
        return {"code": 200}

    monkeypatch.setattr("app.core.relay.mas.request", fake_request)
    assert await relay_executor._execute("mas.stop", {"taskId": "task-1"}) == {}
    assert captured["path"] == "/api/dispatch/stop"


@pytest.mark.asyncio
async def test_executor_sign_run_reports_busy(monkeypatch):
    from app.tools.community_contract import CommunitySignInProgressError

    async def busy_sign(*, force):
        raise CommunitySignInProgressError("签到正在进行中")

    monkeypatch.setattr("app.core.relay.runtime.sign", busy_sign)
    with pytest.raises(ValueError, match="签到正在进行中"):
        await relay_executor._execute("sign.run", {})


@pytest.mark.asyncio
async def test_executor_sign_run_success(monkeypatch):
    called = {}

    async def ok_sign(*, force):
        called["force"] = force

    monkeypatch.setattr("app.core.relay.runtime.sign", ok_sign)
    data = await relay_executor._execute("sign.run", {})
    assert called["force"] is True
    assert "签到已在本机执行" in data["message"]


@pytest.mark.asyncio
async def test_executor_rejects_unknown_type():
    with pytest.raises(ValueError, match="未知的指令类型"):
        await relay_executor._execute("shell.exec", {})


def test_event_loop_runs_pending_tasks():
    asyncio.new_event_loop().close()
