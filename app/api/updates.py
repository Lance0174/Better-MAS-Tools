"""软件更新查询契约；下载和安装由经过限制的系统桥完成。"""

from typing import Literal

from fastapi import APIRouter

from app.models.updates import UpdateCheckOut
from app.services.updates import check_updates

router = APIRouter(prefix="/api/updates", tags=["Updates"])


@router.get("/check", response_model=UpdateCheckOut, operation_id="checkUpdates")
async def check(
    platform: Literal["windows", "android"],
    channel: Literal["stable", "beta"] = "stable",
) -> UpdateCheckOut:
    return await check_updates(platform=platform, channel=channel)
