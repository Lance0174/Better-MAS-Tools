"""云码图标坐标协议，按 jfbym.com/test/317.html（30332）实现。

只发送验证码图像及服务密钥，不发送社区 Cookie、手机号或账号信息。
"""

import base64

from app.services.network import network

YUNMA_URL = "https://api.jfbym.com/api/YmServer/customApi"


async def recognize_icons(
    image: bytes, *, token: str, count: int, proxy: str | None
) -> list[tuple[int, int]]:
    if not token:
        raise ValueError("请在设置中填写云码 API 密钥")
    async with network.client(proxy=proxy, trust_env=False, timeout=45) as client:
        response = await client.post(
            YUNMA_URL,
            json={
                "token": token,
                "type": "30332",
                "image": base64.b64encode(image).decode("ascii"),
                "direction": "bottom",
                "click_num": str(count),
            },
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or data.get("code") != 10000:
        if isinstance(data, dict) and data.get("code") == 10002:
            raise ValueError("云码余额不足，请充值或改用人工验证")
        raise ValueError("云码未能识别此次验证码，请使用人工验证")
    result = data.get("data")
    if not isinstance(result, dict) or not isinstance(result.get("data"), str):
        raise ValueError("云码返回了无效的坐标结果")
    try:
        pairs = [pair.split(",") for pair in result["data"].split("|")]
        if len(pairs) != count or any(len(pair) != 2 for pair in pairs):
            raise ValueError
        points = [(int(x.strip()), int(y.strip())) for x, y in pairs]
    except (ValueError, TypeError):
        raise ValueError("云码返回的点击坐标不匹配") from None
    if any(min(point) < 0 for point in points):
        raise ValueError("云码返回的点击坐标不匹配")
    return points
