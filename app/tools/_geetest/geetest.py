# Copyright (c) 2025 MX
# Adapted from mxyooR/Kuro_login (MIT). See docs/licenses/Kuro_login.txt.
import hashlib
import json
from types import TracebackType
from typing import Any

import httpx

from app.services.network import network

from .consts import DEFAULT_HEADERS
from .errors import CaptchaError
from .track_detact import slide
from .utils import geetest_m, get_current_timestamp, get_guid


class Geetest:
    CALLBACK_SIG = f"geetest_{get_current_timestamp()}"

    def __init__(
        self, captcha_id: str, *, proxy: str | None = None, yunma_token: str = ""
    ):
        self.captcha_id = captcha_id
        self.proxy = proxy
        self.yunma_token = yunma_token
        self.CALLBACK_SIG = f"geetest_{get_current_timestamp()}"
        self.geetest_info: dict[str, Any] = {}

        self.client = network.client(
            headers=DEFAULT_HEADERS,
            timeout=20,
            proxy=proxy,
            trust_env=False,
        )

    def _convert_callback(self, context: str):
        body = context.strip().removesuffix(";").strip()
        prefix = self.CALLBACK_SIG + "("
        if body.startswith(prefix) and body.endswith(")"):
            body = body[len(prefix) : -1]
        value = json.loads(body)
        if not isinstance(value, dict):
            raise CaptchaError("极验返回的验证数据格式无效，请重试")
        return value

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ):
        await self.close()

    async def _send_load(self):
        params = {
            "callback": self.CALLBACK_SIG,
            "captcha_id": self.captcha_id,
            "client_type": "web",
            "pt": "1",
            "lang": "zho",
        }
        try:
            response = await self.client.get(
                url="https://gcaptcha4.geetest.com/load", params=params
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise CaptchaError("极验加载失败，请检查网络或本工具的代理设置") from None

        geetest_info = self._convert_callback(context=response.text)
        if geetest_info.get("status") != "success":
            raise CaptchaError("极验未能创建验证挑战，请重试")

        geetest_data = geetest_info.get("data")
        if not isinstance(geetest_data, dict):
            raise CaptchaError("极验返回的挑战数据无效，请重试")

        self.geetest_info = geetest_data

    def _get_pow(self) -> tuple[str, str]:
        pow_detail = self.geetest_info["pow_detail"]
        hash_func = pow_detail["hashfunc"]
        if int(pow_detail["bits"]) != 0 or hash_func not in {"md5", "sha1", "sha256"}:
            raise CaptchaError("当前验证码需要人工验证")
        pow_info = [
            str(pow_detail["version"]),
            str(pow_detail["bits"]),
            hash_func,
            pow_detail["datetime"],
            str(self.captcha_id),
            self.geetest_info["lot_number"],
            get_guid(),
        ]
        pow_message = "|".join(pow_info)
        hash_obj = hashlib.new(hash_func)
        hash_obj.update(pow_message.encode("utf-8"))
        sign = hash_obj.hexdigest()

        return pow_message, sign

    async def _fetch_track(self, pow_message: str, sign: str):
        captcha_type = self.geetest_info["captcha_type"]
        if captcha_type == "slide":
            return await slide.get_track(
                geetest_info=self.geetest_info,
                message=pow_message,
                sign=sign,
                client=self.client,
            )

        if captcha_type == "icon" and self.yunma_token:
            from .track_detact import icon

            return await icon.get_track(
                self.geetest_info,
                pow_message,
                sign,
                self.client,
                token=self.yunma_token,
                proxy=self.proxy,
            )

        if captcha_type == "icon":
            raise CaptchaError("当前为图标验证码，请人工完成或在设置中配置云码")
        raise CaptchaError("当前验证码类型不支持自动识别，请使用人工验证")

    async def _verify(self, w: str):
        params = {
            "callback": self.CALLBACK_SIG,
            "captcha_id": self.captcha_id,
            "client_type": "web",
            "lot_number": self.geetest_info["lot_number"],
            "payload": self.geetest_info["payload"],
            "process_token": self.geetest_info["process_token"],
            "payload_protocol": "1",
            "pt": "1",
            "w": w,
        }

        try:
            response = await self.client.get(
                url="https://gcaptcha4.geetest.com/verify", params=params
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise CaptchaError("极验校验请求失败，请检查网络后重试") from None

        response_data = self._convert_callback(context=response.text)
        data = response_data.get("data")
        if (
            response_data.get("status") != "success"
            or not isinstance(data, dict)
            or data.get("result") != "success"
        ):
            raise CaptchaError("极验未通过本次识别结果，请重试或使用人工验证")

        proof = data.get("seccode")
        if (
            not isinstance(proof, dict)
            or proof.get("captcha_id") != self.captcha_id
            or not all(
                isinstance(proof.get(key), str) and proof[key]
                for key in ("lot_number", "pass_token", "gen_time", "captcha_output")
            )
        ):
            raise CaptchaError("极验未返回完整验证凭证，请重新验证")

        return response_data

    async def fetch_sec_code(self) -> str:
        stage = "极验加载"
        try:
            await self._send_load()
            pow_message, sign = self._get_pow()
            stage = "验证码图片识别"
            track = await self._fetch_track(pow_message, sign)
            stage = "极验校验"
            verify_result = await self._verify(geetest_m(track))
            return json.dumps(verify_result["data"]["seccode"])
        except CaptchaError:
            raise
        except httpx.HTTPError:
            raise CaptchaError(f"{stage}网络请求失败，请重试或使用人工验证") from None
        except Exception:
            raise CaptchaError(f"{stage}未完成，请重试或使用人工验证") from None
