# BMT 发版流程

本文描述 BMT（更好的MAS工具）的标准发版流程。版本号与 Release 正文的唯一来源是 `CHANGELOG.md` 顶部版本段，格式固定为：

```markdown
## X.Y.Z（未发布）

### 新增

- 一条变更说明
```

分类标题固定使用：**新增 / 变更 / 优化 / 修复 / 安全**。日常开发使用 `changelog.d/` 碎片记录变更，发版时由脚本统一聚合。

## 日常开发：记录变更

合并用户可见变更（`app/`、`frontend/src/`、`frontend/electron/`、`main.py`）时，同步创建一条碎片：

```bash
python scripts/changelog.py add feat "新增某某功能"        # 新增
python scripts/changelog.py fix "修复某某问题"            # 修复
python scripts/changelog.py add perf "优化某某性能" --id 123   # 指定文件名前缀
```

- 片段文件名为 `<id>.<类型>.md`（类型：feat/change/fix/perf/security），单行内容。
- 涉及外部贡献者的修改，在发版聚合后在 CHANGELOG 条目末尾补 `（@用户名）`署名。

## 发版：一条命令聚合

1. 把 `CHANGELOG.md` 顶部版本段改为目标版本（例如 `## 0.1.5（未发布）`）；
2. 执行聚合（写发布日期、按分类归并碎片并去重、删除碎片、同步全部版本文件）：

```bash
python scripts/changelog.py release --version 0.1.5
```

3. 提交并推送：`git add -A && git commit -m "chore(release): 发布 v0.1.5。" && git push origin main`；
4. 打 tag 并推送：`git tag v0.1.5 && git push origin v0.1.5`。

### 预发布（公测）版

公测版在版本号后加 `-beta.N`，其余流程完全一致：

```markdown
## 0.2.0-beta.1（未发布）
```

```bash
python scripts/changelog.py release --version 0.2.0-beta.1
git tag v0.2.0-beta.1 && git push origin v0.2.0-beta.1
```

脚本按各生态的规则分别落盘，不要手改：

- `pyproject.toml` / `uv.lock` 保持 `0.2.0-beta.1`；PEP 440 本身接受这种写法并按 `0.2.0b1` 归一，`uv` 若把 lock 里的版本改写成 `0.2.0b1`，守门校验会按归一形式比较，不会误报。
- `frontend/package.json`、`app/version.py`、Android `versionName` 用原样字符串（npm 只认 semver 的 `0.2.0-beta.1`）。
- Android `versionCode` 由脚本换算：`主×100000 + 次×1000 + 修订×10 + 阶段位`，正式版阶段位为 9、公测版为 beta 序号减一（`beta.1` → 0），因此 `0.2.0-beta.1`(2000) 一定小于 `0.2.0`(2009)，装过公测版的用户能正常升级到正式版。
- CI 检测到版本号带 `-` 时，创建 Release 会加 `--prerelease --latest=false`：公测版不会被标成“最新版本”，正式版发布前 `Latest` 仍指向上一稳定版。

## CI 自动化

推送 `v*` 标签后触发两条发布流水线（`windows-release.yml`、`android-release.yml`）：

1. **guard 守门**：`changelog.py guard --tag` 校验 tag 与 CHANGELOG 版本一致、六处版本生成物一致（pyproject / package.json / app/version.py / uv.lock / android versionName / android versionCode）、`changelog.d` 已清空；
2. **构建**：Windows 走 `scripts/build-desktop.ps1 -Zip`，脚本本身只做 `uv sync`（锁定依赖）、`yarn install --immutable` + `yarn typecheck` + `yarn build`、PyInstaller 打包后端、`electron-builder` 出产物；`ruff`、`pytest`、`verify_upstream.py`、`yarn lint`、`yarn test` 与 `scripts/verify-desktop.py` 由同一次运行里的“Check source and desktop runtime”步骤单独执行，不在构建脚本内。Android 走 `prepare-android.py` + `./gradlew --no-daemon :app:assembleDebug :app:testDebugUnitTest :app:lintDebug`；
3. **草稿 Release**：按 `changelog.py release-note` 生成的版本段正文创建 **draft** Release，上传产物；
4. **转正**：资产上传成功后 `--draft=false` 发布。失败时 Release 保持草稿，可在 GitHub Releases 页面人工处理。

### 构建产物命名规范

| 产物 | 文件名 / Artifact 名 |
|---|---|
| Windows ZIP | `BMT-<version>-windows-x64.zip` |
| Windows 便携 EXE | `BMT-<version>-windows-x64.exe` |
| Android APK | `BMT-<version>-android.apk` |
| Windows 校验和 | `SHA256SUMS-windows-x64.txt`（与产物一同上传） |
| Android 校验和 | `SHA256SUMS-android.txt`（与产物一同上传） |
| Actions Artifact 名 | `BMT-windows-x64`（`windows-release.yml`）、`BMT-android`（`android-release.yml`） |

校验和按平台拆成两个文件，而不是共用一个 `SHA256SUMS.txt`：Release 内资产名必须唯一，两条流水线都用 `gh release upload --clobber` 上传，同名清单会互相覆盖——谁后上传，另一个平台的清单就没了。Windows 侧由 `Get-FileHash` 生成（覆盖 ZIP 与便携 EXE 两个文件），Android 侧由 `sha256sum` 生成（只含 APK）。

Release 标题统一为 `BMT vX.Y.Z`。

### 重复发版守卫

两条流水线都按“产物是否已存在”判定，而不是按 tag 是否推送过；已转正的版本不会被静默覆盖：

- **草稿阶段不限次**：Release 仍是 draft 时，重跑工作流可以用 `--clobber` 覆盖同名资产，便于修复后重推同一 tag；
- **已转正即拒绝**：Release 已转正（`isDraft=false`）且本平台产物已存在时直接失败并提示换版本号（Windows 匹配 `windows-x64` 资产名，Android 匹配 `android.apk`）；
- **允许补齐另一平台的资产**：先转正的一方发布后，另一平台此时草稿判定已是 false，但它自己的产物尚不存在，因此仍可补传，不会被守卫拦下；
- **创建 Release 允许竞态**：同一 tag 的两条流水线可能同时创建 Release，创建失败后会再查一次；查到即继续，避免把竞态判成发布失败。

## 常用命令速查

| 命令 | 用途 |
|---|---|
| `python scripts/changelog.py current` | 查看当前版本号 |
| `python scripts/changelog.py add <type> <text>` | 新建变更碎片 |
| `python scripts/changelog.py release --version X.Y.Z` | 聚合碎片并同步版本 |
| `python scripts/changelog.py release-note --version X.Y.Z` | 预览 Release 正文 |
| `python scripts/changelog.py guard --tag vX.Y.Z` | 发布前守门校验 |
| `python scripts/changelog.py sync` | 仅同步版本号到各生成物 |

## 异常处理

- **guard 失败**：按提示执行 `changelog.py sync` 或聚合碎片后重跑；
- **Release 卡在草稿**：CI 某步失败时草稿保留，修好后重推同 tag 或手动重跑即可——草稿状态不拦重复上传，本平台资产会被覆盖成新产物；
- **版本已转正但产物有问题**：守卫会拒绝覆盖已发布版本，此时改用新版本号（例如补一个修正版本），不要在 Releases 页面手改资产；
- **Android 与 Windows 先后触发同一 tag**：二者会向同一草稿 Release 补充各自产物，互不影响；创建 Release 的竞态由“失败后重查”兜住。
