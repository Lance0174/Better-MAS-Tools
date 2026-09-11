"""库街区短信会话：短时保留手机号，登录后自动提取并加密保存凭据。"""

import asyncio
import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field

from app.core.accounts import update_account
from app.core.runtime import runtime
from app.core.state import state
from app.tools import kuro

SESSION_SECONDS = 600
SMS_INTERVAL = 60
MAX_ATTEMPTS = 5
AUTO_CAPTCHA_TIMEOUT = 15
YUNMA_CAPTCHA_TIMEOUT = 30


@dataclass
class SmsSession:
    account_id: str
    phone: str = field(repr=False)
    device: str = field(default_factory=lambda: secrets.token_hex(20), repr=False)
    distinct: str = field(default_factory=lambda: secrets.token_hex(16), repr=False)
    sent: bool = False
    busy: bool = False
    attempts: int = 0
    credential: str = field(default="", repr=False)
    verification_task: asyncio.Task | None = field(default=None, repr=False)


_sessions: dict[str, SmsSession] = {}
_cooldowns: dict[str, float] = {}
_expiry_handles: dict[str, asyncio.TimerHandle] = {}


def create_session(account_id: str, phone: str) -> str:
    state.require_account(account_id)
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise ValueError("请输入有效的中国大陆手机号")
    if len(_sessions) >= 16:
        raise ValueError("登录会话过多，请关闭其他登录窗口或稍后重试")
    session_id = secrets.token_urlsafe(32)
    session = SmsSession(account_id, phone)
    _sessions[session_id] = session

    def expire() -> None:
        # 主动清理，避免用户关闭页面后手机号仍无限留在进程中。
        cancel_session(session_id)

    _expiry_handles[session_id] = asyncio.get_running_loop().call_later(
        SESSION_SECONDS, expire
    )
    return session_id


def cancel_session(session_id: str) -> None:
    session = _sessions.pop(session_id, None)
    if session and session.verification_task:
        session.verification_task.cancel()
    handle = _expiry_handles.pop(session_id, None)
    if handle is not None:
        handle.cancel()


def clear_sessions() -> None:
    for session_id in list(_sessions):
        cancel_session(session_id)
    _cooldowns.clear()


async def send_automatically(session_id: str) -> tuple[bool, str]:
    from app.tools._geetest import Geetest

    session = require_session(session_id)
    settings = state.data.settings
    if session.busy:
        raise ValueError("登录请求正在执行，请稍候")
    if settings.CaptchaMode == "manual":
        return False, "请完成人工验证"
    phone_key = hashlib.sha256(session.phone.encode()).hexdigest()
    if _cooldowns.get(phone_key, 0) > asyncio.get_running_loop().time():
        raise ValueError("短信发送过于频繁，请 60 秒后重试")

    async def solve() -> dict:
        async with Geetest(
            kuro.KURO_CAPTCHA_ID,
            proxy=state.proxy,
            yunma_token=(settings.YunmaToken or "")
            if settings.CaptchaMode == "local_yunma"
            else "",
        ) as verification:
            return json.loads(await verification.fetch_sec_code())

    session.busy = True
    session.verification_task = asyncio.create_task(solve())
    try:
        # 覆盖加载、下载、识别和校验的总耗时，不能只限制单次 HTTP 请求。
        timeout = (
            YUNMA_CAPTCHA_TIMEOUT
            if settings.CaptchaMode == "local_yunma"
            else AUTO_CAPTCHA_TIMEOUT
        )
        solution = await asyncio.wait_for(session.verification_task, timeout=timeout)
    except TimeoutError:
        return False, "自动验证超时，请改用人工验证"
    except asyncio.CancelledError:
        if session_id not in _sessions:
            raise ValueError("短信登录已取消或过期，请重新开始") from None
        raise
    except Exception:
        return False, "自动验证未完成，请使用人工验证"
    finally:
        session.busy = False
        session.verification_task = None
    if not isinstance(solution, dict):
        return False, "自动验证未取得有效结果，请使用人工验证"
    await send_sms(session_id, solution)
    return True, "短信已发送"


def require_session(session_id: str) -> SmsSession:
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError("短信登录已过期，请重新开始")
    state.require_account(session.account_id)
    return session


async def send_sms(session_id: str, verification: dict[str, str]) -> None:
    session = require_session(session_id)
    if session.busy:
        raise ValueError("登录请求正在执行，请稍候")
    if verification.get("captcha_id") != kuro.KURO_CAPTCHA_ID or not all(
        verification.get(key)
        for key in ("lot_number", "pass_token", "gen_time", "captcha_output")
    ):
        raise ValueError("请先完成人机验证")
    loop = asyncio.get_running_loop()
    phone_key = hashlib.sha256(session.phone.encode()).hexdigest()
    if _cooldowns.get(phone_key, 0) > loop.time():
        raise ValueError("短信发送过于频繁，请 60 秒后重试")
    deadline = loop.time() + SMS_INTERVAL
    _cooldowns[phone_key] = deadline

    def clear_cooldown() -> None:
        if _cooldowns.get(phone_key) == deadline:
            _cooldowns.pop(phone_key, None)

    loop.call_later(SMS_INTERVAL, clear_cooldown)
    session.busy = True
    try:
        await kuro.request_kuro_sms(
            phone=session.phone,
            verification=verification,
            device=session.device,
            distinct=session.distinct,
            proxy=state.proxy,
        )
        require_session(session_id)
        session.sent = True
        session.attempts = 0
        session.credential = ""
    finally:
        session.busy = False


async def finish_login(session_id: str, code: str) -> None:
    session = require_session(session_id)
    if session.busy:
        raise ValueError("登录请求正在执行，请稍候")
    if not session.sent:
        raise ValueError("请先发送短信验证码")
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("请输入六位短信验证码")
    if session.attempts >= MAX_ATTEMPTS and not session.credential:
        raise ValueError("验证码尝试次数已用完，请重新发送")
    runtime.require_idle()
    session.busy = True
    try:
        if not session.credential:
            session.attempts += 1
            session.credential = await kuro.login_kuro_sms(
                phone=session.phone,
                code=code,
                device=session.device,
                distinct=session.distinct,
                proxy=state.proxy,
            )
        require_session(session_id)
        runtime.require_idle()
        # 写盘失败保留短时正式凭据，重试保存不重复消费短信码。
        await update_account(session.account_id, {"KuroToken": session.credential})
        cancel_session(session_id)
    finally:
        session.busy = False
