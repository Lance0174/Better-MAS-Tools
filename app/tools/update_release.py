"""GitHub Release 元数据的纯转换与版本比较。"""

import re

from app.models.updates import UpdateCheckOut

REPOSITORY = "Lance0174/Better-MAS-Tools"
RELEASE_ROOT = f"https://github.com/{REPOSITORY}/releases"
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")


def version_key(value: str) -> tuple[int, ...] | None:
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        return None
    major, minor, patch, stage, number = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        {"alpha": 0, "beta": 1, "rc": 2, None: 3}[stage],
        int(number or 0),
    )


def select_update(
    releases: object, *, current: str, platform: str, channel: str
) -> UpdateCheckOut:
    if not isinstance(releases, list):
        raise ValueError("更新服务返回格式异常，请稍后重试")
    current_key = version_key(current)
    if current_key is None:
        raise ValueError("当前版本号无效，无法比较更新")
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = release.get("tag_name", "")
        if not isinstance(tag, str) or not tag.startswith("v"):
            continue
        version = tag[1:]
        key = version_key(version)
        if key is None or (
            channel == "stable" and (release.get("prerelease") or "-" in version)
        ):
            continue
        candidates.append((key, version, release))
    latest = max(candidates, key=lambda item: item[0]) if candidates else None
    result = UpdateCheckOut(
        currentVersion=current,
        latestVersion=latest[1] if latest else current,
        available=False,
        channel=channel,
    )
    if latest is None or latest[0] <= current_key:
        return result
    _, version, release = latest
    suffix = "android.apk" if platform == "android" else "windows-x64.exe"
    name = f"BMT-{version}-{suffix}"
    release_assets = release.get("assets")
    if not isinstance(release_assets, list):
        raise ValueError("更新安装包信息异常，请稍后重试")
    assets = [
        asset
        for asset in release_assets
        if isinstance(asset, dict)
        and asset.get("name") == name
        and asset.get("state") == "uploaded"
    ]
    if len(assets) != 1:
        raise ValueError("新版本安装包尚未完整上传，请稍后重试")
    asset = assets[0]
    expected_url = f"{RELEASE_ROOT}/download/v{version}/{name}"
    digest = asset.get("digest", "")
    size = asset.get("size", 0)
    if (
        asset.get("browser_download_url") != expected_url
        or not isinstance(digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        or type(size) is not int
        or not 0 < size <= 512 * 1024 * 1024
    ):
        raise ValueError("新版本缺少可信的下载地址或完整性信息，已停止更新")
    result.available = True
    result.prerelease = "-" in version
    result.releaseUrl = f"{RELEASE_ROOT}/tag/v{version}"
    result.downloadUrl = expected_url
    result.sha256 = digest[7:]
    result.assetName = name
    result.size = size
    result.notes = str(release.get("body") or "")[:20000]
    return result
