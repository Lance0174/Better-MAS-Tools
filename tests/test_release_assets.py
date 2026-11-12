"""两平台发布门禁，使用假资产与内存摘要，不访问 GitHub。"""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "finalize_release",
    Path(__file__).resolve().parents[1] / "scripts/finalize-release.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_release_lookup_includes_drafts_on_later_pages():
    draft = {"tag_name": "v0.2.0-beta.4", "draft": True}
    pages = [[{"tag_name": "v0.2.0-beta.2", "draft": False}], [draft]]
    assert module.find_release(pages, "v0.2.0-beta.4") == draft


@pytest.mark.parametrize("duplicate", [False, True])
def test_release_lookup_rejects_missing_or_ambiguous_tags(duplicate):
    release = {"tag_name": "v0.2.0-beta.4", "draft": True}
    pages = [[release], [release]] if duplicate else [[]]
    with pytest.raises(ValueError, match="唯一"):
        module.find_release(pages, "v0.2.0-beta.4")


def fixture():
    version = "0.2.0-beta.4"
    files = [
        f"BMT-{version}-android.apk",
        f"BMT-{version}-windows-x64.exe",
        f"BMT-{version}-windows-x64.zip",
    ]
    assets = [
        {"name": name, "size": 100, "state": "uploaded", "digest": "sha256:" + "a" * 64}
        for name in files + ["SHA256SUMS-android.txt", "SHA256SUMS-windows-x64.txt"]
    ]
    manifests = {
        "SHA256SUMS-android.txt": "a" * 64 + "  " + files[0],
        "SHA256SUMS-windows-x64.txt": "\n".join(
            "a" * 64 + "  " + name for name in files[1:]
        ),
    }
    return assets, manifests


def test_complete_assets_match_both_platform_manifests():
    assets, manifests = fixture()
    module.verify_assets(assets, version="0.2.0-beta.4", manifests=manifests)


@pytest.mark.parametrize(
    "failure", ["missing", "duplicate", "digest", "wrong_platform", "missing_manifest"]
)
def test_incomplete_or_mismatched_release_is_blocked(failure):
    assets, manifests = fixture()
    if failure == "missing":
        assets.pop()
    elif failure == "duplicate":
        assets.append(assets[0].copy())
    elif failure == "digest":
        assets[0]["digest"] = "sha256:" + "b" * 64
    elif failure == "wrong_platform":
        manifests["SHA256SUMS-android.txt"] = manifests["SHA256SUMS-windows-x64.txt"]
    else:
        manifests.pop("SHA256SUMS-android.txt")
    with pytest.raises(ValueError):
        module.verify_assets(assets, version="0.2.0-beta.4", manifests=manifests)
