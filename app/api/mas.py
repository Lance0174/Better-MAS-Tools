"""本机 MAS 接入 HTTP 契约。"""

from fastapi import APIRouter

from app.core.state import state
from app.models.schema import (
    MasSnapshotOut,
    MasStartIn,
    MasStartOut,
    MasStopIn,
    OutBase,
)
from app.services import mas

router = APIRouter(prefix="/api/mas", tags=["Mas"])


@router.get("/snapshot", response_model=MasSnapshotOut, operation_id="getMasSnapshot")
async def snapshot() -> MasSnapshotOut:
    try:
        return MasSnapshotOut(**await mas.snapshot(state.data.settings.MasBaseUrl))
    except Exception:
        raise ValueError("无法连接本机 MAS，请确认地址是否正确和 MAS 是否已启动") from None


@router.post("/start", response_model=MasStartOut, operation_id="startMasTask")
async def start(body: MasStartIn) -> MasStartOut:
    try:
        result = await mas.request(
            state.data.settings.MasBaseUrl,
            "/api/dispatch/start",
            payload=body.model_dump(),
        )
        return MasStartOut(taskId=result["taskId"])
    except Exception:
        raise ValueError("MAS 启动请求未确认，请先刷新运行状态再决定是否重试") from None


@router.post("/stop", response_model=OutBase, operation_id="stopMasTask")
async def stop(body: MasStopIn) -> OutBase:
    try:
        await mas.request(
            state.data.settings.MasBaseUrl,
            "/api/dispatch/stop",
            payload=body.model_dump(),
        )
    except Exception:
        raise ValueError("MAS 停止请求未确认，请刷新运行状态") from None
    return OutBase(message="已请求 MAS 停止任务")
