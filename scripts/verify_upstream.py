#!/usr/bin/env python3
"""校验 docs/upstream-files.json：来源基线、本地摘要、归属文件与反向扫描。

用途：改动上游移植文件后，确认清单没有失真——
  1) 基线上游文件摘要仍与该提交一致（基线与文件对应关系未错位）；
  2) 本轮记录的上游同步提交都能在本机 AUTO-MAS 仓库中取到；
  3) 新增的上游同步文件条目字段完整；
  4) 归属文件（attributed_files）字段完整，且本地摘要与登记值一致；
  5) 反向扫描：仓库内文件头带上游标记却没登记的文件会被判失败。

反向扫描规则
------------
* 扫描后缀：``.py``、``.json``、``.ts``、``.vue``。
* 只看文件前 40 行（``HEADER_LINES``）；命中 ``MARKERS`` 中任一固定标记即视为
  上游归属：``Adapted from``、``移植自``、``Priestess-bot``、``Kuro_login``、
  ``Starward``。标记一律取项目名或固定中英文短语，不用 ``参考``、``AUTO-MAS``
  这类宽泛词——它们会命中“不依赖参考项目运行环境”“本机 AUTO-MAS 接口”等普通
  说明，造成误报。
* 跳过目录：``.git``、``.venv``、``node_modules``（含 ``frontend/node_modules``）、
  ``build``、``dist``、``local``、``tests``、``__pycache__`` 等缓存目录，以及
  ``deploy/worker`` 生成目录和仓库根的 ``data``（gitignore 的运行期缓存；
  ``app/tools/data`` 仍在扫描范围内）；跳过本清单与校验脚本自身。
* 扫描根默认是仓库根目录，可用 ``--scan-root`` 指向别处（便于测试注入临时目录）。
* 命中标记的文件必须登记在 ``files``（有上游摘要的移植文件）或
  ``attributed_files``（只有归属说明、给不出上游摘要的文件）里，否则失败并列出路径。

默认只做静态校验；仓库外需要第 1、2 项时用 --repo 指向本机 AUTO-MAS 检出。
不一致时以非零状态退出，便于放进 CI。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "upstream-files.json"
REQUIRED_FIELDS = ("path", "source", "source_sha256", "standalone_sha256")
ATTRIBUTED_FIELDS = ("path", "origin", "license", "standalone_sha256", "note")
MARKERS = ("Adapted from", "移植自", "Priestess-bot", "Kuro_login", "Starward")
HEADER_LINES = 40
SCAN_SUFFIXES = frozenset({".py", ".json", ".ts", ".vue"})
SKIP_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
        "local",
        "tests",
        "__pycache__",
        ".ruff_cache",
        ".pytest_cache",
    }
)
SKIP_ROOT_PARTS = frozenset({"data"})
SKIP_PREFIXES = ("deploy/worker", "frontend/out", "frontend/dist")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _configure_output() -> None:
    """把标准输出/错误切到 UTF-8。

    脚本会打印中文，而 Windows CI 的控制台编码是 cp1252：直接 print 会抛
    UnicodeEncodeError（pytest 调用时 PYTHONIOENCODING=utf-8 才侥幸通过）。
    这里显式指定编码与替换策略，让中文日志在任意终端都不至于把校验判成失败。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
        ".ttf", ".otf", ".woff", ".woff2", ".pdf", ".zip", ".gz", ".tar",
    }
)


def _local_sha256(path: Path) -> str:
    """本地文件摘要；文本先按 LF 归一。

    git 在 Windows 上会按 core.autocrlf 把工作区还原成 CRLF，CI 检出的却是 LF；
    不归一的话同一份内容在两边算出不同摘要，校验结果取决于谁在跑。没有扩展名的
    文本（LICENSE）也算文本，图片字体等二进制保持原样，避免替换字节时损坏内容。
    """
    data = path.read_bytes()
    if path.suffix.lower() not in BINARY_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return _sha256(data)


def _upstream_sha256(repo: Path, rev: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", f"{rev}:{path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return _sha256(result.stdout)


def _skip_scan_path(relative: Path) -> bool:
    """反向扫描的过滤：按相对路径逐段精确比对目录名，避免误伤同名子目录。"""
    if any(part in SKIP_PARTS for part in relative.parts):
        return True
    if relative.parts and relative.parts[0] in SKIP_ROOT_PARTS:
        return True
    scanned = relative.as_posix()
    return any(
        scanned == prefix or scanned.startswith(f"{prefix}/")
        for prefix in SKIP_PREFIXES
    )


def _header_marker(path: Path) -> str | None:
    """返回文件前 HEADER_LINES 行命中的第一个上游标记。"""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for index, line in enumerate(handle):
                if index >= HEADER_LINES:
                    break
                for marker in MARKERS:
                    if marker in line:
                        return marker
    except OSError:
        return None
    return None


def scan_unregistered(scan_root: Path, registered: set[str]) -> list[str]:
    """反向扫描：文件头带上游标记却未登记在清单里的文件。"""
    self_paths = {Path(__file__).resolve(), MANIFEST.resolve()}
    problems: list[str] = []
    for current, dirnames, filenames in os.walk(scan_root):
        directory = Path(current)
        relative_dir = directory.relative_to(scan_root)
        # 先剪枝再遍历，避免为了跳过 .venv / node_modules 而走进整棵树。
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not _skip_scan_path(relative_dir / name)
        )
        for name in sorted(filenames):
            candidate = directory / name
            if candidate.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if candidate in self_paths:
                continue
            marker = _header_marker(candidate)
            if marker is None:
                continue
            relative = candidate.relative_to(scan_root).as_posix()
            if relative in registered:
                continue
            problems.append(
                f"{relative}: 文件头命中上游标记 {marker!r}，"
                "但未登记在 files 或 attributed_files"
            )
    return problems


def _refresh_standalone_hashes(manifest: object) -> int:
    """就地刷新本地文件摘要，只改 ``standalone_sha256``。

    移植文件在本地被修改后，摘要必然漂移；把刷新做成脚本选项，避免手工改 JSON
    写错或漏改，也让"改完就跑一次"成为可复现操作。删除的文件不会自动删条目，
    仍然由 ``--local`` 的缺失检查提醒。
    """

    if not isinstance(manifest, dict):
        print("上游来源清单格式错误：根节点必须是对象")
        return 1
    updated = 0
    for group in ("files", "attributed_files"):
        items = manifest.get(group, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not path:
                continue
            target = ROOT / path
            if not target.is_file():
                continue
            digest = _local_sha256(target)
            if item.get("standalone_sha256") != digest:
                item["standalone_sha256"] = digest
                updated += 1
                print(f"已更新 {path}")
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"摘要刷新完成：{updated} 处变更")
    return 0


def main() -> int:
    _configure_output()
    parser = argparse.ArgumentParser(description="校验上游来源清单")
    parser.add_argument("--repo", type=Path, default=None, help="本机 AUTO-MAS 检出路径（可选）")
    parser.add_argument("--local", action="store_true", help="同时校验本地文件摘要")
    parser.add_argument(
        "--scan-root",
        type=Path,
        default=None,
        help="反向扫描的根目录（默认仓库根目录）",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="就地刷新 files/attributed_files 的 standalone_sha256（改了移植文件后使用）",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.update:
        return _refresh_standalone_hashes(manifest)
    problems: list[str] = []
    if not isinstance(manifest, dict):
        print("上游来源清单格式错误：根节点必须是对象")
        return 1
    base = manifest.get("commit", "")
    entries = manifest.get("files", [])
    if not isinstance(entries, list):
        print("上游来源清单格式错误：files 必须是数组")
        return 1

    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("files 中含有非对象条目")
            continue
        missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
        if missing:
            problems.append(f"{entry.get('path', '?')}: 缺少字段 {', '.join(missing)}")
        if args.local:
            path = entry.get("path")
            if not path:
                continue
            target = ROOT / path
            if not target.is_file():
                problems.append(
                    f"{entry['path']}: 本地文件不存在"
                    "（文件已删除请从 files 移除该条目，路径写错请修正 path）"
                )
            elif entry.get("standalone_sha256"):
                digest = _local_sha256(target)
                if digest != entry["standalone_sha256"]:
                    problems.append(
                        f"{entry['path']}: standalone_sha256 不一致"
                    )

    # 归属文件：带上游标记但给不出上游摘要，只登记本地摘要与归属说明。
    attributed = manifest.get("attributed_files", [])
    if not isinstance(attributed, list):
        problems.append("attributed_files 必须是数组")
        attributed = []
    known_paths = {
        entry.get("path") for entry in entries if isinstance(entry, dict)
    }
    seen_attributed: set[str] = set()
    for item in attributed:
        if not isinstance(item, dict):
            problems.append("attributed_files 中含有非对象条目")
            continue
        missing = [field for field in ATTRIBUTED_FIELDS if not item.get(field)]
        if missing:
            problems.append(
                f"attributed_files {item.get('path', '?')}: "
                f"缺少字段 {', '.join(missing)}"
            )
        path = item.get("path")
        if not path:
            continue
        if path in known_paths:
            problems.append(f"{path}: 已在 files 中登记，attributed_files 不应重复")
        elif path in seen_attributed:
            problems.append(f"{path}: attributed_files 中重复登记")
        seen_attributed.add(path)
        if not args.local:
            continue
        target = ROOT / path
        if not target.is_file():
            problems.append(
                f"{path}: 本地文件不存在"
                "（文件已删除请从 attributed_files 移除该条目，路径写错请修正 path）"
            )
        elif item.get("standalone_sha256"):
            digest = _local_sha256(target)
            if digest != item["standalone_sha256"]:
                problems.append(f"{path}: standalone_sha256 不一致")

    registered = {path for path in known_paths if isinstance(path, str)}
    registered |= seen_attributed
    scan_root = (args.scan_root or ROOT).resolve()
    if scan_root.is_dir():
        problems.extend(scan_unregistered(scan_root, registered))

    synced = manifest.get("synced_commits", [])
    if not isinstance(synced, list):
        problems.append("synced_commits 必须是数组")
        synced = []
    for item in synced:
        if not isinstance(item, dict):
            problems.append("synced_commits 中含有非对象条目")
            continue
        for field in ("commit", "subject", "files", "summary"):
            if not item.get(field):
                problems.append(f"synced_commits {item.get('commit', '?')}: 缺少字段 {field}")

    recorded = sum(
        1
        for entry in entries
        if isinstance(entry, dict) and entry.get("synced_source_sha256")
    )
    if synced and recorded == 0:
        problems.append("已记录 synced_commits，但没有任何文件写入 synced_source_sha256")

    # 协议/数据源参考条目：只有名称、地址与用途，不登记文件摘要（未复制代码）。
    references = manifest.get("reference_sources", [])
    for item in references if isinstance(references, list) else []:
        if not isinstance(item, dict):
            problems.append("reference_sources 中含有非对象条目")
            continue
        for field in ("name", "url", "usage", "license"):
            if not item.get(field):
                problems.append(f"reference_sources {item.get('name', '?')}: 缺少字段 {field}")

    if args.repo is not None:
        repo = args.repo
        base_commit = manifest.get("commit")
        if not base_commit:
            problems.append("manifest 缺少基线 commit")
        else:
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("source"):
                    continue
                digest = _upstream_sha256(repo, base_commit, entry.get("source", ""))
                if digest is None:
                    problems.append(
                        f"基线上游缺少文件: {base_commit} {entry.get('source', '?')}"
                    )
                elif digest != entry.get("source_sha256"):
                    problems.append(
                        f"{entry['path']}: source_sha256 与基线提交不一致"
                    )
        for item in synced:
            if not isinstance(item, dict) or not item.get("commit"):
                continue
            files = item.get("files", [])
            if not isinstance(files, list):
                continue
            for synced_path in files:
                digest = _upstream_sha256(repo, item["commit"], synced_path)
                if digest is None:
                    problems.append(
                        f"上游仓库缺少提交或文件: {item['commit']} {synced_path}"
                    )
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            if not entry.get("synced_source_sha256"):
                continue
            item = None
            for candidate in synced:
                candidate_files = (
                    candidate.get("files", []) if isinstance(candidate, dict) else []
                )
                if isinstance(candidate_files, list) and entry["path"] in candidate_files:
                    item = candidate
                    break
            if item is None:
                problems.append(f"{entry['path']}: 有 synced_source_sha256 但未登记所属提交")
                continue
            synced_from = entry.get("synced_from")
            if not synced_from:
                problems.append(f"{entry['path']}: 缺少 synced_from")
                continue
            digest = _upstream_sha256(repo, synced_from, entry["source"])
            if digest is None:
                problems.append(
                    f"{entry['path']}: synced_from 中不存在该文件"
                )
            elif digest != entry["synced_source_sha256"]:
                problems.append(
                    f"{entry['path']}: synced_source_sha256 与 synced_from 不一致"
                )

    if problems:
        print("上游来源清单校验失败：")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        f"上游来源清单校验通过：基线 {base[:12]}，"
        f"{len(entries)} 个文件，{len(attributed)} 个归属文件，"
        f"{len(synced)} 个同步提交记录。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
