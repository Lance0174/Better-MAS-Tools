"""发布签名从 PEM 证书计算，避免 SDK 展示格式影响发布门禁。"""

import base64
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "verify_android_signing",
    Path(__file__).resolve().parents[1] / "scripts/verify-android-signing.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def pem(value: bytes) -> str:
    encoded = base64.b64encode(value).decode()
    return f"-----BEGIN CERTIFICATE-----\n{encoded}\n-----END CERTIFICATE-----"


def test_certificate_digest_does_not_depend_on_sdk_labels_or_line_endings():
    certificate = b"fixture public certificate"
    digest = hashlib.sha256(certificate).hexdigest()
    output = "SDK-specific signer label\r\n" + pem(certificate).replace("\n", "\r\n")
    assert module.certificate_digests(output) == {digest}
    assert module.certificate_digests(output + "\n" + output) == {digest}
    assert module.certificate_digests("Signer certificate SHA-256: " + digest) == set()


@pytest.mark.parametrize("failure", [None, "missing", "different", "additional"])
def test_release_requires_only_the_fixed_verified_certificate(
    tmp_path, monkeypatch, failure
):
    certificate = b"fixture public certificate"
    expected = hashlib.sha256(certificate).hexdigest()
    directory = tmp_path / "android"
    directory.mkdir()
    (directory / "signing-certificate.sha256").write_text(expected)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["verify", str(tmp_path / "app.apk"), "--apksigner", "fake"]
    )
    output = pem(certificate)
    if failure == "missing":
        output = "No certificate"
    elif failure == "different":
        output = pem(b"other public certificate")
    elif failure == "additional":
        output += "\n" + pem(b"other public certificate")

    def verify(args, **options):
        assert "--print-certs-pem" in args
        assert options["check"] is True
        return subprocess.CompletedProcess(args, 0, stdout=output)

    monkeypatch.setattr(module.subprocess, "run", verify)
    if failure:
        with pytest.raises(SystemExit, match="APK 签名与固定发布证书不一致"):
            module.main()
    else:
        module.main()
