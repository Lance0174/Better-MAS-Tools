"""独立社区 HTTP 接口；业务流程交给 core，前端客户端从这些契约生成。"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter

from app.core import accounts, login
from app.core.runtime import runtime
from app.core.state import state
from app.models.config import SettingsData
from app.models.schema import (
    AccountCreateOut,
    AccountIdIn,
    AccountOut,
    AccountReorderIn,
    AccountsOut,
    AccountUpdateIn,
    ActivityQueryIn,
    CommunityActivityOut,
    CommunityActivitySnapshotOut,
    OutBase,
    QrCheckIn,
    QrCheckOut,
    QrCreateOut,
    QrSaveIn,
    SettingsOut,
    SignAccountOut,
    StatusOut,
    TaygedoLoginIn,
)
from app.services.network import network
from app.utils.constants import UTC8

router = APIRouter(prefix="/api", tags=["Community"])


@router.get("/accounts", response_model=AccountsOut, operation_id="listAccounts")
async def list_accounts() -> AccountsOut:
    return AccountsOut(
        data=[
            AccountOut(uid=uid, data=data) for uid, data in state.data.accounts.items()
        ]
    )


@router.post("/accounts", response_model=AccountCreateOut, operation_id="createAccount")
async def create_account() -> AccountCreateOut:
    runtime.require_idle()
    uid = await state.create_account()
    return AccountCreateOut(data=AccountOut(uid=uid, data=state.require_account(uid)))


@router.post("/accounts/update", response_model=OutBase, operation_id="updateAccount")
async def update_account(body: AccountUpdateIn) -> OutBase:
    runtime.require_idle()
    await accounts.update_account(
        body.accountId, body.data.model_dump(exclude_unset=True, exclude_none=True)
    )
    return OutBase()


@router.post("/accounts/delete", response_model=OutBase, operation_id="deleteAccount")
async def delete_account(body: AccountIdIn) -> OutBase:
    runtime.require_idle()
    await state.delete_account(body.accountId)
    return OutBase()


@router.post(
    "/accounts/reorder", response_model=OutBase, operation_id="reorderAccounts"
)
async def reorder_accounts(body: AccountReorderIn) -> OutBase:
    runtime.require_idle()
    await state.reorder_accounts(body.order)
    return OutBase()


@router.get("/settings", response_model=SettingsOut, operation_id="getSettings")
async def get_settings() -> SettingsOut:
    return SettingsOut(
        data=state.data.settings.model_copy(update={"YunmaToken": None}),
        yunmaConfigured=bool(state.data.settings.YunmaToken),
        localConnections=network.local_connections,
    )


@router.put("/settings", response_model=OutBase, operation_id="updateSettings")
async def update_settings(body: SettingsData) -> OutBase:
    runtime.require_idle()
    from urllib.parse import urlsplit

    if body.Proxy and not network.local_connections:
        raise ValueError("纯 Cloudflare 版不支持本机代理")

    if body.Proxy and urlsplit(body.Proxy).scheme not in {
        "http",
        "https",
        "socks5",
        "socks5h",
    }:
        raise ValueError("代理地址必须包含有效的协议")
    if body.YunmaToken is None:
        body.YunmaToken = state.data.settings.YunmaToken
    from app.services.mas import validate_base_url

    body.MasBaseUrl = validate_base_url(body.MasBaseUrl)
    await state.update_settings(body)
    return OutBase()


@router.get("/status", response_model=StatusOut, operation_id="getStatus")
async def get_status() -> StatusOut:
    grouped = state.sign_results()
    return StatusOut(
        running=runtime.sign_running,
        activityRunning=runtime.activity_running,
        revision=state.revision,
        today=datetime.now(tz=UTC8).strftime("%Y-%m-%d"),
        results={
            key: [SignAccountOut.model_validate(item) for item in value]
            for key, value in grouped.items()
        },
    )


@router.post("/sign", response_model=OutBase, operation_id="manualSign")
async def manual_sign() -> OutBase:
    await runtime.sign(force=True)
    return OutBase(message="签到执行完成，请查看各游戏结果")


@router.post(
    "/activity", response_model=CommunityActivityOut, operation_id="queryActivity"
)
async def query_activity(body: ActivityQueryIn) -> CommunityActivityOut:
    snapshots = await runtime.activity(body.accountIds)
    return CommunityActivityOut(
        data=[
            CommunityActivitySnapshotOut(
                account=item.account,
                accountUid=item.account_uid,
                game=item.game,
                platform=item.platform,
                status=item.status,
                completed=item.completed,
                target=item.target,
                tasks=[dict(task) for task in item.tasks],
                resources=[dict(resource) for resource in item.resources],
                reason=item.reason,
                updatedAt=item.updated_at,
                roleName=item.role_name,
                roleUid=item.role_uid,
                server=item.server,
                source=item.source,
            )
            for item in snapshots
        ]
    )


@router.post(
    "/login/{provider}/qr/create", response_model=QrCreateOut, operation_id="createQr"
)
async def create_qr(provider: Literal["miyoushe", "skland"]) -> QrCreateOut:
    try:
        result = await login.create_qr(provider)
        return QrCreateOut(
            ticket=str(result["ticket"]),
            device=str(result["device"]),
            qr_url=str(result["qr_url"]),
        )
    except Exception:
        # 登录异常禁止回显请求和原始响应，避免凭据进入日志或错误页面。
        raise ValueError("二维码创建失败，请稍后重试") from None


@router.post(
    "/login/{provider}/qr/check", response_model=QrCheckOut, operation_id="checkQr"
)
async def check_qr(
    provider: Literal["miyoushe", "skland"], body: QrCheckIn
) -> QrCheckOut:
    try:
        result = await login.check_qr(provider, body.ticket, body.device)
        return QrCheckOut(
            status=str(result.get("status") or "error"),
            cookies_str=str(result.get("cookies_str") or ""),
            scan_code=str(result.get("scan_code") or ""),
            message=str(result.get("message") or ""),
        )
    except Exception:
        raise ValueError("二维码状态查询失败，请稍后重试") from None


@router.post("/login/{provider}/qr/save", response_model=OutBase, operation_id="saveQr")
async def save_qr(provider: Literal["miyoushe", "skland"], body: QrSaveIn) -> OutBase:
    runtime.require_idle()
    try:
        await login.save_qr(
            provider, body.account_uid, cookie=body.cookie, scan_code=body.scan_code
        )
    except Exception:
        raise ValueError("登录凭据保存失败，请检查账号及登录状态") from None
    return OutBase(message="登录凭据已保存")


@router.post("/login/taygedo", response_model=OutBase, operation_id="loginTaygedo")
async def login_taygedo(body: TaygedoLoginIn) -> OutBase:
    runtime.require_idle()
    try:
        await login.login_taygedo(
            body.accountId, body.phone, body.password.get_secret_value()
        )
    except Exception:
        raise ValueError("塔吉多登录失败，请检查账号密码或稍后重试") from None
    return OutBase(message="塔吉多凭据已保存")
