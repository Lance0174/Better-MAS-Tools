"""两平台均成功、五份资产与摘要齐全后才公开 Release。"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gh(*args: str) -> bytes:
    return subprocess.run(
        ["gh", *args], cwd=ROOT, capture_output=True, check=True
    ).stdout


def verify_assets(
    assets: list[dict], *, version: str, manifests: dict[str, str]
) -> None:
    expected = {
        f"BMT-{version}-windows-x64.exe",
        f"BMT-{version}-windows-x64.zip",
        f"BMT-{version}-android.apk",
        "SHA256SUMS-windows-x64.txt",
        "SHA256SUMS-android.txt",
    }
    indexed = {asset["name"]: asset for asset in assets}
    if set(indexed) != expected or len(assets) != len(expected):
        raise ValueError("发布资产缺失、重复或包含意外文件")
    for asset in assets:
        if (
            asset.get("state") != "uploaded"
            or not asset.get("size")
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", asset.get("digest") or "")
        ):
            raise ValueError("发布资产未就绪或缺少摘要")
    checked = set()
    for name, content in manifests.items():
        # 使用原始下载字节的摘要由调用方验证；文本这里只检查每个平台的文件归属。
        allowed = (
            {f"BMT-{version}-android.apk"}
            if name == "SHA256SUMS-android.txt"
            else {f"BMT-{version}-windows-x64.exe", f"BMT-{version}-windows-x64.zip"}
        )
        rows = set()
        for row in content.lstrip("\ufeff").splitlines():
            match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(\S+)", row)
            if match is None:
                raise ValueError("摘要清单格式无效")
            digest, filename = match.groups()
            if (
                filename not in allowed
                or filename in rows
                or indexed[filename]["digest"] != f"sha256:{digest.lower()}"
            ):
                raise ValueError("摘要与平台发布资产不符")
            rows.add(filename)
        if rows != allowed:
            raise ValueError("摘要清单未覆盖平台产物")
        checked.update(rows)
    if checked != expected - set(manifests):
        raise ValueError("发布摘要不完整")


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    prefix = f"repos/{repository}"
    run = json.loads(gh("api", f"{prefix}/actions/runs/{os.environ['RELEASE_RUN_ID']}"))
    tag = run["head_branch"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", tag):
        print("Not a version tag; nothing to publish")
        return
    sha = os.environ["RELEASE_SHA"]
    commit = subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if commit != sha or run["head_sha"] != sha:
        raise ValueError("Tag 与构建提交不一致")
    for workflow in ("windows-release.yml", "android-release.yml"):
        runs = json.loads(
            gh(
                "api",
                f"{prefix}/actions/workflows/{workflow}/runs?head_sha={sha}&per_page=30",
            )
        )["workflow_runs"]
        matching = [
            item
            for item in runs
            if item["head_sha"] == sha
            and item["head_branch"] == tag
            and item["event"] == "push"
        ]
        latest = max(matching, key=lambda item: item["id"]) if matching else None
        if (
            latest is None
            or latest["status"] != "completed"
            or latest["conclusion"] != "success"
        ):
            print(f"Waiting for successful {workflow}; release remains a draft")
            return
    subprocess.run(
        [sys.executable, "scripts/changelog.py", "guard", "--tag", tag],
        cwd=ROOT,
        check=True,
    )
    release = json.loads(gh("api", f"{prefix}/releases/tags/{tag}"))
    if not release["draft"]:
        print("Release already public; no changes made")
        return
    notes = subprocess.run(
        [sys.executable, "scripts/changelog.py", "release-note", "--version", tag[1:]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    if release["body"].strip() != notes.strip() or release["prerelease"] != (
        "-" in tag
    ):
        raise ValueError("Release 说明或预发布状态不符")
    manifests = {}
    for asset in release["assets"]:
        if asset["name"] in {"SHA256SUMS-android.txt", "SHA256SUMS-windows-x64.txt"}:
            import hashlib

            content = gh(
                "api",
                f"{prefix}/releases/assets/{asset['id']}",
                "-H",
                "Accept: application/octet-stream",
            )
            if len(
                content
            ) > 4096 or f"sha256:{hashlib.sha256(content).hexdigest()}" != asset.get(
                "digest"
            ):
                raise ValueError("摘要清单下载校验失败")
            manifests[asset["name"]] = content.decode("utf-8-sig")
    verify_assets(release["assets"], version=tag[1:], manifests=manifests)
    gh("release", "edit", tag, "--draft=false", "--repo", repository)
    print(f"Published {tag}: both platforms succeeded and five assets verified")


if __name__ == "__main__":
    main()
