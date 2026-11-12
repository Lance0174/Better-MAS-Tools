"""软件更新的公开元数据；不接收任意下载地址或本机路径。"""

from typing import Literal

from app.models.schema import OutBase


class UpdateCheckOut(OutBase):
    currentVersion: str
    latestVersion: str
    available: bool
    channel: Literal["stable", "beta"]
    prerelease: bool = False
    releaseUrl: str = ""
    downloadUrl: str = ""
    sha256: str = ""
    assetName: str = ""
    size: int = 0
    notes: str = ""
