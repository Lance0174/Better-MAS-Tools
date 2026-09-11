# Copyright (c) 2025 MX
# Adapted from mxyooR/Kuro_login (MIT). See docs/licenses/Kuro_login.txt.
import asyncio
import io
import sys
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx


def _calculate_slide_distance_numpy(bg_bytes: bytes, target_bytes: bytes) -> int:
    """Workers 无 OpenCV，使用灰度梯度相关匹配；无法识别的挑战仍交人工。"""
    import numpy as np
    from PIL import Image

    images = []
    for raw in (bg_bytes, target_bytes):
        with Image.open(io.BytesIO(raw)) as image:
            if not (2 <= image.width <= 640 and 2 <= image.height <= 400):
                raise ValueError("当前滑块图片尺寸需要人工验证")
            gray = np.asarray(image.convert("L"), dtype=np.float32)
        dy, dx = np.gradient(gray)
        images.append(np.hypot(dx, dy))
    background, target = images
    height, width = target.shape
    if (
        height > background.shape[0]
        or width > background.shape[1]
        or float(target.std()) < 1
    ):
        raise ValueError("滑块图片缺少有效特征")
    shape = tuple(
        1 << (a + b - 2).bit_length() for a, b in zip(background.shape, target.shape)
    )
    kernel = target - target.mean()
    correlation = np.fft.irfft2(
        np.fft.rfft2(background, shape) * np.fft.rfft2(kernel[::-1, ::-1], shape),
        s=shape,
    )
    correlation = correlation[
        height - 1 : background.shape[0], width - 1 : background.shape[1]
    ]

    # 归一化背景区域能量，避免把纹理最强处直接当作滑块缺口。
    def window_sum(array):
        integral = np.pad(array.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return (
            integral[height:, width:]
            - integral[:-height, width:]
            - integral[height:, :-width]
            + integral[:-height, :-width]
        )

    energy = np.maximum(
        window_sum(background * background) - window_sum(background) ** 2 / target.size,
        1,
    )
    score = correlation / np.sqrt(energy * (kernel * kernel).sum())
    if float(score.max()) < 0.15:
        raise ValueError("滑块匹配置信度不足，请人工验证")
    return int(np.unravel_index(score.argmax(), score.shape)[1])


def _calculate_slide_distance_cv2(bg_bytes: bytes, target_bytes: bytes) -> int:
    import cv2
    import numpy as np
    from PIL import Image

    # 限定同步识别的计算量；超时取消不会强制终止已经运行的 OpenCV 线程。
    sizes = []
    for raw in (bg_bytes, target_bytes):
        with Image.open(io.BytesIO(raw)) as image:
            if not (2 <= image.width <= 640 and 2 <= image.height <= 400):
                raise ValueError("当前滑块图片尺寸需要人工验证")
            sizes.append(image.size)
    if sizes[1][0] > sizes[0][0] or sizes[1][1] > sizes[0][1]:
        raise ValueError("滑块尺寸不能大于背景")

    bg_arr = np.frombuffer(bg_bytes, np.uint8)
    target_arr = np.frombuffer(target_bytes, np.uint8)

    bg_img = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
    target_img = cv2.imdecode(target_arr, cv2.IMREAD_COLOR)
    if bg_img is None or target_img is None:
        raise ValueError("滑块图片格式无效")

    bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)

    bg_edges = cv2.Canny(bg_gray, 100, 200)
    target_edges = cv2.Canny(target_gray, 100, 200)

    res = cv2.matchTemplate(bg_edges, target_edges, cv2.TM_CCOEFF_NORMED)

    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    return max_loc[0]


async def download_image(client: httpx.AsyncClient, path: str) -> bytes:
    url = urljoin("https://static.geetest.com/", path)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "static.geetest.com"
        or parsed.port not in (None, 443)
    ):
        raise ValueError("验证码图片来源不受支持")
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        data = bytearray()
        async for block in response.aiter_bytes():
            data.extend(block)
            if len(data) > 2_000_000:
                raise ValueError("验证码图片过大")
    return bytes(data)


async def get_slide_distance(
    bgPath: str, slicePath: str, client: httpx.AsyncClient
) -> int:
    """
    异步下载图片并计算距离
    """
    target_bytes, bg_bytes = await asyncio.gather(
        download_image(client, slicePath), download_image(client, bgPath)
    )

    if sys.platform == "emscripten":
        distance = _calculate_slide_distance_numpy(bg_bytes, target_bytes)
    else:
        distance = await asyncio.to_thread(
            _calculate_slide_distance_cv2, bg_bytes, target_bytes
        )

    return distance


async def get_track(
    geetest_info: dict[str, Any], message: str, sign: str, client: httpx.AsyncClient
) -> dict[str, Any]:
    slide_distance = await get_slide_distance(
        geetest_info["bg"], geetest_info["slice"], client
    )

    return {
        "setLeft": slide_distance,
        "passtime": 1718,
        "userresponse": slide_distance / 1.0059466666666665 + 2,
        "device_id": "",
        "lot_number": geetest_info["lot_number"],
        "pow_msg": message,
        "pow_sign": sign,
        "geetest": "captcha",
        "lang": "zh",
        "ep": "123",
        "biht": "1426265548",
        "dRjQ": "738u",
        "em": {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0},
    }
