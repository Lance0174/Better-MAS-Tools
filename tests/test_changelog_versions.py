"""发版版本号解析：预发布归一、Android versionCode 单调、版本行格式。"""

from scripts import changelog


def test_version_line_accepts_stable_and_prerelease() -> None:
    assert changelog.VERSION_LINE.match("## 0.1.5（2026-09-20）")
    assert changelog.VERSION_LINE.match("## 0.2.0-beta.1（未发布）")
    assert changelog.VERSION_LINE.match("## 0.2.0-beta.10（2026-11-07）")


def test_version_line_rejects_malformed_headers() -> None:
    assert not changelog.VERSION_LINE.match("## 0.2（未发布）")
    assert not changelog.VERSION_LINE.match("## 0.2.0 未发布")
    assert not changelog.VERSION_LINE.match("## 0.2.0-beta.1")


def test_normalize_pep440_matches_uv_and_pip_spelling() -> None:
    assert changelog.normalize_pep440("0.2.0-beta.1") == "0.2.0b1"
    assert changelog.normalize_pep440("0.2.0b1") == "0.2.0b1"
    assert changelog.normalize_pep440("0.2.0-rc.2") == "0.2.0rc2"
    assert changelog.normalize_pep440("0.2.0-alpha.3") == "0.2.0a3"
    assert changelog.normalize_pep440("0.1.5") == "0.1.5"


def test_android_version_code_orders_prerelease_before_stable() -> None:
    beta1 = changelog.android_version_code("0.2.0-beta.1")
    beta2 = changelog.android_version_code("0.2.0-beta.2")
    stable = changelog.android_version_code("0.2.0")
    assert beta1 < beta2 < stable
    assert beta1 == 2000
    assert stable == 2009


def test_android_version_code_is_monotonic_across_versions() -> None:
    codes = [
        changelog.android_version_code("0.1.5"),
        changelog.android_version_code("0.2.0-beta.1"),
        changelog.android_version_code("0.2.0"),
        changelog.android_version_code("0.2.1"),
        changelog.android_version_code("0.10.0"),
        changelog.android_version_code("1.0.0"),
    ]
    assert codes == sorted(codes)
    assert len(set(codes)) == len(codes)
