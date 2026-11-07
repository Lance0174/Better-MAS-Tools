"""上游清单完整性校验：本地失败路径、反向扫描与归属文件字段。"""

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import verify_upstream

REPO_ROOT = Path(verify_upstream.__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    """与脚本同源：文本按 LF 归一后取摘要。

    Path.write_text 在 Windows 上会把换行落成 CRLF，直接对字节做哈希会让用例的结果
    取决于手里是什么系统；归一后 Windows 与 CI 走同一条路。
    """
    return verify_upstream._local_sha256(path)


def _file_entry(path: str, digest: str) -> dict:
    return {
        "path": path,
        "source": path,
        "source_sha256": "0" * 64,
        "standalone_sha256": digest,
    }


def _write_manifest(tmp_path: Path, files: list, attributed: list | None = None) -> Path:
    payload = {
        "commit": "baseline",
        "files": files,
        "synced_commits": [],
        "reference_sources": [],
    }
    if attributed is not None:
        payload["attributed_files"] = attributed
    manifest = tmp_path / "upstream-files.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return manifest


def _run(monkeypatch, root: Path, manifest: Path, *argv: str) -> int:
    monkeypatch.setattr(verify_upstream, "MANIFEST", manifest)
    monkeypatch.setattr(verify_upstream, "ROOT", root)
    monkeypatch.setattr(sys, "argv", ["verify_upstream.py", *argv])
    return verify_upstream.main()


def test_local_verification_rejects_a_changed_standalone_file(tmp_path, monkeypatch):
    local_root = tmp_path / "project"
    local_root.mkdir()
    (local_root / "sample.py").write_text("changed", encoding="utf-8")
    manifest = tmp_path / "upstream-files.json"
    manifest.write_text(
        json.dumps(
            {
                "commit": "baseline",
                "files": [
                    {
                        "path": "sample.py",
                        "source": "sample.py",
                        "source_sha256": "0" * 64,
                        "standalone_sha256": "0" * 64,
                    }
                ],
                "synced_commits": [],
                "reference_sources": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_upstream, "MANIFEST", manifest)
    monkeypatch.setattr(verify_upstream, "ROOT", local_root)
    monkeypatch.setattr(sys, "argv", ["verify_upstream.py", "--local"])

    assert verify_upstream.main() == 1


def test_reverse_scan_rejects_unregistered_adapted_file(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    (root / "app").mkdir(parents=True)
    own = root / "app" / "own.py"
    own.write_text('"""本仓独立实现。"""\n', encoding="utf-8")
    ported = root / "app" / "ported.py"
    ported.write_text(
        "# Copyright (c) 2025 MX\n"
        "# Adapted from mxyooR/Kuro_login (MIT). See docs/licenses/Kuro_login.txt.\n",
        encoding="utf-8",
    )
    manifest = _write_manifest(tmp_path, [_file_entry("app/own.py", _sha(own))])

    assert _run(monkeypatch, root, manifest, "--local") == 1
    out = capsys.readouterr().out
    assert "app/ported.py" in out
    assert "Adapted from" in out


def test_reverse_scan_accepts_registered_files_and_attributed_files(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    (root / "app" / "tools").mkdir(parents=True)
    ported = root / "app" / "tools" / "ported.py"
    ported.write_text("移植自 Priestess-bot 的 data.py（MIT License）\n", encoding="utf-8")
    attributed = root / "app" / "tools" / "geetest.py"
    attributed.write_text("# Adapted from mxyooR/Kuro_login (MIT).\n", encoding="utf-8")
    manifest = _write_manifest(
        tmp_path,
        [_file_entry("app/tools/ported.py", _sha(ported))],
        [
            {
                "path": "app/tools/geetest.py",
                "origin": "mxyooR/Kuro_login",
                "license": "MIT",
                "standalone_sha256": _sha(attributed),
                "note": "极验辅助函数",
            }
        ],
    )
    monkeypatch.setattr(sys, "argv", ["verify_upstream.py", "--local"])

    assert _run(monkeypatch, root, manifest, "--local") == 0


def test_reverse_scan_ignores_generic_wording_and_excluded_dirs(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    (root / "app").mkdir(parents=True)
    plain = root / "app" / "plain.py"
    plain.write_text(
        '"""不依赖参考项目运行环境；只调用本机 AUTO-MAS 接口。"""\n', encoding="utf-8"
    )
    # 排除目录里的同名标记不应触发失败：tests、node_modules、deploy/worker、根 data。
    for relative in (
        "tests/test_fake.py",
        "frontend/node_modules/pkg/adapted.py",
        "deploy/worker/generated.py",
        "data/cache.json",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Adapted from mxyooR/Kuro_login (MIT).\n", encoding="utf-8")
    # app/tools/data 不是运行期缓存目录，仍需扫描。
    nested = root / "app" / "tools" / "data" / "aliases.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text('{"_来源": "Priestess-bot aliases.json"}\n', encoding="utf-8")
    manifest = _write_manifest(
        tmp_path,
        [_file_entry("app/plain.py", _sha(plain))],
        [
            {
                "path": "app/tools/data/aliases.json",
                "origin": "Billtranscend/Priestess-bot",
                "license": "MIT",
                "standalone_sha256": _sha(nested),
                "note": "昵称表",
            }
        ],
    )
    monkeypatch.setattr(sys, "argv", ["verify_upstream.py", "--local"])

    assert _run(monkeypatch, root, manifest, "--local") == 0


def test_attributed_files_missing_field_is_reported(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    item = root / "sample.py"
    item.write_text("plain\n", encoding="utf-8")
    manifest = _write_manifest(
        tmp_path,
        [],
        [
            {
                "path": "sample.py",
                "origin": "mxyooR/Kuro_login",
                "license": "MIT",
                "standalone_sha256": _sha(item),
            }
        ],
    )

    assert _run(monkeypatch, root, manifest, "--local") == 1
    out = capsys.readouterr().out
    assert "attributed_files sample.py: 缺少字段 note" in out


def test_attributed_files_rejects_path_already_in_files(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    item = root / "sample.py"
    item.write_text("plain\n", encoding="utf-8")
    entry = _file_entry("sample.py", _sha(item))
    manifest = _write_manifest(
        tmp_path,
        [entry],
        [
            {
                "path": "sample.py",
                "origin": "mxyooR/Kuro_login",
                "license": "MIT",
                "standalone_sha256": _sha(item),
                "note": "重复登记",
            }
        ],
    )

    assert _run(monkeypatch, root, manifest, "--local") == 1
    assert "已在 files 中登记" in capsys.readouterr().out


def test_missing_local_file_is_reported_readably(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    manifest = _write_manifest(tmp_path, [_file_entry("removed.py", "0" * 64)])

    assert _run(monkeypatch, root, manifest, "--local") == 1
    out = capsys.readouterr().out
    assert "removed.py: 本地文件不存在" in out
    assert "请从 files 移除该条目" in out


def test_real_repository_passes_local_verification():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_upstream.py"), "--local"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "校验通过" in result.stdout
