# Contributing

完整分支模型与发布流程见 [docs/branching.md](docs/branching.md)。

## 开发流程

1. 从最新 `develop` 创建 `feature/<issue>-<slug>` 或 `bugfix/<issue>-<slug>`。
2. 新功能先写失败测试，再写实现。
3. 提交前运行 `make lint && make test`。
4. 向 `develop` 提 PR；CI 全绿、review 通过后 Squash merge。
5. 发布走 `release/<version>` → `main`，合并后打 `v*` Tag。

## 提交规范

使用 Conventional Commits，例如：

```text
feat: add qianchuan ad cost adapter
fix: preserve watermark on backfill
docs: document CSV mappings
```

## 禁止事项

- 不直接 push `main` / `develop`。
- 不提交真实店铺 ID、手机号、密钥、平台 Token。
- 不修改已进入 `main` 的数据库迁移文件，只能新增迁移。
