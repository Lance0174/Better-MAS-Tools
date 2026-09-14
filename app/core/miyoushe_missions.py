"""米游币编排及短期人工验证，不持久化挑战或验证票据。"""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime

from app.core.state import state
from app.tools import miyoushe
from app.tools.miyoushe_bbs import MiyousheBbsClient, VerificationRequired
from app.utils.constants import UTC8


@dataclass
class PendingVerification:
    account_id: str
    result: dict[str, object]
    context: dict[str, str] = field(repr=False)
    credential_hash: str = field(repr=False)
    handle: asyncio.TimerHandle | None = field(default=None, repr=False)


_pending: dict[str, PendingVerification] = {}


def cancel(session_id: str) -> None:
    item = _pending.pop(session_id, None)
    if item and item.handle:
        item.handle.cancel()


def clear() -> None:
    for session_id in list(_pending):
        cancel(session_id)


def pending() -> list[dict[str, str]]:
    return [
        {
            "sessionId": key,
            "accountId": item.account_id,
            "label": f"{state.data.accounts[item.account_id].Name} · {item.result['game']}",
            "gt": item.context["gt"],
            "challenge": item.context["challenge"],
        }
        for key, item in _pending.items()
        if item.account_id in state.data.accounts
    ]


def capture(results: list[dict[str, object]]) -> None:
    for result in results:
        context = result.pop("_verification", None)
        if not isinstance(context, dict):
            continue
        account_id = str(result.get("account_uid", ""))
        account = state.require_account(account_id)
        for key, previous in list(_pending.items()):
            if (
                previous.account_id == account_id
                and previous.result.get("account") == result.get("account")
                and previous.result["game"] == result["game"]
            ):
                cancel(key)
        if len(_pending) >= 64:
            result["reason"] = "待验证任务较多，请完成现有验证后重试"
            continue
        key = secrets.token_urlsafe(32)
        item = PendingVerification(
            account_id,
            dict(result),
            dict(context),
            hashlib.sha256(account.MiyousheToken.encode()).hexdigest(),
        )
        item.handle = asyncio.get_running_loop().call_later(600, cancel, key)
        _pending[key] = item


def client_for(account_id: str, *, challenge: str = "", override_state=None) -> MiyousheBbsClient:
    scope_state = override_state if override_state is not None else state
    account = scope_state.require_account(account_id)
    return MiyousheBbsClient(
        account.MiyousheToken,
        proxy=scope_state.proxy,
        device_id=account.MiyousheDeviceId,
        device_fp=account.MiyousheDeviceFp,
        challenge=challenge,
    )


async def run(account_id: str, *, challenge: str = "", override_state=None) -> dict[str, object]:
    scope_state = override_state if override_state is not None else state
    account = scope_state.require_account(account_id)
    result: dict[str, object] = {
        "account": account.Name,
        "account_uid": account_id,
        "platform": "米游社",
        "game": "米游币任务",
        "status": "失败",
        "reward": "",
        "reason": "",
    }
    try:
        async with client_for(account_id, challenge=challenge, override_state=scope_state) as client:
            completed, detail = await client.run()
        result["status"] = "成功" if completed else "失败"
        result["reward" if completed else "reason"] = detail
    except VerificationRequired as error:
        result.update(
            status="风控",
            reason=str(error),
            _verification={"gt": error.gt, "challenge": error.challenge, "kind": "bbs"},
        )
    except ValueError as error:
        result["reason"] = str(error)
    except Exception:
        result["reason"] = "米游币请求未完成，请检查网络或稍后重试"
    return result


async def resume(session_id: str, proof: dict[str, str]) -> None:
    from app.core.community_sign import community_sign_flow
    from app.core.runtime import runtime

    runtime.require_idle()
    item = _pending.get(session_id)
    if item is None:
        raise ValueError("人工验证已过期，请重新执行相应任务")
    account = state.require_account(item.account_id)
    if (
        hashlib.sha256(account.MiyousheToken.encode()).hexdigest()
        != item.credential_hash
    ):
        cancel(session_id)
        raise ValueError("账号凭据已变更，请重新获取验证")
    if not proof["geetest_challenge"].startswith(item.context["challenge"][:32]):
        raise ValueError("验证结果与本次挑战不匹配")
    async with community_sign_flow():
        runtime.sign_running = True
        try:
            if item.context["kind"] == "bbs":
                async with client_for(item.account_id) as client:
                    challenge = await client.verify(proof)
                result = await run(item.account_id, challenge=challenge)
            else:
                config = miyoushe.GAME_CONFIG[item.context["gameBiz"]]
                result, cookie = await miyoushe._do_sign(
                    account.MiyousheToken,
                    config,
                    item.context["region"],
                    item.context["uid"],
                    str(item.result["account"]),
                    proxy=state.proxy,
                    verification=proof,
                )
                result["account_uid"] = item.account_id
                if cookie != account.MiyousheToken:
                    await state.update_account(
                        item.account_id, {"MiyousheToken": cookie}, reset_date=False
                    )
            # 已消费票据不得因网络/落盘失败而无限重放。
            cancel(session_id)
            capture([result])
            result["signedAt"] = datetime.now(tz=UTC8).isoformat(timespec="seconds")
            await state.save_results([result], replace_accounts=False)
        finally:
            runtime.sign_running = False
