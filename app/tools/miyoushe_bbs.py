"""米游币任务协议。接口知识参考 Ljzd-PRO/nonebot-plugin-mystool。

不依赖参考项目运行环境；不输出 Cookie、原始响应或验证票据。
"""

import asyncio
import hashlib
import json
import secrets
import time

from app.services.network import network

from .miyoushe import SALT_DATA, prepare_miyoushe_session

BBS_API = "https://bbs-api.miyoushe.com"
BBS_SALT = "idMMaGYmVgPzh3wxmWudUXKUPGidO7GM"
TASK_KEYS = ("continuous_sign", "view_post_0", "post_up_0", "share_post_0")


class VerificationRequired(ValueError):
    def __init__(self, gt: str, challenge: str):
        super().__init__("需要人工验证，完成后可继续米游币任务")
        self.gt = gt
        self.challenge = challenge


def mission_remaining(definitions: list[dict], states: list[dict]) -> dict[str, int]:
    """只执行上游明确声明的四种日常任务，不推测未知任务或完成状态。"""
    progress = {str(item.get("mission_key")): item for item in states}
    remaining = {}
    for item in definitions:
        key = str(item.get("mission_key"))
        if key not in TASK_KEYS:
            continue
        threshold = int(item.get("threshold", 0))
        if not 1 <= threshold <= 20:
            raise ValueError("米游币任务目标异常，已停止自动执行")
        current = progress.get(key, {})
        remaining[key] = (
            0
            if current.get("is_get_award")
            else max(0, threshold - int(current.get("happened_times", 0)))
        )
    if not remaining:
        raise ValueError("未取得可识别的米游币任务定义")
    return remaining


class MiyousheBbsClient:
    def __init__(
        self,
        cookie: str,
        *,
        proxy: str | None,
        device_id: str = "",
        device_fp: str = "",
        challenge: str = "",
    ):
        session = prepare_miyoushe_session(cookie)
        if not session.capabilities.has_stoken or not session.uid:
            raise ValueError(
                "米游币任务需要完整 stoken；现有游戏签到 Cookie 可继续使用"
            )
        if session.capabilities.has_stoken_v2 and not session.capabilities.has_mid:
            raise ValueError("米游币凭据缺少与 stoken_v2 配套的 mid")
        self.headers = {
            "Cookie": "; ".join(
                f"{key}={value}"
                for key, value in session.cookies.items()
                if key != "login_ticket"
            ),
            "x-rpc-device_id": device_id or session.device_id,
            "x-rpc-app_version": "2.106.2",
            "x-rpc-client_type": "2",
            "x-rpc-channel": "miyousheluodi",
            "x-rpc-sys_version": "12",
            "x-rpc-device_name": "Xiaomi MI 6",
            "x-rpc-device_model": "Mi 6",
            "User-Agent": "okhttp/4.9.3",
            "Referer": "https://app.mihoyo.com",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if device_fp:
            self.headers["x-rpc-device_fp"] = device_fp
        if challenge:
            self.headers["x-rpc-challenge"] = challenge
        self.client = network.client(proxy=proxy, trust_env=False, timeout=25)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self.client.aclose()

    async def request(
        self,
        path: str,
        *,
        payload: dict | None = None,
        detect_verification: bool = True,
    ) -> dict:
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
        stamp = str(int(time.time()))
        nonce = str(100001 + secrets.randbelow(100000))
        raw = (
            f"salt={SALT_DATA}&t={stamp}&r={nonce}&b={body}&q="
            if body
            else f"salt={BBS_SALT}&t={stamp}&r={nonce}"
        )
        headers = dict(
            self.headers, DS=f"{stamp},{nonce},{hashlib.md5(raw.encode()).hexdigest()}"
        )
        response = await self.client.request(
            "POST" if payload is not None else "GET",
            BBS_API + path,
            headers=headers,
            content=body or None,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("米游币接口返回格式异常")
        code = result.get("retcode")
        if code == 1034 and detect_verification:
            data = await self.request(
                "/misc/api/createVerification?is_high=true", detect_verification=False
            )
            if data.get("gt") and data.get("challenge"):
                raise VerificationRequired(str(data["gt"]), str(data["challenge"]))
            raise ValueError("米游社风控验证暂不可用，请稍后重试")
        if code not in (0, 1008):
            raise ValueError(
                f"米游币请求未完成（业务码 {code if isinstance(code, int) else '未知'}）"
            )
        data = result.get("data")
        return data if isinstance(data, dict) else {}

    async def verify(self, proof: dict[str, str]) -> str:
        data = await self.request(
            "/misc/api/verifyVerification", payload=proof, detect_verification=False
        )
        challenge = data.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise ValueError("米游社未返回验证凭证，请重新获取挑战")
        return challenge

    async def run(self) -> tuple[bool, str]:
        definitions = (await self.request("/apihub/wapi/getMissions?point_sn=myb")).get(
            "missions"
        )
        before = await self.request("/apihub/wapi/getUserMissionsState?point_sn=myb")
        if not isinstance(definitions, list) or not isinstance(
            before.get("states"), list
        ):
            raise ValueError("未取得完整米游币任务状态")
        remaining = mission_remaining(definitions, before["states"])
        if not any(remaining.values()):
            return True, "今日米游币任务已完成"
        # 多个讨论区共享日常目标。按上游目标执行，已完成的阅读和点赞不重放。
        for gid in (2, 5, 6, 8)[: remaining.get("continuous_sign", 0)]:
            await self.request("/apihub/app/api/signIn", payload={"gids": str(gid)})
            await asyncio.sleep(1)
        if any(remaining.get(key, 0) for key in TASK_KEYS[1:]):
            data = await self.request(
                "/post/api/feeds/posts?fresh_action=1&gids=2&is_first_initialize=false&last_id="
            )
            posts = [
                item
                for item in data.get("list", [])
                if isinstance(item, dict) and isinstance(item.get("post"), dict)
            ]
            for key in TASK_KEYS[1:]:
                candidates = [
                    item
                    for item in posts
                    if key != "post_up_0"
                    or (item.get("self_operation") or {}).get("attitude", 0) == 0
                ]
                for item in candidates[: remaining.get(key, 0)]:
                    post_id = str(item["post"].get("post_id", ""))
                    if not post_id.isdigit():
                        continue
                    if key == "view_post_0":
                        await self.request(f"/post/api/getPostFull?post_id={post_id}")
                    elif key == "post_up_0":
                        await self.request(
                            "/post/api/post/upvote",
                            payload={
                                "post_id": post_id,
                                "is_cancel": False,
                                "gids": "2",
                            },
                        )
                    else:
                        await self.request(
                            f"/apihub/api/getShareConf?entity_id={post_id}&entity_type=1"
                        )
                    await asyncio.sleep(1)
        after = await self.request("/apihub/wapi/getUserMissionsState?point_sn=myb")
        if not isinstance(after.get("states"), list):
            raise ValueError("执行后未取得米游币任务进度，无法确认完成")
        unfinished = mission_remaining(definitions, after["states"])
        gained = max(
            0,
            int(after.get("already_received_points", 0))
            - int(before.get("already_received_points", 0)),
        )
        complete = not any(unfinished.values())
        return complete, f"本次新增 {gained} 米游币；" + (
            "今日任务全部完成" if complete else "部分任务尚未完成，可稍后刷新重试"
        )
