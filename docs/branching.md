# 分支管理规范（企业级）

本项目采用「主干 + 集成分支 + 短生命周期功能分支」模型。目标是让 `main` 始终可部署、让 `develop` 始终可集成，同时保持发布与热修复路径清晰。

## 1. 分支模型

| 分支 | 用途 | 生命周期 | 合并来源 | 合并目标 |
|---|---|---|---|---|
| `main` | 生产可部署基线 | 长期 | `release/*`、`hotfix/*` | — |
| `develop` | 日常集成 | 长期 | `feature/*`、`bugfix/*` | `release/*` |
| `feature/<issue>-<slug>` | 新功能 | 短（建议 ≤ 2 周） | `develop` | `develop` |
| `bugfix/<issue>-<slug>` | 非紧急缺陷 | 短 | `develop` | `develop` |
| `release/<version>` | 发布冻结 | 短 | `develop` | `main` + `develop` |
| `hotfix/<version>` | 生产紧急修复 | 短 | `main` | `main` + `develop` |
| `support/<version>` | 可选 LTS 维护 | 长期 | `main` | `main` |

约束：

- 不使用 `staging` / `prod` 等环境分支；环境由 Tag + 部署系统区分。
- `main`、`develop` 禁止直接 push，必须走 PR。
- `feature/*` / `bugfix/*` 合并后删除，避免分支堆积。
- 数据库迁移文件一旦进入 `main` 不得修改，只能新增迁移。

## 2. 当前仓库映射

| 分支 | 当前状态 |
|---|---|
| `main` | M0 骨架 + M1 接入层基线，已推送 |
| `develop` | 与 `main` 同基线，后续功能从此外拉 |
| `feature/m0-skeleton` | 历史功能分支，M0+M1 提交来源；确认后可删除 |

建议下一发布版本为 `v0.2.0`（M1 接入层）。打 Tag 前先走一次 `release/v0.2.0` 流程。

## 3. 命名规范

- 全小写，单词用 `-` 分隔，不使用中文、空格、姓名。
- 必须带 Issue 编号（有 Issue 时）：`feature/123-douyin-order-adapter`。
- 版本号使用 SemVer：`release/v0.2.0`、`hotfix/v0.2.1`。
- 示例：
  - `feature/45-m2-dwd-model`
  - `bugfix/67-csv-window-filter`
  - `release/v0.2.0`
  - `hotfix/v0.2.1`

## 4. 标准流程

### 功能开发

1. 从最新 `develop` 创建 `feature/<issue>-<slug>`。
2. 小步提交；每天至少同步一次 `develop`（rebase 或 merge，团队内统一）。
3. 先写失败测试，再实现；本地跑 `make lint && make test`。
4. 推送分支，向 `develop` 提 PR。
5. CI 全绿 + 至少 1 名 reviewer 批准后，使用 **Squash merge** 合入。
6. 删除功能分支。

### 发布

1. 从 `develop` 切 `release/<version>`。
2. 冻结功能，只接受发布阻塞类修复；更新 CHANGELOG 与版本号。
3. 发布 PR：`release/<version>` → `main`。
4. `main` 合并后打 annotated tag（如 `v0.2.0`）。
5. 将 `release/<version>` 合回 `develop`，删除 release 分支。
6. 部署由 Tag 触发，不从分支名推断环境。

### 热修复

1. 从 `main` 切 `hotfix/<version>`。
2. 只修生产问题，补回归测试。
3. PR → `main`，合并后打 patch Tag。
4. 同一提交合回 `develop`，避免版本漂移。

## 5. PR 准入标准

- 标题符合 Conventional Commits，例如 `feat: add qianchuan ad cost adapter`。
- 描述包含：变更说明、影响范围、测试方式、风险与回滚、数据库迁移说明。
- CI 必须通过：
  - `uv lock --check`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run alembic upgrade head`（MySQL service）
  - `uv run pytest -q`（含集成测试）
  - `docker compose config --quiet`
- 至少 1 名 reviewer；`release/*`、`hotfix/*`、安全相关改动建议 2 名。
- 所有 review comment 已解决；不允许 force push 覆盖他人提交。
- 合入方式统一 Squash，保持 `main` / `develop` 线性可读。

## 6. 分支保护（GitHub 手动设置）

仓库 Settings → Branches → Add branch protection rule，对 `main` 和 `develop` 分别设置：

- Require a pull request before merging
  - Required approvals: 1（`main` 建议 2）
  - Dismiss stale pull request approvals when new commits are pushed
- Require status checks to pass before merging
  - 选择 CI job（`test`）
  - Require branches to be up to date before merging
- Require conversation resolution before merging
- Require linear history
- Do not allow bypassing the above settings
- Restrict deletions
- Block force pushes

同时：

- Settings → General → Default branch 设为 `main`。
- 开启「Automatically delete head branches」。
- 开启 Dependabot alerts / security updates。
- 只有维护者拥有 `main` 的 merge 权限。

## 7. CI/CD 分层

| 触发 | 内容 |
|---|---|
| PR → `develop` / `main` | lint、类型、单元测试、MySQL 集成测试、compose 配置校验 |
| push → `develop` | 同 PR，保证集成基线可用 |
| push → `main` / Tag | 构建镜像、生成 Release Notes、部署生产（后续接入 Registry） |
| Tag `v*` | 发布制品与变更日志 |

后续接入镜像仓库时，在 `.github/workflows/release.yml` 中增加：

- Docker build + push
- SBOM / 漏洞扫描
- Release Notes 自动生成
- 部署审批（GitHub Environments）

## 8. 提交规范

使用 Conventional Commits：

```text
<type>(<scope>): <subject>

<body>

<footer>
```

常用 type：

- `feat`：新功能
- `fix`：缺陷修复
- `docs`：文档
- `test`：测试
- `refactor`：重构（不改变行为）
- `perf`：性能
- `build` / `ci`：构建与流水线
- `chore`：杂项

约束：

- 一个提交只做一件事；禁止 WIP 提交进入 `main` / `develop`。
- 提交信息用英文 subject，正文可用中文。
- 不提交 `.env`、真实店铺 ID、手机号、平台 Token、密钥。
- 破坏性变更在 footer 写 `BREAKING CHANGE:`。

## 9. 版本与发布

- 遵循 SemVer：`MAJOR.MINOR.PATCH`。
- `0.x` 阶段允许不兼容变更，但必须在 CHANGELOG 标注。
- Tag 使用 annotated tag：`git tag -a v0.2.0 -m "M1 ingestion"`。
- 每次发布更新 `CHANGELOG.md`，至少包含：新增、修复、迁移、已知限制。
- 数据库迁移必须可在空库和上一版本库上执行；发布说明写清迁移顺序与回滚方式。

## 10. 安全与合规

- 所有密钥走 GitHub Secrets 或环境变量，不进入仓库。
- 分支保护覆盖管理员，避免误操作。
- 依赖升级走 PR，CI 必须通过。
- 开源发布前跑脱敏检查：公司名、真实 UID、手机号、IP、密钥模式。
- 安全修复可走私有分支 + 协调披露，合并后再公开细节。
