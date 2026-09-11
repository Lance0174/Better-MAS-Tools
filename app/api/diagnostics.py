"""诊断日志的受认证接口；仅返回已脱敏的工具日志。"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Request

from app.models.schema import ClientLogIn, LogExportOut, LogsOut, OutBase
from app.services.diagnostics import Diagnostics
from app.utils.constants import UTC8
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/logs", tags=["Diagnostics"])


@router.get("", response_model=LogsOut, operation_id="getLogs")
async def get_logs(request: Request) -> LogsOut:
    diagnostics: Diagnostics = request.app.state.diagnostics
    return LogsOut(
        data=diagnostics.snapshot(),
        capacity=diagnostics.capacity,
        fileAvailable=diagnostics.directory is not None,
    )


@router.get("/export", response_model=LogExportOut, operation_id="exportLogs")
async def export_logs(request: Request) -> LogExportOut:
    diagnostics: Diagnostics = request.app.state.diagnostics
    content = (
        await asyncio.to_thread(diagnostics.export)
        if diagnostics.directory is not None
        else diagnostics.export()
    )
    return LogExportOut(
        filename=f"Better-MAS-Tools-{datetime.now(tz=UTC8):%Y%m%d-%H%M%S}.log",
        content=content,
    )


@router.post("/frontend", response_model=OutBase, operation_id="writeClientLog")
async def write_client_log(body: ClientLogIn) -> OutBase:
    get_logger(f"前端/{body.module}").log(body.level, body.message)
    return OutBase()
