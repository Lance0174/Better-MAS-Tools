# Copyright (c) 2025 MX
# Adapted from mxyooR/Kuro_login (MIT). See docs/licenses/Kuro_login.txt.
"""拼接极验图标提示，交由云码识别，再生成极验4要求的坐标。"""

import asyncio
import io
import sys

import httpx
from PIL import Image

from app.tools.yunma import recognize_icons

from .slide import download_image


def compose_icons(background: bytes, icons: list[bytes]) -> tuple[bytes, int, int]:
    with Image.open(io.BytesIO(background)) as original:
        width, height = original.size
        if not 1 <= width <= 2048 or not 1 <= height <= 2048:
            raise ValueError("验证码图片尺寸无效")
        canvas = Image.new("RGB", (width, height + 64), "white")
        canvas.paste(original.convert("RGB"), (0, 0))
    for index, raw in enumerate(icons):
        with Image.open(io.BytesIO(raw)) as icon:
            if not 1 <= icon.width <= 512 or not 1 <= icon.height <= 512:
                raise ValueError("验证码提示图片尺寸无效")
            icon.thumbnail((48, 48))
            rgba = icon.convert("RGBA")
            # Kuro_login 的 pictureUtils 从 Alpha 提取轮廓；白色透明图标直接贴白底会消失。
            alpha = rgba.getchannel("A")
            if alpha.getextrema()[0] < 255 and all(
                low == high for low, high in rgba.convert("RGB").getextrema()
            ):
                rgba = Image.new("RGBA", rgba.size, "black")
                rgba.putalpha(alpha)
            canvas.paste(rgba, (12 + index * 56, height + 8), rgba)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue(), width, height


async def get_track(
    data: dict,
    message: str,
    sign: str,
    client: httpx.AsyncClient,
    *,
    token: str,
    proxy: str | None,
) -> dict:
    questions = data.get("ques")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 5:
        raise ValueError("当前图标验证码暂不支持")
    background = await download_image(client, data["imgs"])
    icons = await asyncio.gather(*(download_image(client, path) for path in questions))
    if sys.platform == "emscripten":
        image, width, height = compose_icons(background, icons)
    else:
        image, width, height = await asyncio.to_thread(compose_icons, background, icons)
    points = await recognize_icons(image, token=token, count=len(icons), proxy=proxy)
    if any(x >= width or y >= height for x, y in points):
        raise ValueError("云码返回坐标超出验证图片范围")
    return {
        "passtime": 2098,
        "userresponse": [
            [round(x / 301.8125 * 10000), round(y / 201.296875 * 10000)]
            for x, y in points
        ],
        "device_id": "",
        "lot_number": data["lot_number"],
        "pow_msg": message,
        "pow_sign": sign,
        "geetest": "captcha",
        "lang": "zh",
        "ep": "123",
        "biht": "1426265548",
        "HufC": "hxdr",
        "d229": {"543fa0": "24e1b527"},
        "em": {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0},
    }
