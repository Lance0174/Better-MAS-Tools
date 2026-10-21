"""诊断日志的受认证接口；仅返回已脱敏的工具日志。"""

import asyncio
import re
from datetime import datetime

from fastapi import APIRouter, Request

from app.models.schema import ClientLogIn, LogExportOut, LogsOut, OutBase
from app.services.diagnostics import Diagnostics
from app.utils.constants import UTC8
from app.utils.logger import get_logger
from app.utils.security import sanitize_log_message

router = APIRouter(prefix="/api/logs", tags=["Diagnostics"])

# 前端日志单条落到诊断缓冲区的最大长度：12000 字的前端堆栈会把 2000 条环形
# 缓冲区一次冲掉，也会拉大 /api/logs 的响应体。
CLIENT_LOG_MESSAGE_LIMIT = 2000
# 模块名会拼进日志器名称，只允许路径分隔符与常规标识符字符。
_MODULE_SAFE = re.compile(r"[^\w\u4e00-\u9fff./-]")


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
    # 前端上报内容按服务端日志同等规则处理：先脱敏，再把换行压成空格，
    # 避免一条前端消息在诊断文件里伪造出多行记录，最后按预算截断。
    message = " ".join(sanitize_log_message(body.message).split())
    module = _MODULE_SAFE.sub("_", body.module)
    get_logger(f"前端/{module}").log(body.level, message[:CLIENT_LOG_MESSAGE_LIMIT])
    return OutBase()
