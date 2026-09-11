"""账号修改和一次性凭据校验，不包含 HTTP 或文件读写。"""

from app.core.state import state
from app.tools.community_credentials import validate_community_credential
from app.tools.community_sign_provider import COMMUNITY_TOKEN_FIELDS


async def update_account(uid: str, fields: dict[str, object]) -> None:
    state.require_account(uid)
    if fields.get("MiyousheToken"):
        # 临时票据无论来自扫码还是手动粘贴，都不能进入持久化凭据。
        original = str(fields["MiyousheToken"])
        cookie = "; ".join(
            part.strip()
            for part in original.split(";")
            if part.strip() and part.partition("=")[0].strip() != "login_ticket"
        )
        if original.strip() and not cookie:
            raise ValueError("米游社凭据缺少可保存的认证信息")
        fields["MiyousheToken"] = cookie
    for field in ("MiyousheDeviceId", "MiyousheDeviceFp"):
        if field in fields:
            fields[field] = str(fields[field] or "").strip()
    for field in COMMUNITY_TOKEN_FIELDS:
        if field in fields and fields[field]:
            result = validate_community_credential(field, fields[field])
            if not result.locally_valid:
                raise ValueError("凭据格式不完整，请检查内容或使用内置登录")
    await state.update_account(uid, fields)
