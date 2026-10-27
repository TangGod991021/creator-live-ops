# creator-live-ops

达人店播经营数据底座。用 Python + FastAPI 重做电商数据采集与数仓编排，v1 聚焦抖音平台的达人与店播经营分析。

## 能力边界

- ✅ 抖音官方开放平台：订单、售后、结算、直播时段、千川消耗
- ✅ 达人 × 店播统一数据模型与指标口径
- ✅ 单库分层前缀；多 schema 为预留能力（M0 仅验证 `single_db`）
- ✅ 按凭证分车道调度，车道内串行、车道间并行
- ✅ 敏感配置应用层加密、默认掩码
- ⛔ v1 不做小红书/微信小店（留接口）
- ⛔ v1 不做星图合作数据（留预留表）
- ⛔ v1 不做直播间流量指标（只做成交/退款/单量/消耗）
- ⛔ v1 不含业务前端，只提供数据 API 与 Metabase 示例看板

## 快速开始

```bash
cp .env.example .env
KEY=$(uv run python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())")
sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$KEY|" .env
uv sync
docker compose up -d --build
curl http://127.0.0.1:8000/health
curl -H "X-API-Key: change-me" http://127.0.0.1:8000/api/v1/jobs
```

> `API_KEY` 在 dev 默认为 `change-me`；生产环境必须改为强随机值，且 `ENCRYPTION_KEY` 不能为空。

## M1 接入

```bash
# 可选：配置抖店/千川凭证后，把对应 jobs/*.yml 的 enabled 改为 true
cp .env.example .env

# CSV 兜底：把导出文件放到 data/csv/<dataset>/*.csv
uv run python -m app.executor.cli --job csv_live_rooms_daily
```

字段映射、凭证优先级、补数和水位规则见 [docs/ingestion.md](docs/ingestion.md)。

## 开发

```bash
make test          # 单元测试
make lint          # ruff + mypy
make migrate       # 数据库迁移
docker compose up -d mysql
RUN_INTEGRATION=1 uv run pytest -q
```

Windows 没有 GNU Make 时，直接运行对应的 `uv run ...` 命令即可。

## 架构

见 [docs/architecture.md](docs/architecture.md)。

## 分支与发布

见 [docs/branching.md](docs/branching.md)：`main` 生产基线、`develop` 日常集成、`feature/*` 短分支、`release/*` 发布冻结、`hotfix/*` 生产修复。

## 指标口径

见 [docs/metrics.md](docs/metrics.md)。

## 许可证

Apache-2.0。
