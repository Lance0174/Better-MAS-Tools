"""云端签到同步接口：接收本地账号 token，临时执行后返回结果，不持久化凭据。

本地端在云端模式下把账号 token 上传到这里；本模块构造一个纯内存的
临时 state 执行签到，执行结束即弃。token 只存在于本次请求的内存中，
不写入云端存储。CF Workers 与 Linux 完整后端共用此契约。
"""

import asyncio

from fastapi import APIRouter

from app.core.community_sign import run_community_sign_in
from app.core.state import CommunityState
from app.models.config import AccountData, SavedState, SettingsData
from app.models.schema import CloudSyncIn, CloudSyncOut, CloudSyncResult

router = APIRouter(prefix="/api/cloud", tags=["Cloud"])


class _MemoryStore:
    """临时内存存储：云端同步执行不落盘，避免污染云端持久状态。"""

    async def save_async(self, _state: SavedState) -> None:
        pass


@router.post("/sync", response_model=CloudSyncOut, operation_id="cloudSync")
async def cloud_sync(body: CloudSyncIn) -> CloudSyncOut:
    if not body.accounts:
        return CloudSyncOut(data=[])

    # 构造临时 state：账号来自上传，设置只保留本次执行相关的开关。
    temp = CommunityState()
    temp.storage = _MemoryStore()
    temp.data = SavedState()
    temp.data.settings = SettingsData(MiyousheBbsEnabled=body.miyoushe_bbs)
    for item in body.accounts:
        account = AccountData(
            Name=item.name or "云端账号",
            Enabled=item.enabled,
        )
        for field, value in item.tokens.items():
            if hasattr(account, field):
                setattr(account, field, value)
        temp.data.accounts[item.uid] = account

    # 用临时 state 执行签到；force=True 不依赖本地 LastSignDate 去重。
    try:
        results = await asyncio.wait_for(
            run_community_sign_in(force=True, override_state=temp),
            timeout=180,
        )
    except asyncio.TimeoutError:
        return CloudSyncOut(
            code=504, status="error", message="云端签到执行超时，请稍后重试", data=[]
        )

    return CloudSyncOut(
        data=[
            CloudSyncResult(
                account_uid=str(item.get("account_uid", "")),
                account=str(item.get("account", "")),
                game=str(item.get("game", "")),
                platform=str(item.get("platform", "")),
                status=str(item.get("status", "")),
                reward=str(item.get("reward", "")),
                reason=str(item.get("reason", "")),
                signedAt=str(item.get("signedAt", "")),
            )
            for item in results
        ]
    )
