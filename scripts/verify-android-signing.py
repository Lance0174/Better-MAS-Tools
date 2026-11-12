"""校验 APK 签名并对照仓库固定证书；不读取私钥或口令。"""

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--apksigner", type=Path)
    args = parser.parse_args()
    signer = args.apksigner
    if signer is None:
        sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
        if not sdk:
            parser.error("请设置 ANDROID_SDK_ROOT 或通过 --apksigner 指定工具")
        binary = "apksigner.bat" if os.name == "nt" else "apksigner"
        choices = list((Path(sdk) / "build-tools").glob(f"*/{binary}"))
        if not choices:
            parser.error("Android SDK 缺少 apksigner")
        signer = max(
            choices,
            key=lambda path: tuple(
                int(n) for n in re.findall(r"\d+", path.parent.name)
            ),
        )
    result = subprocess.run(
        [str(signer.resolve()), "verify", "--print-certs", str(args.apk.resolve())],
        capture_output=True,
        text=True,
        check=True,
    )
    digests = re.findall(
        r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)$",
        result.stdout,
        re.MULTILINE,
    )
    expected = (ROOT / "android/signing-certificate.sha256").read_text().strip()
    if digests != [expected]:
        raise SystemExit("APK 签名与固定发布证书不一致，拒绝发布")
    print(f"PASS: APK signature SHA-256 {expected}")


if __name__ == "__main__":
    main()
