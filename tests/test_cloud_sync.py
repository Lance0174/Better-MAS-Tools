"""云端同步地址校验与超时预算测试：不联网、不接触真实凭据。"""

import pytest

from app.services.cloud import (
    CLOUD_CLIENT_TIMEOUT_SECONDS,
    CLOUD_SYNC_TIMEOUT_SECONDS,
    validate_cloud_url,
)


def test_cloud_url_requires_https_for_public_hosts():
    assert (
        validate_cloud_url("https://community.example.com/")
        == "https://community.example.com"
    )
    # 同步请求会先发访问密码、再发全部账号 Token，公网地址不允许明文 http。
    with pytest.raises(ValueError, match="HTTPS"):
        validate_cloud_url("http://community.example.com")


def test_cloud_url_allows_http_on_loopback_only():
    assert validate_cloud_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert validate_cloud_url("http://localhost:8000/") == "http://localhost:8000"
    assert validate_cloud_url("http://[::1]:8000") == "http://[::1]:8000"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_cloud_url("http://10.0.0.5:8000")
    with pytest.raises(ValueError, match="HTTPS"):
        validate_cloud_url("http://192.168.1.10:8000")


@pytest.mark.parametrize(
    "value",
    [
        "https://community.example.com/api",
        "https://community.example.com?token=1",
        "https://community.example.com#frag",
        "https://user:pass@community.example.com",
        "ftp://community.example.com",
        "community.example.com",
    ],
)
def test_cloud_url_rejects_non_root_or_unsupported_values(value):
    with pytest.raises(ValueError):
        validate_cloud_url(value)


def test_client_timeout_exceeds_server_budget():
    # 客户端先超时等于"云端已执行、本地结果全丢"，所以客户端预算必须更宽。
    assert CLOUD_CLIENT_TIMEOUT_SECONDS > CLOUD_SYNC_TIMEOUT_SECONDS
