"""库街区短信登录 HTTP 契约；错误响应不包含验证码或上游原文。"""

from fastapi import APIRouter

from app.core import kuro_login
from app.models.schema import (
    KuroSmsAutomaticOut,
    KuroSmsCreateIn,
    KuroSmsCreateOut,
    KuroSmsLoginIn,
    KuroSmsSendIn,
    KuroSmsSessionIn,
    OutBase,
)
from app.tools.kuro import KURO_CAPTCHA_ID

router = APIRouter(prefix="/api/login/kuro/sms", tags=["KuroLogin"])


@router.post(
    "/automatic", response_model=KuroSmsAutomaticOut, operation_id="automaticKuroSms"
)
async def automatic_sms(body: KuroSmsSessionIn) -> KuroSmsAutomaticOut:
    try:
        sent, message = await kuro_login.send_automatically(body.sessionId)
    except ValueError:
        raise
    except Exception:
        raise ValueError("库街区短信发送失败，请稍后重试") from None
    return KuroSmsAutomaticOut(sent=sent, message=message)


@router.post("/create", response_model=KuroSmsCreateOut, operation_id="createKuroSms")
async def create_sms(body: KuroSmsCreateIn) -> KuroSmsCreateOut:
    session_id = kuro_login.create_session(
        body.accountId, body.phone.get_secret_value()
    )
    return KuroSmsCreateOut(sessionId=session_id, captchaId=KURO_CAPTCHA_ID)


@router.post("/send", response_model=OutBase, operation_id="sendKuroSms")
async def send_sms(body: KuroSmsSendIn) -> OutBase:
    try:
        await kuro_login.send_sms(body.sessionId, body.verification.model_dump())
    except ValueError:
        raise
    except Exception:
        raise ValueError("库街区短信发送失败，请稍后重试") from None
    return OutBase(message="短信已发送，请填写验证码")


@router.post("/login", response_model=OutBase, operation_id="loginKuroSms")
async def login_sms(body: KuroSmsLoginIn) -> OutBase:
    try:
        await kuro_login.finish_login(body.sessionId, body.smsCode.get_secret_value())
    except ValueError:
        raise
    except Exception:
        raise ValueError("库街区登录或保存失败，请稍后重试") from None
    return OutBase(message="库街区登录凭据已自动保存")


@router.post("/cancel", response_model=OutBase, operation_id="cancelKuroSms")
async def cancel_sms(body: KuroSmsSessionIn) -> OutBase:
    kuro_login.cancel_session(body.sessionId)
    return OutBase()
