"""米游社人工验证 HTTP 契约。"""

from fastapi import APIRouter

from app.core import miyoushe_missions
from app.models.schema import MiyousheVerificationIn, MiyousheVerificationsOut, OutBase

router = APIRouter(prefix="/api/miyoushe/verification", tags=["MiyousheMissions"])


@router.get(
    "",
    response_model=MiyousheVerificationsOut,
    operation_id="listMiyousheVerifications",
)
async def list_verifications() -> MiyousheVerificationsOut:
    return MiyousheVerificationsOut(data=miyoushe_missions.pending())


@router.post(
    "/submit", response_model=OutBase, operation_id="submitMiyousheVerification"
)
async def submit(body: MiyousheVerificationIn) -> OutBase:
    try:
        await miyoushe_missions.resume(body.sessionId, body.verification.model_dump())
    except ValueError:
        raise
    except Exception:
        raise ValueError("米游社验证或执行未完成，请稍后重试") from None
    return OutBase(message="验证后的执行已结束，请查看对应任务结果")
