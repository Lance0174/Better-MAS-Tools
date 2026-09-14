"""准备 Android 离线资源；只打包源码和锁定的公共依赖，不读取用户配置。"""

import argparse
import base64
import csv
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


def frontend_licenses(directory: Path) -> None:
    """附带生产依赖的许可与版本，保留其原始文本。"""
    modules = ROOT / "frontend/node_modules"
    pending = list(
        json.loads((ROOT / "frontend/package.json").read_text())["dependencies"]
    )
    seen = {}
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        package = modules / name
        metadata = package / "package.json"
        if not metadata.is_file():
            raise RuntimeError(f"前端许可依赖缺失：{name}")
        data = json.loads(metadata.read_text(encoding="utf-8"))
        seen[name] = {"version": data.get("version"), "license": data.get("license")}
        destination = directory / name
        destination.mkdir(parents=True, exist_ok=True)
        for source in package.iterdir():
            if source.name.lower().startswith(
                ("license", "licence", "notice", "copying")
            ):
                if source.is_file():
                    shutil.copy2(source, destination)
                elif source.is_dir():
                    shutil.copytree(
                        source, destination / source.name, dirs_exist_ok=True
                    )
        pending.extend(data.get("dependencies", {}))
    (directory / "packages.json").write_text(
        json.dumps(seen, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-cache", type=Path, default=ROOT / "local/android-cache/runtime"
    )
    parser.add_argument(
        "--python-cache",
        type=Path,
        help="可选的已安装纯 Python 包缓存，逐文件校验 RECORD",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--proxy", help="只对本次资源下载生效")
    args = parser.parse_args()
    manifest = json.loads((ANDROID / "runtime/manifest.json").read_text())
    cache = args.runtime_cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    base = f"https://cdn.jsdelivr.net/pyodide/v{manifest['pyodide']}/full/"

    def obtain(
        filename: str,
        digest: str,
        *,
        url: str | None = None,
        alternate: str | None = None,
    ) -> bytes:
        target = cache / filename
        accepted = {digest, alternate} - {None}
        if target.is_file():
            data = target.read_bytes()
            if hashlib.sha256(data).hexdigest() in accepted:
                return data
        if args.offline:
            raise RuntimeError(f"离线缓存缺失或校验失败：{filename}")
        with httpx.Client(
            proxy=args.proxy, trust_env=False, timeout=60, follow_redirects=True
        ) as client:
            response = client.get(url or base + filename)
            response.raise_for_status()
            data = response.content
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"下载校验失败：{filename}")
        target.write_bytes(data)
        return data

    if not args.skip_frontend:
        subprocess.run(
            ["node", "node_modules/vite/bin/vite.js", "build"],
            cwd=ROOT / "frontend",
            check=True,
        )
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("请先构建 frontend")
    output = (ANDROID / "app/src/main/assets").resolve()
    expected = ROOT / "android/app/src/main/assets"
    if output != expected or not output.is_relative_to(ANDROID.resolve()):
        raise RuntimeError("拒绝覆盖非 Android 生成资源目录")
    staging_parent = ROOT / "local/android-build"
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=staging_parent) as temporary:
        staging = Path(temporary)
        shutil.copytree(ROOT / "frontend/dist", staging, dirs_exist_ok=True)
        runtime = staging / "runtime"
        runtime.mkdir()
        lock = json.loads((ANDROID / "runtime/pyodide-lock.json").read_text())
        provenance = []
        for item in manifest["runtime"]:
            (runtime / item["file"]).write_bytes(obtain(item["file"], item["sha256"]))
        for item in manifest["packages"]:
            data = obtain(
                item["file"], item["sha256"], alternate=item.get("repackedSha256")
            )
            digest = hashlib.sha256(data).hexdigest()
            lock["packages"][item["name"]]["sha256"] = digest
            (runtime / item["file"]).write_bytes(data)
            provenance.append(
                {
                    "name": item["name"],
                    "sha256": digest,
                    "repacked": digest != item["sha256"],
                }
            )
        (runtime / "pyodide-lock.json").write_text(json.dumps(lock), encoding="utf-8")
        shutil.copy2(ANDROID / "runtime/engine-worker.js", runtime)
        with zipfile.ZipFile(
            runtime / "python-source.zip", "w", zipfile.ZIP_DEFLATED
        ) as bundle:

            def add(name: str, data: bytes) -> None:
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, data)

            for source in sorted((ROOT / "app").rglob("*.py")):
                add(source.relative_to(ROOT).as_posix(), source.read_bytes())
            for item in manifest["pure"]:
                if args.python_cache:
                    module_cache = args.python_cache.resolve()
                    record = (
                        module_cache
                        / f"{item['name'].replace('-', '_')}-{item['version']}.dist-info/RECORD"
                    )
                    for name, checksum, _size in csv.reader(
                        io.StringIO(record.read_text())
                    ):
                        source = (module_cache / name).resolve()
                        if (
                            not source.is_relative_to(module_cache)
                            or source.suffix.lower() in {".pyc", ".exe", ".dll", ".so"}
                            or Path(name).parts[0] in {"bin", "Scripts"}
                        ):
                            continue
                        if not checksum:
                            continue  # 不引入本机生成的 INSTALLER、脚本和缓存。
                        algorithm, digest = checksum.split("=", 1)
                        data = source.read_bytes()
                        actual = (
                            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
                            .decode()
                            .rstrip("=")
                        )
                        if algorithm != "sha256" or actual != digest:
                            raise RuntimeError(
                                f"纯 Python 缓存校验失败：{item['name']}/{name}"
                            )
                        add("site/" + name, data)
                else:
                    filename = item["url"].rsplit("/", 1)[1]
                    wheel = obtain(filename, item["sha256"], url=item["url"])
                    with zipfile.ZipFile(io.BytesIO(wheel)) as package:
                        for name in sorted(package.namelist()):
                            if (
                                name.endswith("/")
                                or ".." in Path(name).parts
                                or name.startswith("/")
                            ):
                                continue
                            add("site/" + name, package.read(name))
        licenses = staging / "licenses"
        licenses.mkdir(exist_ok=True)
        for name in ("LICENSE", "NOTICE.md"):
            shutil.copy2(ROOT / name, licenses)
        shutil.copytree(ROOT / "docs/licenses", licenses / "docs/licenses")
        shutil.copy2(ANDROID / "runtime/LICENSE-Pyodide.txt", licenses)
        frontend_licenses(licenses / "frontend")
        (licenses / "android-runtime.json").write_text(
            json.dumps({"manifest": manifest, "packages": provenance}, indent=2),
            encoding="utf-8",
        )
        if output.exists():
            shutil.rmtree(output)  # 已校验为唯一的、被 gitignore 排除的生成资源目录。
        shutil.copytree(staging, output)
    print(f"Android 离线资源已准备：{output}")


if __name__ == "__main__":
    main()
