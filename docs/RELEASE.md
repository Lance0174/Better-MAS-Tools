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

## CI 自动化

推送 `v*` 标签后触发两条发布流水线（`windows-release.yml`、`android-release.yml`）：

1. **guard 守门**：`changelog.py guard --tag` 校验 tag 与 CHANGELOG 版本一致、五处版本生成物一致（pyproject / package.json / app/version.py / uv.lock / android versionName）、`changelog.d` 已清空；
2. **构建**：Windows 走 `build-desktop.ps1 -Zip`（typecheck/test/lint/verify-desktop 全跑），Android 走 prepare-android + gradle；
3. **草稿 Release**：按 `changelog.py release-note` 生成的版本段正文创建 **draft** Release，上传产物；
4. **转正**：资产上传成功后 `--draft=false` 发布。失败时 Release 保持草稿，可在 GitHub Releases 页面人工处理。

### 构建产物命名规范

| 产物 | 文件名 |
|---|---|
| Windows ZIP | `BMT-<version>-windows-x64.zip` |
| Windows 便携 EXE | `BMT-<version>-windows-x64.exe` |
| Android APK | `BMT-<version>-android.apk` |
| 校验和 | `SHA256SUMS.txt`（与产物一同上传） |

Release 标题统一为 `BMT vX.Y.Z`。

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
- **Release 卡在草稿**：CI 某步失败时草稿保留，修复后重推同 tag 会让 Windows 侧守门拒绝——此时在 GitHub Releases 页面删除草稿 Release 与 tag 后重新打 tag；
- **Android 与 Windows 先后触发同一 tag**：二者会向同一草稿 Release 补充各自产物，互不影响。
