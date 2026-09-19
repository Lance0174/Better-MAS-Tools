"""转发层 HTTP 契约：仅在注入 relay_store 的部署形态可用。

Cloudflare Worker（entry.py 注入 DurableRelayStore）与本地演练
（COMMUNITY_RELAY_HUB=1 注入 MemoryRelayStore）会启用；普通本地后端
不注入，端点返回明确错误。认证沿用 local_session 中间件：控制端用
浏览器会话，执行层用密码换取的会话 key。
"""

from fastapi import APIRouter, Request

from app.models.schema import (
    OutBase,
    RelayCommandAcceptedOut,
    RelayCommandIn,
    RelayCommandStatusOut,
    RelayNodesOut,
    RelayPollIn,
    RelayPollOut,
    RelayResultIn,
)
from app.services.relay import POLL_HOLD_SECONDS, RelayStore

router = APIRouter(prefix="/api/relay", tags=["Relay"])


def _store(request: Request) -> RelayStore:
    store = getattr(request.app.state, "relay_store", None)
    if store is None:
        raise ValueError("当前后端未启用转发服务，请在云端后端操作")
    return store


@router.post(
    "/command", response_model=RelayCommandAcceptedOut, operation_id="relayCommand"
)
async def relay_command(body: RelayCommandIn, request: Request) -> RelayCommandAcceptedOut:
    command_id = await _store(request).enqueue(body.type, body.payload)
    return RelayCommandAcceptedOut(id=command_id, message="指令已进入转发队列")


@router.post("/poll", response_model=RelayPollOut, operation_id="relayPoll")
async def relay_poll(body: RelayPollIn, request: Request) -> RelayPollOut:
    command = await _store(request).take_wait(body.nodeId, POLL_HOLD_SECONDS)
    return RelayPollOut(data=command)


@router.post("/result", response_model=OutBase, operation_id="relayResult")
async def relay_result(body: RelayResultIn, request: Request) -> OutBase:
    await _store(request).submit_result(
        body.nodeId, body.commandId, body.ok, body.data, body.error
    )
    return OutBase(message="结果已记录")


@router.get("/nodes", response_model=RelayNodesOut, operation_id="relayNodes")
async def relay_nodes(request: Request) -> RelayNodesOut:
    return RelayNodesOut(data=await _store(request).nodes())


@router.get(
    "/commands/{command_id}",
    response_model=RelayCommandStatusOut,
    operation_id="relayCommandStatus",
)
async def relay_command_status(command_id: str, request: Request) -> RelayCommandStatusOut:
    status = await _store(request).command_status(command_id)
    if status is None:
        raise ValueError("指令不存在或已被清理")
    return RelayCommandStatusOut(
        id=status["id"],
        type=status["type"],
        commandStatus=status["status"],
        result=status["result"],
    )
