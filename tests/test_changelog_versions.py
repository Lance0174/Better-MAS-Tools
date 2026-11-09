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

def test_sync_writes_prerelease_version_to_generated_files(tmp_path, monkeypatch) -> None:
    """sync 必须能把带预发布后缀的版本写进全部生成物（uv.lock 曾因正则只认数字而漏改）。"""
    (tmp_path / "frontend").mkdir()
    (tmp_path / "android" / "app").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.2.0-beta.1"\n', encoding="utf-8")
    (tmp_path / "frontend" / "package.json").write_text('{\n  "version": "0.2.0-beta.1"\n}\n', encoding="utf-8")
    (tmp_path / "android" / "app" / "build.gradle.kts").write_text(
        'versionCode = 2000\nversionName = "0.2.0-beta.1"\n', encoding="utf-8"
    )
    (tmp_path / "app" / "version.py").write_text('VERSION = "0.2.0-beta.1"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "better-mas-tools"\nversion = "0.2.0-beta.1"\nsource = { editable = "." }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(changelog, "ROOT", tmp_path)

    changed = changelog.sync("0.2.0-beta.2")

    assert "uv.lock" in changed
    assert 'version = "0.2.0-beta.2"' in (tmp_path / "uv.lock").read_text(encoding="utf-8")
    assert 'version = "0.2.0-beta.2"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'versionCode = 2001' in (tmp_path / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
