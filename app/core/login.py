"""复用上游登录协议，一次性密码和扫码票据只在当前请求中存在。"""

from app.core.accounts import update_account
from app.core.state import state


async def create_qr(provider: str) -> dict[str, object]:
    if provider == "skland":
        from app.tools import skland

        result = await skland.create_skland_qr_login(proxy=state.proxy)
    else:
        from app.tools import miyoushe_qr

        result = await miyoushe_qr.create_qr_login(proxy=state.proxy)
    if not isinstance(result, dict) or result.get("error"):
        raise ValueError("二维码创建失败，请稍后重试")
    if not all(
        isinstance(result.get(key), str) and result[key]
        for key in ("ticket", "device", "qr_url")
    ):
        raise ValueError("二维码服务返回的数据不完整")
    return result


async def check_qr(provider: str, ticket: str, device: str) -> dict[str, object]:
    if provider == "skland":
        from app.tools import skland

        result = await skland.check_skland_qr_status(ticket, device, proxy=state.proxy)
    else:
        from app.tools import miyoushe_qr

        result = await miyoushe_qr.check_qr_status(ticket, device, proxy=state.proxy)
    if not isinstance(result, dict):
        raise ValueError("二维码状态响应格式无效")
    if result.get("error") and result.get("status") != "expired":
        raise ValueError("二维码状态查询失败，请稍后重试")
    return result


async def save_qr(provider: str, uid: str, *, cookie: str, scan_code: str) -> None:
    state.require_account(uid)
    if provider == "skland":
        from app.tools import skland

        serialized = await skland.finalize_skland_qr_login(scan_code, proxy=state.proxy)
        credential = skland.validate_skland_credential(serialized)
        if any(not credential.get(field) for field in ("oauthToken", "token", "cred")):
            raise ValueError("森空岛扫码未取得完整凭据")
        await update_account(uid, {"SklandToken": serialized})
    else:
        # 沿用 MAS 的完整 Cookie 链路，不裁剪补全得到的 stoken、mid 等字段。
        if not cookie.strip():
            raise ValueError("米游社扫码未取得完整凭据")
        await update_account(uid, {"MiyousheToken": cookie})


async def login_taygedo(uid: str, phone: str, password: str) -> None:
    from app.tools import taygedo

    account = state.require_account(uid)
    credential = await taygedo.login_taygedo_with_password(
        phone.strip(), password, existing_raw=account.TaygedoToken, proxy=state.proxy
    )
    serialized = taygedo.serialize_taygedo_credential(credential)
    parsed = taygedo.parse_taygedo_credential(serialized)
    if any(not parsed.get(field) for field in ("accessToken", "refreshToken", "uid")):
        raise ValueError("塔吉多登录未取得完整凭据")
    await update_account(uid, {"TaygedoToken": serialized})
