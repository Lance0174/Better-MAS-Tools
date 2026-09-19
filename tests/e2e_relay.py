"""转发层/执行层端到端演练：单进程内起转发层与假 MAS 服务，控制端验证全链路。

不访问真实 MAS，不发送真实消息；端口使用本机回环地址，测试结束全部关闭。
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from app.core.relay import relay_executor
from app.core.state import state
from app.main import create_app
from app.services.relay import MemoryRelayStore

HUB_PORT = 37210
FAKE_MAS_PORT = 37310
HUB = f"http://127.0.0.1:{HUB_PORT}"
FAKE_MAS = f"http://127.0.0.1:{FAKE_MAS_PORT}"


def _fake_mas_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/queue/get")
    async def queue_get():
        return {
            "code": 200,
            "data": {"q1": {"Info": {"Name": "测试队列"}}},
            "index": [{"uid": "q1"}],
        }

    @app.get("/api/dispatch/runtime-snapshot")
    async def runtime_snapshot():
        return {
            "code": 200,
            "tasks": [{"taskId": "t1", "mode": "AutoProxy", "stopping": False}],
        }

    @app.post("/api/dispatch/start")
    async def dispatch_start():
        return {"code": 200, "taskId": "t-new"}

    @app.post("/api/dispatch/stop")
    async def dispatch_stop():
        return {"code": 200}

    return app


async def _serve(app: FastAPI, port: int):
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    async with httpx.AsyncClient(trust_env=False, timeout=2) as probe:
        while True:
            try:
                # 任何 HTTP 响应（含 404）都说明端口已监听。
                await probe.get(f"http://127.0.0.1:{port}/healthz")
                break
            except httpx.HTTPError:
                await asyncio.sleep(0.1)
    return server, task


async def _wait_command_done(
    client: httpx.AsyncClient, command_id: str, headers: dict
) -> dict:
    for _ in range(60):
        response = await client.get(
            f"{HUB}/api/relay/commands/{command_id}", headers=headers
        )
        status = response.json()
        if status["commandStatus"] in {"done", "failed", "expired"}:
            return status
        await asyncio.sleep(0.5)
    raise AssertionError("指令在超时内未完成")


async def run_flow(tmp_path) -> None:
    step = 0

    def trace(message: str) -> None:
        nonlocal step
        step += 1
        print(f"[e2e {step}] {message}", flush=True)

    hub_app = create_app(
        data_dir=tmp_path / "hub",
        start_scheduler=False,
        relay_store=MemoryRelayStore(),
    )
    trace("构建转发层应用")
    hub_server, hub_task = await _serve(hub_app, HUB_PORT)
    trace("转发层已监听")
    mas_server, mas_task = await _serve(_fake_mas_app(), FAKE_MAS_PORT)
    trace("假 MAS 已监听")
    executor_task = None
    try:
        # 配置执行层并启动其长轮询循环。
        state.data.settings.RelayEnabled = True
        state.data.settings.CloudBaseUrl = HUB
        state.data.settings.CloudPassword = "演练密码"
        state.data.settings.MasBaseUrl = FAKE_MAS
        executor_task = asyncio.create_task(relay_executor.loop())
        trace("执行层循环已启动")

        # 控制端登录并下发指令。
        async with httpx.AsyncClient(trust_env=False, timeout=40) as client:
            session = (
                await client.get(f"{HUB}/api/session")
            ).json()
            headers = {"x-community-session": session["key"]}
            trace("控制端已取得会话")

            snapshot_id = (
                await client.post(
                    f"{HUB}/api/relay/command",
                    json={"type": "mas.snapshot", "payload": {}},
                    headers=headers,
                )
            ).json()["id"]
            start_id = (
                await client.post(
                    f"{HUB}/api/relay/command",
                    json={"type": "mas.start", "payload": {"taskId": "q1"}},
                    headers=headers,
                )
            ).json()["id"]
            stop_id = (
                await client.post(
                    f"{HUB}/api/relay/command",
                    json={"type": "mas.stop", "payload": {"taskId": "t1"}},
                    headers=headers,
                )
            ).json()["id"]
            trace(f"三条指令已入队：{snapshot_id} {start_id} {stop_id}")

            snapshot = await _wait_command_done(client, snapshot_id, headers)
            assert snapshot["commandStatus"] == "done", snapshot
            assert snapshot["result"]["data"]["queues"][0]["name"] == "测试队列"
            trace("mas.snapshot 结果正确")

            started = await _wait_command_done(client, start_id, headers)
            assert started["commandStatus"] == "done", started
            assert started["result"]["data"]["taskId"] == "t-new"
            trace("mas.start 结果正确")

            stopped = await _wait_command_done(client, stop_id, headers)
            assert stopped["commandStatus"] == "done", stopped
            trace("mas.stop 结果正确")

            nodes = (
                await client.get(f"{HUB}/api/relay/nodes", headers=headers)
            ).json()["data"]
            assert any(item["nodeId"] == relay_executor.node_id for item in nodes)
            trace("节点在线状态正确")
    finally:
        if executor_task is not None:
            executor_task.cancel()
            await asyncio.gather(executor_task, return_exceptions=True)
        hub_server.should_exit = True
        mas_server.should_exit = True
        await asyncio.gather(hub_task, mas_task, return_exceptions=True)
        trace("全部服务已关闭")


@pytest.mark.asyncio
async def test_end_to_end_relay_flow(tmp_path):
    await asyncio.wait_for(run_flow(tmp_path), timeout=90)


if __name__ == "__main__":
    import tempfile

    asyncio.run(run_flow(Path(tempfile.mkdtemp()) / "e2e"))
