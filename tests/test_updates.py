"""离线软件更新元数据回归，不下载或执行安装包。"""

import pytest
import httpx

from app.tools.update_release import RELEASE_ROOT, select_update, version_key


def release(version="0.2.0-beta.4", *, platform="android", **overrides):
    name = (
        f"BMT-{version}-{'android.apk' if platform == 'android' else 'windows-x64.exe'}"
    )
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": "-" in version,
        "body": "更新说明",
        "assets": [
            {
                "name": name,
                "state": "uploaded",
                "size": 123,
                "browser_download_url": f"{RELEASE_ROOT}/download/v{version}/{name}",
                "digest": "sha256:" + "a" * 64,
            }
        ],
        **overrides,
    }


def test_versions_handle_release_stages_and_multi_digit_numbers():
    values = [
        "0.2.0-alpha.1",
        "0.2.0-beta.2",
        "0.2.0-beta.10",
        "0.2.0-rc.1",
        "0.2.0",
        "0.2.1",
    ]
    assert sorted(reversed(values), key=version_key) == values
    assert version_key("0.2.0;execute") is None


def test_beta_channel_includes_stable_but_does_not_downgrade():
    output = select_update(
        [release(), release("0.2.0")],
        current="0.2.0-beta.3",
        platform="android",
        channel="beta",
    )
    assert output.available and output.latestVersion == "0.2.0"
    assert not select_update(
        [release()], current="0.2.0", platform="android", channel="beta"
    ).available


def test_stable_channel_ignores_drafts_and_prereleases():
    output = select_update(
        [release(), release("1.0.0", draft=True), release("0.1.5")],
        current="0.1.5",
        platform="android",
        channel="stable",
    )
    assert output.available is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("browser_download_url", "https://evil.test/update.apk"),
        ("digest", None),
        ("size", 0),
        ("size", 9999999999),
    ],
)
def test_invalid_asset_is_never_offered(field, value):
    item = release()
    item["assets"][0][field] = value
    with pytest.raises(ValueError):
        select_update(
            [item], current="0.2.0-beta.2", platform="android", channel="beta"
        )


@pytest.mark.parametrize("assets", [None, {}, "unexpected"])
def test_malformed_asset_collection_has_actionable_error(assets):
    with pytest.raises(ValueError, match="安装包信息异常"):
        select_update(
            [release(assets=assets)],
            current="0.2.0-beta.2",
            platform="android",
            channel="beta",
        )


@pytest.mark.asyncio
async def test_check_uses_official_api_without_account_credentials(monkeypatch):
    from app.services import updates

    def handler(request):
        assert request.url.host == "api.github.com"
        assert (
            "authorization" not in request.headers and "cookie" not in request.headers
        )
        return httpx.Response(200, json=[release("9.0.0")])

    monkeypatch.setattr(
        updates.network,
        "client",
        lambda **options: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await updates.check_updates(platform="android", channel="stable")
    assert result.available and result.sha256 == "a" * 64
