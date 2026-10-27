# creator-live-ops M1 接入层实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M0 骨架上完成 M1 接入层：抖店订单/售后/结算、千川消耗、CSV 兜底，把昨日数据幂等写入 ODS，并具备重试、超时、fetch_log 与增量水位。

**Architecture:** 新增 `app/adapters/` 适配器层（抖店、千川、CSV）与 `app/ingest/` 入仓服务。适配器只负责把平台响应/文件规范化为 ODS 行；入仓服务统一做 MySQL UPSERT、批次 ID、fetch_log、watermark、失败重试与超时。Job 定义新增 `kind: ingest` 与 `adapter`，`JobService` 按 kind 分派到 SQL Runner 或 IngestionService。

**Tech Stack:** Python 3.12、httpx、SQLAlchemy 2 async、MySQL 8 方言 UPSERT、Alembic、PyYAML、pytest、httpx.MockTransport、ruff、mypy、uv。

---

## 范围决策（必须先读）

1. **直播时段来源**：设计文档 §15.2 已确认「v1 店播排期唯一来源为 CSV」。抖店开放平台没有稳定的官方直播场次列表接口（现有内部仓库的直播数据来自飞书排期 + 存储过程）。因此 M1 的 `ods_live_room` 由 `CsvImportAdapter` 导入；`DouyinShopAdapter.fetch_live_rooms()` 明确抛 `UnsupportedResource`，不伪造接口。后续需要 `open.douyin.com` 的直播数据权限时再单独接入。
2. **真实凭证**：当前项目 `.env` 没有抖店/千川凭证。M1 按官方契约实现签名、Token、分页与错误分类，用 `httpx.MockTransport` 做契约测试；真实凭证联调作为可选 smoke，等凭证配置后再跑。不在仓库写入任何凭证。
3. **千川 Token**：M1 只使用长期 `access_token`（环境变量或 `sys_config` 加密存储），不实现千川 OAuth 刷新；文档标注为 M1 限制。
4. **API 类 Job 默认关闭**：没有凭证时每天失败会产生噪音。`douyin_*` / `qianchuan_*` Job 默认 `enabled: false`；配置凭证后在 YAML 或后续配置中心启用。CSV Job 默认开启，目录为空时成功写入 0 行。
5. **不新增 ODS 表**：M1 只落 `ods_order`、`ods_after_sale`、`ods_settlement`、`ods_live_room`、`ods_ad_cost`、`ods_fetch_log`。`ods_order_item`、`ods_live_stat`、`ods_talent` 留给 M2。

---

## File Structure

```text
creator-live-ops/
├─ app/
│  ├─ adapters/
│  │  ├─ __init__.py
│  │  ├─ base.py                  # TimeWindow / 异常 / BaseAdapter
│  │  ├─ values.py                # 时间、金额解析
│  │  ├─ retry.py                 # 重试策略
│  │  ├─ credentials.py           # env / sys_config 凭证读取与加密写入
│  │  ├─ factory.py               # 按 adapter 名称构建适配器
│  │  ├─ douyin/
│  │  │  ├─ __init__.py
│  │  │  ├─ signer.py             # HMAC-SHA256 签名
│  │  │  ├─ client.py             # 抖店 HTTP 客户端
│  │  │  ├─ token.py              # token.create / token.refresh
│  │  │  └─ adapter.py            # 订单/售后/结算
│  │  ├─ qianchuan/
│  │  │  ├─ __init__.py
│  │  │  ├─ client.py
│  │  │  └─ adapter.py
│  │  └─ csv/
│  │     ├─ __init__.py
│  │     ├─ mapping.py
│  │     ├─ adapter.py
│  │     └─ mappings/
│  │        ├─ orders.yml
│  │        ├─ after_sales.yml
│  │        ├─ settlements.yml
│  │        └─ live_rooms.yml
│  ├─ ingest/
│  │  ├─ __init__.py
│  │  └─ service.py
│  ├─ db/
│  │  └─ ods_models.py
│  └─ executor/
│     ├─ demo.py                  # 增加 run_job
│     └─ cli.py                   # 手动触发/补数
├─ alembic/versions/0003_ods_tables.py
├─ data/csv/{orders,after_sales,settlements,live_rooms}/.gitkeep
├─ jobs/
│  ├─ douyin_orders_daily.yml
│  ├─ douyin_after_sales_daily.yml
│  ├─ douyin_settlements_daily.yml
│  ├─ qianchuan_ad_cost_daily.yml
│  ├─ csv_orders_daily.yml
│  ├─ csv_after_sales_daily.yml
│  ├─ csv_settlements_daily.yml
│  └─ csv_live_rooms_daily.yml
├─ tests/
│  ├─ unit/test_adapters_base.py
│  ├─ unit/test_adapters_values.py
│  ├─ unit/test_retry.py
│  ├─ unit/test_douyin_signer.py
│  ├─ unit/test_douyin_client.py
│  ├─ unit/test_douyin_token.py
│  ├─ unit/test_douyin_adapter.py
│  ├─ unit/test_qianchuan_client.py
│  ├─ unit/test_qianchuan_adapter.py
│  ├─ unit/test_csv_mapping.py
│  ├─ unit/test_csv_adapter.py
│  ├─ unit/test_credentials.py
│  ├─ unit/test_ingest_service.py
│  └─ integration/test_ingest.py
├─ docs/ingestion.md
├─ .env.example
├─ docker-compose.yml
├─ Makefile
└─ doc/操作日志.md
```

---

## Task 1: ODS 表与 ORM

**Files:**
- Create: `app/db/ods_models.py`
- Create: `alembic/versions/0003_ods_tables.py`
- Test: `tests/unit/test_ods_models.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_ods_models.py`：

```python
from app.db.models import Base


def test_ods_tables_registered() -> None:
    import app.db.ods_models  # noqa: F401

    names = set(Base.metadata.tables)
    expected = {
        "ods_order",
        "ods_after_sale",
        "ods_settlement",
        "ods_live_room",
        "ods_ad_cost",
        "ods_fetch_log",
    }
    assert expected <= names


def test_ods_order_primary_key() -> None:
    import app.db.ods_models as ods

    pk = [column.name for column in ods.OdsOrder.__table__.primary_key.columns]
    assert pk == ["platform", "order_id"]


def test_ods_ad_cost_primary_key_order() -> None:
    import app.db.ods_models as ods

    pk = [column.name for column in ods.OdsAdCost.__table__.primary_key.columns]
    assert pk == ["platform", "account_id", "stat_time", "granularity"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_ods_models.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.db.ods_models'`

- [ ] **Step 3: 写 ORM 模型**

`app/db/ods_models.py`：

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class OdsOrder(Base):
    __tablename__ = "ods_order"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str | None] = mapped_column(String(64))
    order_status: Mapped[str | None] = mapped_column(String(40))
    pay_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pay_at: Mapped[datetime | None] = mapped_column(DateTime)
    create_at: Mapped[datetime | None] = mapped_column(DateTime)
    update_at: Mapped[datetime | None] = mapped_column(DateTime)
    talent_id: Mapped[str | None] = mapped_column(String(64))
    room_id: Mapped[str | None] = mapped_column(String(64))
    channel_type: Mapped[str | None] = mapped_column(String(40))
    content_type: Mapped[str | None] = mapped_column(String(40))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsAfterSale(Base):
    __tablename__ = "ods_after_sale"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    after_sale_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str | None] = mapped_column(String(40))
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    apply_at: Mapped[datetime | None] = mapped_column(DateTime)
    finish_at: Mapped[datetime | None] = mapped_column(DateTime)
    update_at: Mapped[datetime | None] = mapped_column(DateTime)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsSettlement(Base):
    __tablename__ = "ods_settlement"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    settlement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(64))
    settle_at: Mapped[datetime | None] = mapped_column(DateTime)
    settle_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    talent_commission: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    service_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsLiveRoom(Base):
    __tablename__ = "ods_live_room"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shop_id: Mapped[str | None] = mapped_column(String(64))
    talent_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str | None] = mapped_column(String(40))
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsAdCost(Base):
    __tablename__ = "ods_ad_cost"

    platform: Mapped[str] = mapped_column(String(20), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stat_time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    granularity: Mapped[str] = mapped_column(String(10), primary_key=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    conversions: Mapped[int | None] = mapped_column(BigInteger)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    etl_create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    etl_update_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OdsFetchLog(Base):
    __tablename__ = "ods_fetch_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ods_fetch_log_resource_created", "resource", "created_at"),
    )
```

- [ ] **Step 4: 写 Alembic 迁移**

`alembic/versions/0003_ods_tables.py`：

```python
"""ods tables

Revision ID: 0003_ods_tables
Revises: 0002_demo_tables
Create Date: 2026-10-27
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_ods_tables"
down_revision = "0002_demo_tables"
branch_labels = None
depends_on = None

TABLE_KW = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    op.create_table(
        "ods_order",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("shop_id", sa.String(64)),
        sa.Column("order_status", sa.String(40)),
        sa.Column("pay_amount", sa.Numeric(18, 2)),
        sa.Column("pay_at", sa.DateTime()),
        sa.Column("create_at", sa.DateTime()),
        sa.Column("update_at", sa.DateTime()),
        sa.Column("talent_id", sa.String(64)),
        sa.Column("room_id", sa.String(64)),
        sa.Column("channel_type", sa.String(40)),
        sa.Column("content_type", sa.String(40)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index("ix_ods_order_pay_at", "ods_order", ["pay_at"])
    op.create_index("ix_ods_order_update_at", "ods_order", ["update_at"])

    op.create_table(
        "ods_after_sale",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("after_sale_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64)),
        sa.Column("type", sa.String(40)),
        sa.Column("status", sa.String(40)),
        sa.Column("refund_amount", sa.Numeric(18, 2)),
        sa.Column("apply_at", sa.DateTime()),
        sa.Column("finish_at", sa.DateTime()),
        sa.Column("update_at", sa.DateTime()),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index("ix_ods_after_sale_order_id", "ods_after_sale", ["order_id"])
    op.create_index("ix_ods_after_sale_apply_at", "ods_after_sale", ["apply_at"])

    op.create_table(
        "ods_settlement",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("settlement_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64)),
        sa.Column("settle_at", sa.DateTime()),
        sa.Column("settle_amount", sa.Numeric(18, 2)),
        sa.Column("commission_amount", sa.Numeric(18, 2)),
        sa.Column("talent_commission", sa.Numeric(18, 2)),
        sa.Column("service_fee", sa.Numeric(18, 2)),
        sa.Column("platform_fee", sa.Numeric(18, 2)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index("ix_ods_settlement_order_id", "ods_settlement", ["order_id"])
    op.create_index("ix_ods_settlement_settle_at", "ods_settlement", ["settle_at"])

    op.create_table(
        "ods_live_room",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("room_id", sa.String(64), primary_key=True),
        sa.Column("shop_id", sa.String(64)),
        sa.Column("talent_id", sa.String(64)),
        sa.Column("title", sa.String(255)),
        sa.Column("start_at", sa.DateTime()),
        sa.Column("end_at", sa.DateTime()),
        sa.Column("status", sa.String(40)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index("ix_ods_live_room_start_at", "ods_live_room", ["start_at"])

    op.create_table(
        "ods_ad_cost",
        sa.Column("platform", sa.String(20), primary_key=True),
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("stat_time", sa.DateTime(), primary_key=True),
        sa.Column("granularity", sa.String(10), primary_key=True),
        sa.Column("cost", sa.Numeric(18, 2)),
        sa.Column("impressions", sa.BigInteger()),
        sa.Column("clicks", sa.BigInteger()),
        sa.Column("conversions", sa.BigInteger()),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("etl_create_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("etl_update_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index("ix_ods_ad_cost_stat_time", "ods_ad_cost", ["stat_time"])

    op.create_table(
        "ods_fetch_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        **TABLE_KW,
    )
    op.create_index(
        "ix_ods_fetch_log_resource_created",
        "ods_fetch_log",
        ["resource", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ods_fetch_log_resource_created", table_name="ods_fetch_log")
    op.drop_index("ix_ods_ad_cost_stat_time", table_name="ods_ad_cost")
    op.drop_index("ix_ods_live_room_start_at", table_name="ods_live_room")
    op.drop_index("ix_ods_settlement_settle_at", table_name="ods_settlement")
    op.drop_index("ix_ods_settlement_order_id", table_name="ods_settlement")
    op.drop_index("ix_ods_after_sale_apply_at", table_name="ods_after_sale")
    op.drop_index("ix_ods_after_sale_order_id", table_name="ods_after_sale")
    op.drop_index("ix_ods_order_update_at", table_name="ods_order")
    op.drop_index("ix_ods_order_pay_at", table_name="ods_order")
    for table in [
        "ods_fetch_log",
        "ods_ad_cost",
        "ods_live_room",
        "ods_settlement",
        "ods_after_sale",
        "ods_order",
    ]:
        op.drop_table(table)
```

- [ ] **Step 5: 运行单元测试与离线迁移**

Run:
```bash
uv run pytest tests/unit/test_ods_models.py -q
uv run alembic upgrade head --sql > /tmp/m1_ods.sql
grep -E "CREATE TABLE (ods_order|ods_after_sale|ods_settlement|ods_live_room|ods_ad_cost|ods_fetch_log)" /tmp/m1_ods.sql
```
Expected: 3 passed；离线 SQL 中能看到 6 张新增 ODS 表的 `CREATE TABLE`。

- [ ] **Step 6: 提交**

```bash
git add app/db/ods_models.py alembic/versions/0003_ods_tables.py tests/unit/test_ods_models.py
git commit -m "feat: add ODS tables and models

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 2: 适配器基础类型、解析工具与重试

**Files:**
- Create: `app/adapters/__init__.py`
- Create: `app/adapters/base.py`
- Create: `app/adapters/values.py`
- Create: `app/adapters/retry.py`
- Test: `tests/unit/test_adapters_base.py`
- Test: `tests/unit/test_adapters_values.py`
- Test: `tests/unit/test_retry.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_adapters_base.py`：

```python
from datetime import datetime, timedelta

import pytest

from app.adapters.base import TimeWindow


def test_time_window_rejects_empty_range() -> None:
    with pytest.raises(ValueError, match="start_at must be before end_at"):
        TimeWindow(datetime(2026, 10, 27), datetime(2026, 10, 27))


def test_time_window_slices_cover_full_range() -> None:
    window = TimeWindow(datetime(2026, 10, 27, 0), datetime(2026, 10, 27, 3))
    slices = list(window.iter_slices(minutes=90))
    assert slices == [
        TimeWindow(datetime(2026, 10, 27, 0), datetime(2026, 10, 27, 1, 30)),
        TimeWindow(datetime(2026, 10, 27, 1, 30), datetime(2026, 10, 27, 3)),
    ]


def test_time_window_requires_positive_slice() -> None:
    window = TimeWindow(datetime(2026, 10, 27), datetime(2026, 10, 28))
    with pytest.raises(ValueError, match="minutes must be positive"):
        list(window.iter_slices(minutes=0))
```

`tests/unit/test_adapters_values.py`：

```python
from datetime import datetime
from decimal import Decimal

from app.adapters.values import epoch_seconds, format_datetime, parse_datetime, parse_decimal


def test_parse_datetime_accepts_epoch_seconds_and_millis() -> None:
    assert parse_datetime(0) == datetime(1970, 1, 1, 8)
    assert parse_datetime(0) == parse_datetime(0_000)


def test_parse_datetime_accepts_strings() -> None:
    assert parse_datetime("2026-10-27 12:00:00") == datetime(2026, 10, 27, 12)
    assert parse_datetime("2026-10-27") == datetime(2026, 10, 27)


def test_parse_datetime_rejects_blank() -> None:
    assert parse_datetime(None) is None
    assert parse_datetime("") is None


def test_parse_decimal_strips_currency_and_commas() -> None:
    assert parse_decimal("￥1,234.50") == Decimal("1234.50")
    assert parse_decimal("") is None
    assert parse_decimal("bad") is None


def test_format_and_epoch_round_trip() -> None:
    dt = datetime(2026, 10, 27, 12, 30)
    assert format_datetime(dt) == "2026-10-27 12:30:00"
    assert epoch_seconds(dt) == 1793075400
```

注意：`epoch_seconds` 的期望值按 `Asia/Shanghai` 计算；如果本机时区不同也不影响，因为实现显式使用 `ZoneInfo("Asia/Shanghai")`。

`tests/unit/test_retry.py`：

```python
import pytest

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy


async def test_retry_transient_until_success() -> None:
    calls = 0
    delays: list[float] = []

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("boom")
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await retry_call(flaky, RetryPolicy(3, 2), sleep=fake_sleep)
    assert result.value == "ok"
    assert result.attempts == 3
    assert delays == [2, 4]


async def test_retry_does_not_retry_auth_or_permanent() -> None:
    async def auth() -> str:
        raise AuthError("bad token")

    with pytest.raises(AuthError):
        await retry_call(auth, RetryPolicy(3, 1), sleep=_noop)

    async def permanent() -> str:
        raise PermanentError("bad params")

    with pytest.raises(PermanentError):
        await retry_call(permanent, RetryPolicy(3, 1), sleep=_noop)


async def test_retry_honours_rate_limit_delay() -> None:
    delays: list[float] = []
    calls = 0

    async def limited() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("slow down", retry_after=7)
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await retry_call(limited, RetryPolicy(2, 30), sleep=fake_sleep)
    assert result.value == "ok"
    assert delays == [7]


async def _noop(seconds: float) -> None:
    return None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_adapters_base.py tests/unit/test_adapters_values.py tests/unit/test_retry.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写实现**

`app/adapters/__init__.py`：

```python
"""平台数据源适配器。"""
```

`app/adapters/base.py`：

```python
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


class AdapterError(Exception):
    pass


class UnsupportedResource(AdapterError):
    pass


class AuthError(AdapterError):
    pass


class PermanentError(AdapterError):
    pass


class RetryableError(AdapterError):
    pass


class TransientError(RetryableError):
    pass


class RateLimitError(RetryableError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class TimeWindow:
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")

    def iter_slices(self, minutes: int) -> Iterator["TimeWindow"]:
        if minutes <= 0:
            raise ValueError("minutes must be positive")
        cursor = self.start_at
        while cursor < self.end_at:
            next_cursor = min(cursor + timedelta(minutes=minutes), self.end_at)
            yield TimeWindow(cursor, next_cursor)
            cursor = next_cursor


class BaseAdapter:
    platform: str = ""
    lane: str = ""

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support orders")

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support after sales")

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support settlements")

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support live rooms")

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(f"{type(self).__name__} does not support ad cost")

    async def close(self) -> None:
        return None
```

`app/adapters/values.py`：

```python
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Shanghai")


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, TIMEZONE).replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(TIMEZONE).replace(tzinfo=None)
    return parsed


def parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("￥", "").replace("¥", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def epoch_seconds(value: datetime) -> int:
    aware = value.replace(tzinfo=TIMEZONE) if value.tzinfo is None else value
    return int(aware.timestamp())
```

`app/adapters/retry.py`：

```python
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.adapters.base import (
    AuthError,
    PermanentError,
    RateLimitError,
    RetryableError,
    UnsupportedResource,
)
from app.scheduler.models import RetryPolicy

T = TypeVar("T")


@dataclass(frozen=True)
class AttemptedResult(Generic[T]):
    value: T
    attempts: int


async def retry_call(
    call: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AttemptedResult[T]:
    max_attempts = max(1, policy.max_attempts)
    for attempt in range(1, max_attempts + 1):
        try:
            return AttemptedResult(await call(), attempt)
        except (AuthError, PermanentError, UnsupportedResource):
            raise
        except RetryableError as exc:
            if attempt >= max_attempts:
                raise
            if isinstance(exc, RateLimitError) and exc.retry_after is not None:
                delay = exc.retry_after
            else:
                delay = policy.backoff_seconds * (2 ** (attempt - 1))
            await sleep(float(delay))
    raise AssertionError("unreachable")
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/unit/test_adapters_base.py tests/unit/test_adapters_values.py tests/unit/test_retry.py -q`
Expected: PASS（10 个左右）。

- [ ] **Step 5: 提交**

```bash
git add app/adapters tests/unit/test_adapters_base.py tests/unit/test_adapters_values.py tests/unit/test_retry.py
git commit -m "feat: add adapter primitives and retry policy

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 3: 抖店签名与 HTTP 客户端

**Files:**
- Create: `app/adapters/douyin/__init__.py`
- Create: `app/adapters/douyin/signer.py`
- Create: `app/adapters/douyin/client.py`
- Test: `tests/unit/test_douyin_signer.py`
- Test: `tests/unit/test_douyin_client.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_douyin_signer.py`：

```python
from app.adapters.douyin.signer import canonical_json, sign_request


def test_canonical_json_sorts_and_compacts() -> None:
    assert canonical_json({"size": 50, "page": 0}) == '{"page":0,"size":50}'


def test_sign_request_matches_known_vector() -> None:
    signature = sign_request(
        app_key="test_key",
        app_secret="test_secret",
        method="order.searchList",
        param_json='{"page":0,"size":50}',
        timestamp="2026-10-27 10:00:00",
    )
    assert signature == "af379fa1da6904e2061934441a330fa1713f0a51928665c2237985b9438b6c35"
```

`tests/unit/test_douyin_client.py`：

```python
import json

import httpx
import pytest

from app.adapters.base import AuthError, PermanentError, TransientError
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.signer import sign_request
from app.scheduler.models import RetryPolicy


def make_client(handler, *, token: str = "token") -> DouyinClient:
    return DouyinClient(
        app_key="test_key",
        app_secret="test_secret",
        access_token=token,
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
    )


async def test_request_builds_signed_query_and_returns_data() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    client = make_client(handler)
    data = await client.request("order.searchList", {"size": 50, "page": 0})
    assert data == {"ok": True}

    request = captured[0]
    assert request.url.path == "/order/searchList"
    assert request.url.params["method"] == "order.searchList"
    assert request.url.params["app_key"] == "test_key"
    assert request.url.params["access_token"] == "token"
    assert request.url.params["sign_method"] == "hmac-sha256"
    param_json = request.content.decode("utf-8")
    assert param_json == '{"page":0,"size":50}'
    expected_sign = sign_request(
        app_key="test_key",
        app_secret="test_secret",
        method="order.searchList",
        param_json=param_json,
        timestamp=request.url.params["timestamp"],
    )
    assert request.url.params["sign"] == expected_sign


async def test_token_endpoint_omits_access_token() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 10000, "data": {"access_token": "new"}})

    client = make_client(handler)
    data = await client.request(
        "token.create", {"code": "", "grant_type": "authorization_self"},
        include_access_token=False,
    )
    assert data == {"access_token": "new"}
    assert "access_token" not in captured[0].url.params


async def test_transient_http_error_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    client = make_client(handler)
    assert await client.request_with_retry("order.searchList", {}) == {"ok": True}
    assert calls == 2


async def test_business_error_is_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 10001, "msg": "param error"})

    client = make_client(handler)
    with pytest.raises(PermanentError, match="10001"):
        await client.request("order.searchList", {})


async def test_http_401_is_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = make_client(handler)
    with pytest.raises(AuthError):
        await client.request("order.searchList", {})


async def test_missing_token_raises_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = make_client(handler, token="")
    with pytest.raises(AuthError, match="access token"):
        await client.request("order.searchList", {})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_douyin_signer.py tests/unit/test_douyin_client.py -q`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写实现**

`app/adapters/douyin/__init__.py`：

```python
"""抖店开放平台适配器。"""
```

`app/adapters/douyin/signer.py`：

```python
import hashlib
import hmac
import json
from typing import Any


def canonical_json(params: dict[str, Any]) -> str:
    return json.dumps(
        params,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sign_request(
    *,
    app_key: str,
    app_secret: str,
    method: str,
    param_json: str,
    timestamp: str,
    version: str = "2",
) -> str:
    sign_base = (
        f"{app_secret}"
        f"app_key{app_key}"
        f"method{method}"
        f"param_json{param_json}"
        f"timestamp{timestamp}"
        f"v{version}"
        f"{app_secret}"
    )
    return hmac.new(
        app_secret.encode("utf-8"),
        sign_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().lower()
```

`app/adapters/douyin/client.py`：

```python
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.douyin.signer import canonical_json, sign_request
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy

SUCCESS_CODES = {0, 10000}
DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=1)


class DouyinClient:
    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        access_token: str = "",
        base_url: str = "https://openapi-fxg.jinritemai.com",
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self._retry_policy = retry_policy or DEFAULT_RETRY
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Content-Type": "application/json;charset=utf-8"},
        )

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_access_token: bool = True,
    ) -> dict[str, Any]:
        business_params = params or {}
        timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        param_json = canonical_json(business_params)
        query: dict[str, str] = {
            "method": method,
            "app_key": self.app_key,
            "timestamp": timestamp,
            "v": "2",
            "sign_method": "hmac-sha256",
            "sign": sign_request(
                app_key=self.app_key,
                app_secret=self.app_secret,
                method=method,
                param_json=param_json,
                timestamp=timestamp,
            ),
        }
        if include_access_token:
            if not self.access_token:
                raise AuthError("douyin access token is not configured")
            query["access_token"] = self.access_token

        response = await self._client.post(
            f"/{method.replace('.', '/')}",
            params=query,
            content=param_json.encode("utf-8"),
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "douyin rate limited",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code in {401, 403}:
            raise AuthError(f"douyin auth failed: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise TransientError(f"douyin server error: HTTP {response.status_code}")
        if response.status_code != 200:
            raise PermanentError(f"douyin request failed: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransientError("douyin returned invalid JSON") from exc

        code = payload.get("code")
        if code in SUCCESS_CODES:
            data = payload.get("data")
            return data if isinstance(data, dict) else {}
        message = payload.get("msg") or payload.get("message") or "unknown error"
        raise PermanentError(f"douyin api error code={code}: {message}")

    async def request_with_retry(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_access_token: bool = True,
    ) -> dict[str, Any]:
        result = await retry_call(
            lambda: self.request(
                method,
                params,
                include_access_token=include_access_token,
            ),
            self._retry_policy,
        )
        return result.value

    async def close(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/unit/test_douyin_signer.py tests/unit/test_douyin_client.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/adapters/douyin tests/unit/test_douyin_signer.py tests/unit/test_douyin_client.py
git commit -m "feat: add douyin signing and HTTP client

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 4: 凭证读取、加密存储与抖店 Token

**Files:**
- Create: `app/adapters/credentials.py`
- Create: `app/adapters/douyin/token.py`
- Modify: `app/core/settings.py`
- Test: `tests/unit/test_credentials.py`
- Test: `tests/unit/test_douyin_token.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_credentials.py`：

```python
import base64

import pytest

from app.adapters.credentials import CredentialResolver
from app.core.crypto import SecretBox
from app.core.settings import Settings
from app.db.models import AuditSecretAccess, SysConfig


class FakeSession:
    def __init__(self) -> None:
        self.rows: dict[str, SysConfig] = {}
        self.added: list[object] = []
        self.audits: list[AuditSecretAccess] = []
        self.commits = 0

    async def get(self, model, key):
        assert model is SysConfig
        return self.rows.get(key)

    def add(self, row: object) -> None:
        self.added.append(row)
        if isinstance(row, AuditSecretAccess):
            self.audits.append(row)

    async def commit(self) -> None:
        self.commits += 1
        for row in self.added:
            if isinstance(row, SysConfig):
                self.rows[row.config_key] = row
        self.added.clear()


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


async def test_env_value_takes_precedence_over_database() -> None:
    session = FakeSession()
    row = SysConfig(config_key="douyin.app_key", config_value="from-db", is_secret=False)
    session.rows["douyin.app_key"] = row
    settings = make_settings(douyin_app_key="from-env")
    resolver = CredentialResolver(session, settings)
    assert await resolver.get("douyin.app_key") == "from-env"
    assert session.added == []


async def test_database_secret_is_decrypted_and_audited() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    box = SecretBox(key, "k1")
    session = FakeSession()
    session.rows["douyin.access_token"] = SysConfig(
        config_key="douyin.access_token",
        config_value=box.encrypt("token-value", aad="douyin.access_token"),
        is_secret=True,
        key_id="k1",
    )
    settings = make_settings(encryption_key=key)
    resolver = CredentialResolver(session, settings)
    assert await resolver.get("douyin.access_token") == "token-value"
    assert len(session.audits) == 1
    assert session.audits[0].config_key == "douyin.access_token"


async def test_set_secret_encrypts_and_persists() -> None:
    key = base64.b64encode(b"x" * 32).decode()
    session = FakeSession()
    settings = make_settings(encryption_key=key)
    resolver = CredentialResolver(session, settings)
    await resolver.set_secret("douyin.refresh_token", "refresh-value")
    row = session.rows["douyin.refresh_token"]
    assert row.is_secret is True
    assert row.key_id == "k1"
    assert row.config_value != "refresh-value"
    assert box_decrypt(settings, row.config_value, "douyin.refresh_token") == "refresh-value"


def box_decrypt(settings: Settings, token: str, key: str) -> str:
    box = SecretBox(settings.encryption_key_value, settings.encryption_key_id)
    return box.decrypt(token, aad=key)


async def test_set_secret_requires_encryption_key() -> None:
    resolver = CredentialResolver(FakeSession(), make_settings())
    with pytest.raises(ValueError, match="encryption key"):
        await resolver.set_secret("douyin.refresh_token", "value")
```

`tests/unit/test_douyin_token.py`：

```python
from app.adapters.douyin.token import DouyinTokenProvider


class FakeResolver:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.writes: list[tuple[str, str]] = []

    async def get(self, key: str) -> str:
        return self.data.get(key, "")

    async def set_secret(self, key: str, value: str) -> None:
        self.data[key] = value
        self.writes.append((key, value))


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict, bool]] = []
        self.access_token = ""

    async def request(self, method, params=None, *, include_access_token=True):
        self.calls.append((method, params or {}, include_access_token))
        return self.responses.pop(0)


async def test_get_access_token_creates_when_missing() -> None:
    resolver = FakeResolver()
    client = FakeClient([{"access_token": "new-token", "refresh_token": "new-refresh"}])
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.get_access_token() == "new-token"
    assert resolver.data["douyin.access_token"] == "new-token"
    assert resolver.data["douyin.refresh_token"] == "new-refresh"
    assert client.calls[0][0] == "token.create"
    assert client.calls[0][2] is False


async def test_get_access_token_reuses_existing() -> None:
    resolver = FakeResolver()
    resolver.data["douyin.access_token"] = "existing"
    client = FakeClient([])
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.get_access_token() == "existing"
    assert client.calls == []


async def test_refresh_uses_refresh_token() -> None:
    resolver = FakeResolver()
    resolver.data["douyin.refresh_token"] = "old-refresh"
    client = FakeClient([{"access_token": "fresh", "refresh_token": "fresh-refresh"}])
    provider = DouyinTokenProvider(client, resolver)

    assert await provider.refresh() == "fresh"
    assert client.calls[0][0] == "token.refresh"
    assert client.calls[0][1] == {
        "refresh_token": "old-refresh",
        "grant_type": "refresh_token",
    }
    assert resolver.data["douyin.access_token"] == "fresh"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_credentials.py tests/unit/test_douyin_token.py -q`
Expected: FAIL。

- [ ] **Step 3: 扩展 Settings**

在 `app/core/settings.py` 的 `Settings` 里、`metrics_file` 之后增加：

```python
    douyin_app_key: SecretStr = SecretStr("")
    douyin_app_secret: SecretStr = SecretStr("")
    douyin_access_token: SecretStr = SecretStr("")
    douyin_refresh_token: SecretStr = SecretStr("")
    douyin_shop_id: str = ""
    douyin_base_url: str = "https://openapi-fxg.jinritemai.com"
    qianchuan_access_token: SecretStr = SecretStr("")
    qianchuan_advertiser_pairs: str = ""
    qianchuan_base_url: str = "https://api.oceanengine.com/open_api"
    csv_import_dir: str = "data/csv"
    csv_mappings_dir: str = "app/adapters/csv/mappings"
    http_timeout_seconds: float = 20.0
```

并在 `encryption_key_value` 之后增加属性：

```python
    @property
    def douyin_app_key_value(self) -> str:
        return self.douyin_app_key.get_secret_value()

    @property
    def douyin_app_secret_value(self) -> str:
        return self.douyin_app_secret.get_secret_value()

    @property
    def douyin_access_token_value(self) -> str:
        return self.douyin_access_token.get_secret_value()

    @property
    def douyin_refresh_token_value(self) -> str:
        return self.douyin_refresh_token.get_secret_value()

    @property
    def qianchuan_access_token_value(self) -> str:
        return self.qianchuan_access_token.get_secret_value()
```

- [ ] **Step 4: 写凭证解析器**

`app/adapters/credentials.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretBox
from app.core.settings import Settings
from app.db.models import AuditSecretAccess, SysConfig


class CredentialResolver:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        actor: str = "ingest",
    ) -> None:
        self._session = session
        self._settings = settings
        self._actor = actor
        key = settings.encryption_key_value
        self._box = SecretBox(key, settings.encryption_key_id) if key else None

    def _env_value(self, key: str) -> str:
        if key == "douyin.app_key":
            return self._settings.douyin_app_key_value
        if key == "douyin.app_secret":
            return self._settings.douyin_app_secret_value
        if key == "douyin.access_token":
            return self._settings.douyin_access_token_value
        if key == "douyin.refresh_token":
            return self._settings.douyin_refresh_token_value
        if key == "douyin.shop_id":
            return self._settings.douyin_shop_id
        if key == "qianchuan.access_token":
            return self._settings.qianchuan_access_token_value
        if key == "qianchuan.advertiser_pairs":
            return self._settings.qianchuan_advertiser_pairs
        return ""

    async def get(self, key: str) -> str:
        env_value = self._env_value(key)
        if env_value:
            return env_value

        row = await self._session.get(SysConfig, key)
        if row is None or not row.config_value:
            return ""
        if not row.is_secret:
            return row.config_value
        if self._box is None:
            raise ValueError(f"encryption key is required to read {key}")
        plaintext = self._box.decrypt(row.config_value, aad=key)
        self._session.add(
            AuditSecretAccess(actor=self._actor, config_key=key, action="read")
        )
        await self._session.commit()
        return plaintext

    async def set_secret(self, key: str, value: str) -> None:
        if self._box is None:
            raise ValueError("encryption key is not configured")
        stored = self._box.encrypt(value, aad=key)
        row = await self._session.get(SysConfig, key)
        if row is None:
            row = SysConfig(config_key=key)
            self._session.add(row)
        row.config_value = stored
        row.is_secret = True
        row.key_id = self._box.key_id
        await self._session.commit()
```

- [ ] **Step 5: 写 Token 提供器**

`app/adapters/douyin/token.py`：

```python
from app.adapters.base import AuthError
from app.adapters.credentials import CredentialResolver
from app.adapters.douyin.client import DouyinClient

ACCESS_TOKEN_KEY = "douyin.access_token"
REFRESH_TOKEN_KEY = "douyin.refresh_token"


class DouyinTokenProvider:
    def __init__(self, client: DouyinClient, resolver: CredentialResolver) -> None:
        self._client = client
        self._resolver = resolver

    async def get_access_token(self) -> str:
        token = await self._resolver.get(ACCESS_TOKEN_KEY)
        if token:
            return token
        return await self._create()

    async def refresh(self) -> str:
        refresh_token = await self._resolver.get(REFRESH_TOKEN_KEY)
        if not refresh_token:
            return await self._create()
        data = await self._client.request(
            "token.refresh",
            {"refresh_token": refresh_token, "grant_type": "refresh_token"},
            include_access_token=False,
        )
        return await self._store(data)

    async def _create(self) -> str:
        data = await self._client.request(
            "token.create",
            {"code": "", "grant_type": "authorization_self"},
            include_access_token=False,
        )
        return await self._store(data)

    async def _store(self, data: dict) -> str:
        token = str(data.get("access_token") or "")
        if not token:
            raise AuthError("douyin token response missing access_token")
        await self._resolver.set_secret(ACCESS_TOKEN_KEY, token)
        refresh_token = data.get("refresh_token")
        if refresh_token:
            await self._resolver.set_secret(REFRESH_TOKEN_KEY, str(refresh_token))
        return token
```

- [ ] **Step 6: 运行测试**

Run: `uv run pytest tests/unit/test_credentials.py tests/unit/test_douyin_token.py tests/unit/test_settings.py -q`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add app/adapters/credentials.py app/adapters/douyin/token.py app/core/settings.py tests/unit/test_credentials.py tests/unit/test_douyin_token.py
git commit -m "feat: add credential resolver and douyin token refresh

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 5: 抖店订单/售后/结算适配器

**Files:**
- Create: `app/adapters/douyin/adapter.py`
- Test: `tests/unit/test_douyin_adapter.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_douyin_adapter.py`：

```python
from datetime import datetime

import pytest

from app.adapters.base import TimeWindow, UnsupportedResource
from app.adapters.douyin.adapter import DouyinShopAdapter


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []
        self.access_token = "token"

    async def request_with_retry(self, method: str, params: dict | None = None) -> dict:
        self.calls.append((method, params or {}))
        return self.responses.pop(0)


WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))


async def test_orders_merge_created_and_updated_passes() -> None:
    created = {
        "total": 2,
        "shop_order_list": [
            {"order_id": "o1", "pay_amount": "10.00", "pay_time": "2026-10-26 10:00:00"},
            {"order_id": "o2", "pay_amount": "20.00", "pay_time": "2026-10-26 11:00:00"},
        ],
    }
    updated = {
        "total": 1,
        "shop_order_list": [
            {"order_id": "o1", "pay_amount": "12.00", "pay_time": "2026-10-26 10:00:00",
             "order_status": "paid"},
        ],
    }
    client = FakeClient([created, updated])
    adapter = DouyinShopAdapter(client)

    rows = await adapter.fetch_orders(WINDOW)

    assert len(rows) == 2
    assert {row["order_id"] for row in rows} == {"o1", "o2"}
    first = next(row for row in rows if row["order_id"] == "o1")
    assert str(first["pay_amount"]) == "12.00"
    assert first["order_status"] == "paid"
    assert first["raw_json"]["order_id"] == "o1"
    assert client.calls[0][1]["create_time_start"] == 1792944000
    assert client.calls[1][1]["update_time_start"] == 1792944000


async def test_after_sales_maps_nested_payload() -> None:
    response = {
        "total": 1,
        "items": [
            {
                "aftersale_info": {
                    "aftersale_id": 9001,
                    "aftersale_type": "refund",
                    "aftersale_status": "success",
                    "refund_amount": "8.88",
                    "apply_time": "2026-10-26 09:00:00",
                    "refund_time": "2026-10-26 12:00:00",
                    "update_time": "2026-10-26 12:00:00",
                },
                "order_info": {"shop_order_id": "o1"},
            }
        ],
    }
    adapter = DouyinShopAdapter(FakeClient([response, {"total": 0, "items": []}]))

    rows = await adapter.fetch_after_sales(WINDOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["after_sale_id"] == "9001"
    assert row["order_id"] == "o1"
    assert row["type"] == "refund"
    assert row["status"] == "success"
    assert str(row["refund_amount"]) == "8.88"
    assert row["apply_at"] == datetime(2026, 10, 26, 9)
    assert row["finish_at"] == datetime(2026, 10, 26, 12)


async def test_settlements_follow_cursor_until_is_end() -> None:
    first = {
        "is_end": 0,
        "data": [{"request_no": "s1", "shop_order_id": "o1", "settle_amount": "100.00",
                  "settle_time": "2026-10-26 01:00:00"}],
        "next_start_index": "cursor-2",
        "next_start_time": "2026-10-26 02:00:00",
    }
    second = {
        "is_end": 1,
        "data": [{"request_no": "s2", "shop_order_id": "o2", "settle_amount": "50.00",
                  "settle_time": "2026-10-26 03:00:00"}],
        "next_start_index": "",
        "next_start_time": "",
    }
    client = FakeClient([first, second])
    adapter = DouyinShopAdapter(client)

    rows = await adapter.fetch_settlements(WINDOW)

    assert [row["settlement_id"] for row in rows] == ["s1", "s2"]
    assert str(rows[0]["settle_amount"]) == "100.00"
    assert client.calls[1][1]["start_index"] == "cursor-2"
    assert client.calls[1][1]["start_time"] == "2026-10-26 02:00:00"


async def test_live_rooms_are_not_supported_by_douyin_adapter() -> None:
    adapter = DouyinShopAdapter(FakeClient([]))
    with pytest.raises(UnsupportedResource, match="live room"):
        await adapter.fetch_live_rooms(WINDOW)
```

注意：`1792944000` 是 `2026-10-26 00:00:00 Asia/Shanghai` 的 epoch 秒；`create_time_end` 使用窗口结束减 1 秒。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_douyin_adapter.py -q`
Expected: FAIL。

- [ ] **Step 3: 写实现**

`app/adapters/douyin/adapter.py`：

```python
from typing import Any

from app.adapters.base import AuthError, BaseAdapter, TimeWindow, UnsupportedResource
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.token import DouyinTokenProvider
from app.adapters.values import epoch_seconds, format_datetime, parse_datetime, parse_decimal

MAX_PAGES = 1000


class DouyinShopAdapter(BaseAdapter):
    platform = "douyin"
    lane = "douyin_shop"

    def __init__(
        self,
        client: DouyinClient,
        token_provider: DouyinTokenProvider | None = None,
        *,
        page_size: int = 50,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._page_size = page_size

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._client.request_with_retry(method, params)
        except AuthError:
            if self._token_provider is None:
                raise
            token = await self._token_provider.refresh()
            self._client.access_token = token
            return await self._client.request_with_retry(method, params)

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        created = await self._list_orders(window, "create")
        updated = await self._list_orders(window, "update")
        merged = {row["order_id"]: row for row in created}
        merged.update({row["order_id"]: row for row in updated})
        return list(merged.values())

    async def _list_orders(
        self, window: TimeWindow, time_type: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 0
        collected = 0
        while page < MAX_PAGES:
            params: dict[str, Any] = {"page": page, "size": self._page_size}
            if time_type == "update":
                params["update_time_start"] = epoch_seconds(window.start_at)
                params["update_time_end"] = epoch_seconds(window.end_at) - 1
            else:
                params["create_time_start"] = epoch_seconds(window.start_at)
                params["create_time_end"] = epoch_seconds(window.end_at) - 1
            data = await self._request("order.searchList", params)
            items = data.get("shop_order_list") or []
            for item in items:
                normalized = self._normalize_order(item)
                if normalized is not None:
                    rows.append(normalized)
            collected += len(items)
            total = int(data.get("total") or 0)
            page += 1
            if not items or collected >= total:
                break
        return rows

    @staticmethod
    def _normalize_order(item: dict[str, Any]) -> dict[str, Any] | None:
        payload = item.get("shop_order_detail")
        detail = payload if isinstance(payload, dict) else item
        order_id = detail.get("order_id") or detail.get("shop_order_id")
        if not order_id:
            return None
        return {
            "order_id": str(order_id),
            "shop_id": _string(detail.get("shop_id")),
            "order_status": _string(
                detail.get("order_status") or detail.get("order_status_desc")
            ),
            "pay_amount": parse_decimal(
                detail.get("pay_amount") or detail.get("pay_amount_str")
            ),
            "pay_at": parse_datetime(
                detail.get("pay_time") or detail.get("pay_time_str")
            ),
            "create_at": parse_datetime(
                detail.get("create_time") or detail.get("create_time_str")
            ),
            "update_at": parse_datetime(
                detail.get("update_time") or detail.get("update_time_str")
            ),
            "talent_id": _string(detail.get("talent_id") or detail.get("author_id")),
            "room_id": _string(detail.get("room_id_str") or detail.get("room_id")),
            "channel_type": _string(
                detail.get("channel_type") or detail.get("order_channel")
            ),
            "content_type": _string(
                detail.get("content_type") or detail.get("product_type")
            ),
            "raw_json": item,
        }

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        created = await self._list_after_sales(window, "create")
        updated = await self._list_after_sales(window, "update")
        merged = {row["after_sale_id"]: row for row in created}
        merged.update({row["after_sale_id"]: row for row in updated})
        return list(merged.values())

    async def _list_after_sales(
        self, window: TimeWindow, time_type: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 0
        collected = 0
        while page < MAX_PAGES:
            params: dict[str, Any] = {"page": page, "size": self._page_size}
            if time_type == "update":
                params["order_by"] = ["update_time desc"]
                params["update_start_time"] = epoch_seconds(window.start_at)
                params["update_end_time"] = epoch_seconds(window.end_at) - 1
            else:
                params["start_time"] = epoch_seconds(window.start_at)
                params["end_time"] = epoch_seconds(window.end_at) - 1
            data = await self._request("afterSale.List", params)
            items = data.get("items") or []
            for item in items:
                normalized = self._normalize_after_sale(item)
                if normalized is not None:
                    rows.append(normalized)
            collected += len(items)
            total = int(data.get("total") or 0)
            page += 1
            if not items or collected >= total:
                break
        return rows

    @staticmethod
    def _normalize_after_sale(item: dict[str, Any]) -> dict[str, Any] | None:
        info = item.get("aftersale_info")
        info = info if isinstance(info, dict) else {}
        order_info = item.get("order_info")
        order_info = order_info if isinstance(order_info, dict) else {}
        after_sale_id = info.get("aftersale_id")
        if not after_sale_id:
            return None
        return {
            "after_sale_id": str(after_sale_id),
            "order_id": _string(order_info.get("shop_order_id") or info.get("order_id")),
            "type": _string(info.get("aftersale_type") or info.get("type")),
            "status": _string(info.get("aftersale_status") or info.get("status")),
            "refund_amount": parse_decimal(info.get("refund_amount")),
            "apply_at": parse_datetime(info.get("apply_time")),
            "finish_at": parse_datetime(
                info.get("refund_time") or info.get("finish_time")
            ),
            "update_at": parse_datetime(info.get("update_time")),
            "raw_json": item,
        }

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        params: dict[str, Any] = {
            "start_time": format_datetime(window.start_at),
            "end_time": format_datetime(window.end_at),
            "time_type": 0,
            "size": 100,
            "start_index": "",
        }
        for _ in range(MAX_PAGES):
            data = await self._request("order.getSettleBillDetailV3", params)
            for record in data.get("data") or []:
                normalized = self._normalize_settlement(record)
                if normalized is not None:
                    rows.append(normalized)
            if int(data.get("is_end", 1)) == 1:
                break
            next_index = str(data.get("next_start_index") or "").strip()
            next_time = data.get("next_start_time") or ""
            if not next_index and not next_time:
                break
            params["start_index"] = next_index
            if next_time:
                params["start_time"] = str(next_time)
        return rows

    @staticmethod
    def _normalize_settlement(record: dict[str, Any]) -> dict[str, Any] | None:
        settlement_id = (
            record.get("request_no")
            or record.get("settle_id")
            or record.get("settlement_id")
        )
        if not settlement_id:
            return None
        return {
            "settlement_id": str(settlement_id),
            "order_id": _string(record.get("shop_order_id") or record.get("order_id")),
            "settle_at": parse_datetime(
                record.get("settle_time") or record.get("finish_time")
            ),
            "settle_amount": parse_decimal(
                record.get("settle_amount") or record.get("order_settle_amount")
            ),
            "commission_amount": parse_decimal(record.get("commission_amount")),
            "talent_commission": parse_decimal(record.get("talent_commission")),
            "service_fee": parse_decimal(record.get("service_fee")),
            "platform_fee": parse_decimal(record.get("platform_fee")),
            "raw_json": record,
        }

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource(
            "douyin shop api does not expose live room sessions; use csv_import"
        )

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        raise UnsupportedResource("douyin shop adapter does not support ad cost")

    async def close(self) -> None:
        await self._client.close()


def _string(value: object) -> str:
    return "" if value is None else str(value)
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/unit/test_douyin_adapter.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/adapters/douyin/adapter.py tests/unit/test_douyin_adapter.py
git commit -m "feat: add douyin order after-sale settlement adapter

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 6: 千川客户端与消耗适配器

**Files:**
- Create: `app/adapters/qianchuan/__init__.py`
- Create: `app/adapters/qianchuan/client.py`
- Create: `app/adapters/qianchuan/adapter.py`
- Test: `tests/unit/test_qianchuan_client.py`
- Test: `tests/unit/test_qianchuan_adapter.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_qianchuan_client.py`：

```python
import httpx
import pytest

from app.adapters.base import AuthError, PermanentError, RateLimitError
from app.adapters.qianchuan.client import QianchuanClient
from app.scheduler.models import RetryPolicy


def make_client(handler) -> QianchuanClient:
    return QianchuanClient(
        access_token="qc-token",
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
        rate_limit_delay=0,
    )


async def test_get_sends_access_token_header() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 0, "data": {"list": []}})

    client = make_client(handler)
    data = await client.request("v1.0/qianchuan/report/uni_promotion/data/get/", {"page": 1})
    assert data == {"list": []}
    assert captured[0].headers["Access-Token"] == "qc-token"
    assert captured[0].url.path == "/open_api/v1.0/qianchuan/report/uni_promotion/data/get/"


async def test_http_515_is_rate_limited_and_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(515)
        return httpx.Response(200, json={"code": 0, "data": {"list": [1]}})

    client = make_client(handler)
    assert await client.request_with_retry("v1.0/x/", {}) == {"list": [1]}
    assert calls == 2


async def test_code_40000_is_permanent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 40000, "message": "downstream"})

    client = make_client(handler)
    with pytest.raises(PermanentError, match="40000"):
        await client.request("v1.0/x/", {})


async def test_http_403_is_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = make_client(handler)
    with pytest.raises(AuthError):
        await client.request("v1.0/x/", {})


async def test_rate_limit_error_carries_delay() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(515)

    client = make_client(handler)
    with pytest.raises(RateLimitError):
        await client.request("v1.0/x/", {})
```

`tests/unit/test_qianchuan_adapter.py`：

```python
from datetime import datetime

import pytest

from app.adapters.base import TimeWindow
from app.adapters.qianchuan.adapter import QianchuanAdapter, parse_advertiser_pairs


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def request_with_retry(self, path: str, params: dict) -> dict:
        self.calls.append((path, params))
        return self.responses.pop(0)


WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))


def test_parse_advertiser_pairs() -> None:
    assert parse_advertiser_pairs("1:2, 3:4") == [("1", "2"), ("3", "4")]


def test_parse_advertiser_pairs_rejects_bad_value() -> None:
    with pytest.raises(ValueError, match="advertiser:aweme"):
        parse_advertiser_pairs("1:2,bad")


async def test_fetch_ad_cost_paginates_and_maps() -> None:
    page_one = {
        "list": [
            {"stat_datetime": "2026-10-26 00:00:00", "stat_cost": "12.50"},
        ],
        "page_info": {"total_page": 2},
    }
    page_two = {
        "list": [
            {"stat_datetime": "2026-10-26 00:00:00", "stat_cost": "7.50"},
        ],
        "page_info": {"total_page": 2},
    }
    client = FakeClient([page_one, page_two])
    adapter = QianchuanAdapter(client, [("100", "200")])

    rows = await adapter.fetch_ad_cost(WINDOW)

    assert len(rows) == 2
    assert rows[0]["account_id"] == "100"
    assert rows[0]["granularity"] == "day"
    assert str(rows[0]["cost"]) == "12.50"
    assert rows[0]["stat_time"] == datetime(2026, 10, 26)
    assert client.calls[0][1]["advertiser_id"] == "100"
    assert client.calls[0][1]["aweme_id"] == "200"
    assert client.calls[0][1]["dimension"] == "TIME_GRANULARITY_DAILY"
    assert client.calls[0][1]["page"] == 1
    assert client.calls[1][1]["page"] == 2


async def test_rows_without_stat_datetime_are_skipped() -> None:
    client = FakeClient([
        {"list": [{"stat_cost": "1.00"}], "page_info": {"total_page": 1}},
    ])
    adapter = QianchuanAdapter(client, [("1", "2")])
    assert await adapter.fetch_ad_cost(WINDOW) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_qianchuan_client.py tests/unit/test_qianchuan_adapter.py -q`
Expected: FAIL。

- [ ] **Step 3: 写客户端**

`app/adapters/qianchuan/__init__.py`：

```python
"""巨量千川适配器。"""
```

`app/adapters/qianchuan/client.py`：

```python
from typing import Any

import httpx

from app.adapters.base import AuthError, PermanentError, RateLimitError, TransientError
from app.adapters.retry import retry_call
from app.scheduler.models import RetryPolicy

DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=1)
PERMANENT_CODES = {40000}
RETRYABLE_CODES = {400153}


class QianchuanClient:
    def __init__(
        self,
        *,
        access_token: str,
        base_url: str = "https://api.oceanengine.com/open_api",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limit_delay: float = 10.0,
    ) -> None:
        self._retry_policy = retry_policy or DEFAULT_RETRY
        self._rate_limit_delay = rate_limit_delay
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
            headers={
                "Access-Token": access_token,
                "Content-Type": "application/json;charset=utf-8",
            },
        )

    async def request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._client.get(path.lstrip("/"), params=params)
        if response.status_code == 515:
            raise RateLimitError(
                "qianchuan rate limited", retry_after=self._rate_limit_delay
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "qianchuan rate limited",
                retry_after=float(retry_after) if retry_after else self._rate_limit_delay,
            )
        if response.status_code in {401, 403}:
            raise AuthError(f"qianchuan auth failed: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise TransientError(f"qianchuan server error: HTTP {response.status_code}")
        if response.status_code != 200:
            raise PermanentError(f"qianchuan request failed: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TransientError("qianchuan returned invalid JSON") from exc

        code = payload.get("code")
        if code == 0:
            data = payload.get("data")
            return data if isinstance(data, dict) else {}
        if code in PERMANENT_CODES:
            raise PermanentError(
                f"qianchuan api error code={code}: "
                f"{payload.get('message') or 'unknown error'}"
            )
        if code in RETRYABLE_CODES:
            raise TransientError(
                f"qianchuan api error code={code}: "
                f"{payload.get('message') or 'unknown error'}"
            )
        raise PermanentError(
            f"qianchuan api error code={code}: "
            f"{payload.get('message') or 'unknown error'}"
        )

    async def request_with_retry(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = await retry_call(lambda: self.request(path, params), self._retry_policy)
        return result.value

    async def close(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: 写适配器**

`app/adapters/qianchuan/adapter.py`：

```python
import json
from typing import Any

from app.adapters.base import BaseAdapter, TimeWindow
from app.adapters.qianchuan.client import QianchuanClient
from app.adapters.values import format_datetime, parse_datetime, parse_decimal

REPORT_PATH = "v1.0/qianchuan/report/uni_promotion/dimension_data/author/get/"
MAX_PAGES = 1000


def parse_advertiser_pairs(value: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for chunk in value.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("advertiser pairs must use advertiser:aweme format")
        advertiser_id, aweme_id = (part.strip() for part in item.split(":", 1))
        if not advertiser_id or not aweme_id:
            raise ValueError("advertiser pairs must use advertiser:aweme format")
        pairs.append((advertiser_id, aweme_id))
    return pairs


class QianchuanAdapter(BaseAdapter):
    platform = "douyin"
    lane = "douyin_qianchuan"

    def __init__(
        self,
        client: QianchuanClient,
        advertiser_pairs: list[tuple[str, str]],
        *,
        page_size: int = 100,
    ) -> None:
        self._client = client
        self._advertiser_pairs = advertiser_pairs
        self._page_size = page_size

    async def fetch_ad_cost(self, window: TimeWindow) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for advertiser_id, aweme_id in self._advertiser_pairs:
            page = 1
            for _ in range(MAX_PAGES):
                params: dict[str, Any] = {
                    "advertiser_id": advertiser_id,
                    "aweme_id": aweme_id,
                    "start_time": format_datetime(window.start_at),
                    "end_time": format_datetime(window.end_at),
                    "metrics": json.dumps(["stat_cost"], separators=(",", ":")),
                    "dimension": "TIME_GRANULARITY_DAILY",
                    "page": page,
                    "page_size": self._page_size,
                }
                data = await self._client.request_with_retry(REPORT_PATH, params)
                items = data.get("list") or []
                for item in items:
                    normalized = self._normalize(advertiser_id, item)
                    if normalized is not None:
                        rows.append(normalized)
                page_info = data.get("page_info")
                total_page = int((page_info or {}).get("total_page") or 1)
                if not items or page >= total_page:
                    break
                page += 1
        return rows

    @staticmethod
    def _normalize(
        advertiser_id: str, item: dict[str, Any]
    ) -> dict[str, Any] | None:
        stat_time = parse_datetime(item.get("stat_datetime"))
        if stat_time is None:
            return None
        return {
            "account_id": advertiser_id,
            "stat_time": stat_time,
            "granularity": "day",
            "cost": parse_decimal(item.get("stat_cost")),
            "impressions": _int_or_none(item.get("impressions")),
            "clicks": _int_or_none(item.get("clicks")),
            "conversions": _int_or_none(item.get("conversions")),
            "raw_json": item,
        }

    async def close(self) -> None:
        await self._client.close()


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest tests/unit/test_qianchuan_client.py tests/unit/test_qianchuan_adapter.py -q`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add app/adapters/qianchuan tests/unit/test_qianchuan_client.py tests/unit/test_qianchuan_adapter.py
git commit -m "feat: add qianchuan ad cost adapter

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 7: CSV 映射与兜底导入

**Files:**
- Create: `app/adapters/csv/__init__.py`
- Create: `app/adapters/csv/mapping.py`
- Create: `app/adapters/csv/adapter.py`
- Create: `app/adapters/csv/mappings/{orders,after_sales,settlements,live_rooms}.yml`
- Create: `data/csv/{orders,after_sales,settlements,live_rooms}/.gitkeep`
- Test: `tests/unit/test_csv_mapping.py`
- Test: `tests/unit/test_csv_adapter.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_csv_mapping.py`：

```python
from pathlib import Path

import pytest
import yaml

from app.adapters.csv.mapping import CsvMappingError, load_mapping, load_mappings


def write_mapping(tmp_path: Path, body: dict) -> Path:
    path = tmp_path / "orders.yml"
    path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
    return path


def valid_body() -> dict:
    return {
        "dataset": "orders",
        "resource": "orders",
        "target_table": "ods_order",
        "encoding": "utf-8-sig",
        "delimiter": ",",
        "window_column": "pay_at",
        "key_columns": ["order_id"],
        "required": ["order_id"],
        "datetime_columns": ["pay_at"],
        "decimal_columns": ["pay_amount"],
        "on_error": "skip",
        "fields": {"order_id": "order_id", "pay_at": "pay_at", "pay_amount": "pay_amount"},
    }


def test_load_mapping(tmp_path: Path) -> None:
    mapping = load_mapping(write_mapping(tmp_path, valid_body()))
    assert mapping.dataset == "orders"
    assert mapping.window_column == "pay_at"
    assert mapping.fields["pay_amount"] == "pay_amount"


def test_load_mapping_rejects_unknown_on_error(tmp_path: Path) -> None:
    body = valid_body()
    body["on_error"] = "ignore"
    with pytest.raises(CsvMappingError, match="on_error"):
        load_mapping(write_mapping(tmp_path, body))


def test_load_mapping_rejects_unmapped_datetime_column(tmp_path: Path) -> None:
    body = valid_body()
    body["datetime_columns"] = ["missing"]
    with pytest.raises(CsvMappingError, match="datetime_columns"):
        load_mapping(write_mapping(tmp_path, body))


def test_default_mappings_cover_four_datasets() -> None:
    mappings = load_mappings(Path("app/adapters/csv/mappings"))
    assert set(mappings) == {"orders", "after_sales", "settlements", "live_rooms"}
```

`tests/unit/test_csv_adapter.py`：

```python
from datetime import datetime
from pathlib import Path

import pytest

from app.adapters.base import PermanentError, TimeWindow
from app.adapters.csv.adapter import CsvImportAdapter

WINDOW = TimeWindow(datetime(2026, 10, 26), datetime(2026, 10, 27))
MAPPINGS = Path("app/adapters/csv/mappings")


def write_csv(tmp_path: Path, dataset: str, name: str, content: str) -> None:
    directory = tmp_path / dataset
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8-sig")


async def test_orders_filter_window_and_dedupe(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        "o1,10.00,2026-10-26 10:00:00\n"
        "o2,20.00,2026-10-25 10:00:00\n"
        "o1,15.00,2026-10-26 11:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_orders(WINDOW)
    assert len(rows) == 1
    assert rows[0]["order_id"] == "o1"
    assert str(rows[0]["pay_amount"]) == "15.00"
    assert rows[0]["raw_json"]["订单编号"] == "o1"


async def test_live_rooms_do_not_filter_by_window(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "live_rooms",
        "rooms.csv",
        "直播间ID,店铺ID,开播时间,下播时间\n"
        "r1,s1,2026-12-01 20:00:00,2026-12-01 23:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_live_rooms(WINDOW)
    assert len(rows) == 1
    assert rows[0]["room_id"] == "r1"
    assert rows[0]["start_at"] == datetime(2026, 12, 1, 20)


async def test_invalid_decimal_row_is_skipped(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        "o1,bad,2026-10-26 10:00:00\n"
        "o2,20.00,2026-10-26 11:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    rows = await adapter.fetch_orders(WINDOW)
    assert [row["order_id"] for row in rows] == ["o2"]
    assert adapter.errors


async def test_missing_required_column_raises(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "orders",
        "orders.csv",
        "订单编号,实付金额,支付时间\n"
        ",10.00,2026-10-26 10:00:00\n",
    )
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    with pytest.raises(PermanentError, match="required"):
        await adapter.fetch_orders(WINDOW)


async def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    adapter = CsvImportAdapter(tmp_path, MAPPINGS)
    assert await adapter.fetch_orders(WINDOW) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_csv_mapping.py tests/unit/test_csv_adapter.py -q`
Expected: FAIL。

- [ ] **Step 3: 写映射加载器**

`app/adapters/csv/__init__.py`：

```python
"""CSV 兜底导入适配器。"""
```

`app/adapters/csv/mapping.py`：

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CsvMappingError(ValueError):
    pass


@dataclass(frozen=True)
class CsvMapping:
    dataset: str
    resource: str
    target_table: str
    encoding: str
    delimiter: str
    window_column: str | None
    key_columns: tuple[str, ...]
    required: tuple[str, ...]
    datetime_columns: tuple[str, ...]
    decimal_columns: tuple[str, ...]
    on_error: str
    fields: dict[str, str]


def load_mapping(path: Path) -> CsvMapping:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CsvMappingError(f"{path}: mapping must be a mapping")
    for key in ("dataset", "resource", "target_table", "key_columns", "fields"):
        if key not in data:
            raise CsvMappingError(f"{path}: missing {key}")
    fields = data["fields"]
    if not isinstance(fields, dict) or not fields:
        raise CsvMappingError(f"{path}: fields must be a non-empty mapping")
    targets = {str(value) for value in fields.values()}
    key_columns = tuple(str(value) for value in data["key_columns"])
    for column in key_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: key column {column} is not mapped")
    required = tuple(str(value) for value in data.get("required", key_columns))
    for column in required:
        if column not in targets:
            raise CsvMappingError(f"{path}: required column {column} is not mapped")
    datetime_columns = tuple(str(value) for value in data.get("datetime_columns", ()))
    decimal_columns = tuple(str(value) for value in data.get("decimal_columns", ()))
    for column in datetime_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: datetime_columns contains unmapped {column}")
    for column in decimal_columns:
        if column not in targets:
            raise CsvMappingError(f"{path}: decimal_columns contains unmapped {column}")
    on_error = str(data.get("on_error", "skip"))
    if on_error not in {"skip", "raise"}:
        raise CsvMappingError(f"{path}: on_error must be skip or raise")
    window_column = data.get("window_column")
    if window_column is not None:
        window_column = str(window_column)
        if window_column not in targets:
            raise CsvMappingError(f"{path}: window_column {window_column} is not mapped")
    return CsvMapping(
        dataset=str(data["dataset"]),
        resource=str(data["resource"]),
        target_table=str(data["target_table"]),
        encoding=str(data.get("encoding", "utf-8-sig")),
        delimiter=str(data.get("delimiter", ",")),
        window_column=window_column,
        key_columns=key_columns,
        required=required,
        datetime_columns=datetime_columns,
        decimal_columns=decimal_columns,
        on_error=on_error,
        fields={str(key): str(value) for key, value in fields.items()},
    )


def load_mappings(directory: Path) -> dict[str, CsvMapping]:
    mappings: dict[str, CsvMapping] = {}
    for path in sorted(directory.glob("*.yml")):
        mapping = load_mapping(path)
        if mapping.resource in mappings:
            raise CsvMappingError(f"{path}: duplicate resource {mapping.resource}")
        mappings[mapping.resource] = mapping
    return mappings
```

- [ ] **Step 4: 写 CSV 适配器**

`app/adapters/csv/adapter.py`：

```python
import csv
import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.adapters.csv.mapping import CsvMapping, load_mappings
from app.adapters.values import parse_datetime, parse_decimal


class CsvImportError(PermanentError):
    pass


class CsvImportAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, csv_dir: str | Path, mappings_dir: str | Path) -> None:
        self._csv_dir = Path(csv_dir)
        self._mappings = load_mappings(Path(mappings_dir))
        self.errors: list[str] = []

    async def fetch_orders(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("orders", window)

    async def fetch_after_sales(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("after_sales", window)

    async def fetch_settlements(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("settlements", window)

    async def fetch_live_rooms(self, window: TimeWindow) -> list[dict[str, Any]]:
        return self._fetch("live_rooms", window)

    def _fetch(self, resource: str, window: TimeWindow) -> list[dict[str, Any]]:
        self.errors = []
        mapping = self._mappings.get(resource)
        if mapping is None:
            raise PermanentError(f"csv mapping not found for {resource}")
        files = sorted((self._csv_dir / mapping.dataset).glob("*.csv"))
        if not files:
            return []
        records: dict[tuple[str, ...], dict[str, Any]] = {}
        for path in files:
            for row in self._read_file(path, mapping, window):
                key = tuple(str(row[column]) for column in mapping.key_columns)
                records[key] = row
        return list(records.values())

    def _read_file(
        self, path: Path, mapping: CsvMapping, window: TimeWindow
    ) -> list[dict[str, Any]]:
        text = self._read_text(path, mapping.encoding)
        reader = csv.DictReader(io.StringIO(text), delimiter=mapping.delimiter)
        rows: list[dict[str, Any]] = []
        for line_no, source_row in enumerate(reader, start=2):
            normalized_row = {
                (key or "").strip().lstrip("﻿"): (value or "").strip()
                for key, value in source_row.items()
                if key is not None
            }
            try:
                row = self._convert_row(normalized_row, mapping, source_row)
                if row is None:
                    continue
                if mapping.window_column and not _in_window(
                    row.get(mapping.window_column), window
                ):
                    continue
                rows.append(row)
            except CsvImportError as exc:
                message = f"{path}:{line_no}: {exc}"
                if mapping.on_error == "raise":
                    raise CsvImportError(message) from exc
                self.errors.append(message)
        return rows

    def _convert_row(
        self,
        row: dict[str, str],
        mapping: CsvMapping,
        source_row: dict[str, str],
    ) -> dict[str, Any] | None:
        if not any(row.values()):
            return None
        converted: dict[str, Any] = {}
        for source_header, target in mapping.fields.items():
            if source_header not in row:
                continue
            value: Any = row[source_header]
            if target in mapping.datetime_columns:
                value = parse_datetime(value)
            elif target in mapping.decimal_columns:
                value = parse_decimal(value)
            converted[target] = value
        for column in mapping.required:
            value = converted.get(column)
            if value is None or value == "":
                raise CsvImportError(f"required column {column} is empty")
        for column in mapping.datetime_columns:
            if column in converted and converted[column] is None:
                raise CsvImportError(f"datetime column {column} is invalid")
        for column in mapping.decimal_columns:
            if column in converted and converted[column] is None:
                raise CsvImportError(f"decimal column {column} is invalid")
        converted["raw_json"] = {
            str(key): value for key, value in source_row.items() if key is not None
        }
        return converted

    @staticmethod
    def _read_text(path: Path, encoding: str) -> str:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            return path.read_text(encoding="gb18030")


def _in_window(value: object, window: TimeWindow) -> bool:
    if not isinstance(value, datetime):
        return False
    return window.start_at <= value < window.end_at
```

注意：只有「源表头存在且值无法解析」才算错误；CSV 没导出某个可选时间列时不会报错。

- [ ] **Step 5: 写默认映射 YAML**

`app/adapters/csv/mappings/orders.yml`：

```yaml
dataset: orders
resource: orders
target_table: ods_order
encoding: utf-8-sig
delimiter: ","
window_column: pay_at
key_columns: [order_id]
required: [order_id]
datetime_columns: [pay_at, create_at, update_at]
decimal_columns: [pay_amount]
on_error: skip
fields:
  订单编号: order_id
  order_id: order_id
  店铺ID: shop_id
  shop_id: shop_id
  订单状态: order_status
  order_status: order_status
  实付金额: pay_amount
  pay_amount: pay_amount
  支付时间: pay_at
  pay_at: pay_at
  下单时间: create_at
  create_at: create_at
  更新时间: update_at
  update_at: update_at
  达人ID: talent_id
  talent_id: talent_id
  直播间ID: room_id
  room_id: room_id
  渠道类型: channel_type
  channel_type: channel_type
  内容类型: content_type
  content_type: content_type
```

`app/adapters/csv/mappings/after_sales.yml`：

```yaml
dataset: after_sales
resource: after_sales
target_table: ods_after_sale
encoding: utf-8-sig
delimiter: ","
window_column: apply_at
key_columns: [after_sale_id]
required: [after_sale_id]
datetime_columns: [apply_at, finish_at, update_at]
decimal_columns: [refund_amount]
on_error: skip
fields:
  售后单号: after_sale_id
  after_sale_id: after_sale_id
  订单编号: order_id
  order_id: order_id
  售后类型: type
  type: type
  售后状态: status
  status: status
  退款金额: refund_amount
  refund_amount: refund_amount
  申请时间: apply_at
  apply_at: apply_at
  完成时间: finish_at
  finish_at: finish_at
  更新时间: update_at
  update_at: update_at
```

`app/adapters/csv/mappings/settlements.yml`：

```yaml
dataset: settlements
resource: settlements
target_table: ods_settlement
encoding: utf-8-sig
delimiter: ","
window_column: settle_at
key_columns: [settlement_id]
required: [settlement_id]
datetime_columns: [settle_at]
decimal_columns: [settle_amount, commission_amount, talent_commission, service_fee, platform_fee]
on_error: skip
fields:
  结算单号: settlement_id
  settlement_id: settlement_id
  订单编号: order_id
  order_id: order_id
  结算时间: settle_at
  settle_at: settle_at
  结算金额: settle_amount
  settle_amount: settle_amount
  佣金金额: commission_amount
  commission_amount: commission_amount
  达人佣金: talent_commission
  talent_commission: talent_commission
  服务费: service_fee
  service_fee: service_fee
  平台服务费: platform_fee
  platform_fee: platform_fee
```

`app/adapters/csv/mappings/live_rooms.yml`：

```yaml
dataset: live_rooms
resource: live_rooms
target_table: ods_live_room
encoding: utf-8-sig
delimiter: ","
window_column: null
key_columns: [room_id]
required: [room_id]
datetime_columns: [start_at, end_at]
decimal_columns: []
on_error: skip
fields:
  直播间ID: room_id
  room_id: room_id
  店铺ID: shop_id
  shop_id: shop_id
  达人ID: talent_id
  talent_id: talent_id
  直播间标题: title
  title: title
  开播时间: start_at
  start_at: start_at
  下播时间: end_at
  end_at: end_at
  状态: status
  status: status
```

创建目录占位：

```bash
mkdir -p data/csv/orders data/csv/after_sales data/csv/settlements data/csv/live_rooms
touch data/csv/orders/.gitkeep data/csv/after_sales/.gitkeep data/csv/settlements/.gitkeep data/csv/live_rooms/.gitkeep
```

- [ ] **Step 6: 运行测试**

Run: `uv run pytest tests/unit/test_csv_mapping.py tests/unit/test_csv_adapter.py -q`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add app/adapters/csv data/csv tests/unit/test_csv_mapping.py tests/unit/test_csv_adapter.py
git commit -m "feat: add CSV fallback import adapter

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 8: 适配器工厂

**Files:**
- Create: `app/adapters/factory.py`
- Test: `tests/unit/test_adapter_factory.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_adapter_factory.py`：

```python
import base64

from app.adapters.csv.adapter import CsvImportAdapter
from app.adapters.douyin.adapter import DouyinShopAdapter
from app.adapters.factory import AdapterFactory
from app.adapters.qianchuan.adapter import QianchuanAdapter
from app.core.settings import Settings


class FakeSession:
    def __init__(self) -> None:
        self.rows = {}

    async def get(self, model, key):
        return self.rows.get(key)

    def add(self, row) -> None:
        return None

    async def commit(self) -> None:
        return None


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


async def test_builds_douyin_shop_adapter() -> None:
    settings = make_settings(
        douyin_app_key="key",
        douyin_app_secret="secret",
        douyin_access_token="token",
    )
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("douyin_shop")
    assert isinstance(adapter, DouyinShopAdapter)
    await factory.close()


async def test_builds_qianchuan_adapter() -> None:
    settings = make_settings(
        qianchuan_access_token="token",
        qianchuan_advertiser_pairs="1:2,3:4",
    )
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("douyin_qianchuan")
    assert isinstance(adapter, QianchuanAdapter)
    await factory.close()


async def test_builds_csv_adapter(tmp_path) -> None:
    settings = make_settings(csv_import_dir=str(tmp_path), csv_mappings_dir="app/adapters/csv/mappings")
    factory = AdapterFactory(settings, FakeSession())
    adapter = await factory.get("csv_import")
    assert isinstance(adapter, CsvImportAdapter)
    await factory.close()


async def test_unknown_adapter_is_rejected() -> None:
    factory = AdapterFactory(make_settings(), FakeSession())
    try:
        await factory.get("nope")
    except Exception as exc:
        assert "unknown adapter" in str(exc)
    else:
        raise AssertionError("expected unknown adapter error")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_adapter_factory.py -q`
Expected: FAIL。

- [ ] **Step 3: 写实现**

`app/adapters/factory.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter, PermanentError
from app.adapters.credentials import CredentialResolver
from app.adapters.csv.adapter import CsvImportAdapter
from app.adapters.douyin.adapter import DouyinShopAdapter
from app.adapters.douyin.client import DouyinClient
from app.adapters.douyin.token import DouyinTokenProvider
from app.adapters.qianchuan.adapter import QianchuanAdapter, parse_advertiser_pairs
from app.adapters.qianchuan.client import QianchuanClient
from app.core.settings import Settings


class AdapterFactory:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        self._settings = settings
        self._resolver = CredentialResolver(session, settings)
        self._cache: dict[str, BaseAdapter] = {}

    async def get(self, name: str) -> BaseAdapter:
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        if name == "douyin_shop":
            adapter: BaseAdapter = await self._douyin_shop()
        elif name == "douyin_qianchuan":
            adapter = await self._qianchuan()
        elif name == "csv_import":
            adapter = CsvImportAdapter(
                self._settings.csv_import_dir,
                self._settings.csv_mappings_dir,
            )
        else:
            raise PermanentError(f"unknown adapter: {name}")
        self._cache[name] = adapter
        return adapter

    async def _douyin_shop(self) -> DouyinShopAdapter:
        token = await self._resolver.get("douyin.access_token")
        client = DouyinClient(
            app_key=await self._resolver.get("douyin.app_key"),
            app_secret=await self._resolver.get("douyin.app_secret"),
            access_token=token,
            base_url=self._settings.douyin_base_url,
            timeout=self._settings.http_timeout_seconds,
        )
        provider = DouyinTokenProvider(client, self._resolver)
        return DouyinShopAdapter(client, provider)

    async def _qianchuan(self) -> QianchuanAdapter:
        token = await self._resolver.get("qianchuan.access_token")
        pairs = parse_advertiser_pairs(
            await self._resolver.get("qianchuan.advertiser_pairs")
        )
        client = QianchuanClient(
            access_token=token,
            base_url=self._settings.qianchuan_base_url,
            timeout=self._settings.http_timeout_seconds,
        )
        return QianchuanAdapter(client, pairs)

    async def close(self) -> None:
        for adapter in self._cache.values():
            await adapter.close()
        self._cache.clear()
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/unit/test_adapter_factory.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add app/adapters/factory.py tests/unit/test_adapter_factory.py
git commit -m "feat: add adapter factory

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 9: 入仓服务：UPSERT、重试、超时、fetch_log、水位

**Files:**
- Create: `app/ingest/__init__.py`
- Create: `app/ingest/service.py`
- Test: `tests/unit/test_ingest_service.py`
- Test: `tests/integration/test_ingest.py`（本任务先建集成测试，Task 12 统一跑）

- [ ] **Step 1: 写失败测试**

`tests/unit/test_ingest_service.py`：

```python
from datetime import datetime

from sqlalchemy.dialects import mysql

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.db.ods_models import OdsOrder
from app.ingest.service import RESOURCE_SPECS, build_upsert
from app.scheduler.models import JobDefinition, RetryPolicy


class FakeAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, rows: list[dict], fail_times: int = 0) -> None:
        self.rows = rows
        self.fail_times = fail_times
        self.calls = 0

    async def fetch_orders(self, window: TimeWindow) -> list[dict]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise PermanentError("boom")
        return self.rows


class FakeFactory:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter
        self.closed = False

    async def get(self, name: str) -> BaseAdapter:
        return self.adapter

    async def close(self) -> None:
        self.closed = True


def test_resource_specs_cover_ingest_resources() -> None:
    assert set(RESOURCE_SPECS) == {
        "orders",
        "after_sales",
        "settlements",
        "live_rooms",
        "ad_cost",
    }
    assert RESOURCE_SPECS["orders"].method == "fetch_orders"


def test_build_upsert_excludes_primary_key_from_update_set() -> None:
    table = OdsOrder.__table__
    stmt = build_upsert(
        table,
        [{"platform": "douyin", "order_id": "o1", "raw_json": {}, "batch_id": "b",
          "fetched_at": datetime(2026, 10, 27)}],
    )
    compiled = str(stmt.compile(dialect=mysql.dialect()))
    assert "ON DUPLICATE KEY UPDATE" in compiled
    assert "platform = VALUES(platform)" not in compiled
    assert "order_id = VALUES(order_id)" not in compiled


def test_job_definition_defaults_to_sql_kind() -> None:
    job = JobDefinition(
        id="demo",
        lane="demo",
        schedule="0 1 * * *",
        resource="demo",
        window="day",
    )
    assert job.kind == "sql"
    assert job.adapter == ""


def test_retry_policy_defaults() -> None:
    assert RetryPolicy().max_attempts == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_ingest_service.py -q`
Expected: FAIL。

- [ ] **Step 3: 写实现**

`app/ingest/__init__.py`：

```python
"""ODS 入仓服务。"""
```

`app/ingest/service.py`：

```python
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import Table
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.adapters.factory import AdapterFactory
from app.adapters.retry import retry_call
from app.core.settings import Settings
from app.db.models import EtlModelRun, EtlWatermark
from app.db.ods_models import (
    OdsAdCost,
    OdsAfterSale,
    OdsFetchLog,
    OdsLiveRoom,
    OdsOrder,
    OdsSettlement,
)
from app.scheduler.models import JobDefinition

PLATFORM_BY_ADAPTER = {
    "douyin_shop": "douyin",
    "douyin_qianchuan": "douyin",
    "csv_import": "douyin",
}
CHUNK_SIZE = 500


@dataclass(frozen=True)
class ResourceSpec:
    method: str
    table: type[Any]


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "orders": ResourceSpec("fetch_orders", OdsOrder),
    "after_sales": ResourceSpec("fetch_after_sales", OdsAfterSale),
    "settlements": ResourceSpec("fetch_settlements", OdsSettlement),
    "live_rooms": ResourceSpec("fetch_live_rooms", OdsLiveRoom),
    "ad_cost": ResourceSpec("fetch_ad_cost", OdsAdCost),
}


def build_upsert(table: Table, rows: list[dict[str, Any]]) -> Any:
    stmt = mysql_insert(table).values(rows)
    primary_keys = {column.name for column in table.primary_key.columns}
    updates = {
        column.name: stmt.inserted[column.name]
        for column in table.columns
        if column.name not in primary_keys and column.name != "etl_create_at"
    }
    return stmt.on_duplicate_key_update(**updates)


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._factory = adapter_factory or AdapterFactory(settings, session)

    async def run(
        self,
        job: JobDefinition,
        run_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        spec = RESOURCE_SPECS.get(job.resource)
        if spec is None:
            raise PermanentError(f"unsupported ingest resource: {job.resource}")

        window = TimeWindow(start_at, end_at)
        started = time.monotonic()
        attempts = 0
        platform = PLATFORM_BY_ADAPTER.get(job.adapter, "")
        rows: list[dict[str, Any]] = []
        try:
            async with asyncio.timeout(job.timeout_seconds):
                adapter = await self._factory.get(job.adapter)
                platform = adapter.platform or platform
                method = getattr(adapter, spec.method)

                async def call() -> list[dict[str, Any]]:
                    nonlocal attempts
                    attempts += 1
                    return await method(window)

                result = await retry_call(call, job.retry)
                rows = result.value
                await self._upsert(spec.table, rows, platform)
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_success(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                record_count=len(rows),
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
            )
            return len(rows)
        except TimeoutError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_failure(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
                error=f"timeout after {job.timeout_seconds}s",
            )
            raise TimeoutError(
                f"ingest timed out after {job.timeout_seconds}s"
            ) from exc
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._record_failure(
                job=job,
                spec=spec,
                run_id=run_id,
                window=window,
                platform=platform,
                retry_count=max(0, attempts - 1),
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise
        finally:
            await self._factory.close()

    async def _upsert(
        self, table_type: type[Any], rows: list[dict[str, Any]], platform: str
    ) -> None:
        if not rows:
            return
        now = datetime.now(ZoneInfo(self._settings.timezone)).replace(tzinfo=None)
        batch_id = uuid4().hex
        prepared: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            record.setdefault("platform", platform)
            record["batch_id"] = batch_id
            record["fetched_at"] = now
            prepared.append(record)
        table = table_type.__table__
        for index in range(0, len(prepared), CHUNK_SIZE):
            chunk = prepared[index : index + CHUNK_SIZE]
            await self._session.execute(build_upsert(table, chunk))
        await self._session.commit()

    async def _record_success(
        self,
        *,
        job: JobDefinition,
        spec: ResourceSpec,
        run_id: int,
        window: TimeWindow,
        platform: str,
        record_count: int,
        retry_count: int,
        duration_ms: int,
    ) -> None:
        self._session.add(
            EtlModelRun(
                run_id=run_id,
                model_name=f"ingest:{job.resource}",
                target_table=spec.table.__tablename__,
                layer="ods",
                status="success",
                row_count=record_count,
                duration_ms=duration_ms,
            )
        )
        self._session.add(
            OdsFetchLog(
                platform=platform,
                resource=job.resource,
                window_start=window.start_at,
                window_end=window.end_at,
                status="success",
                record_count=record_count,
                retry_count=retry_count,
                duration_ms=duration_ms,
            )
        )
        await self._advance_watermark(job.resource, platform, window.end_at)
        await self._session.commit()

    async def _record_failure(
        self,
        *,
        job: JobDefinition,
        spec: ResourceSpec,
        run_id: int,
        window: TimeWindow,
        platform: str,
        retry_count: int,
        duration_ms: int,
        error: str,
    ) -> None:
        try:
            await self._session.rollback()
            self._session.add(
                EtlModelRun(
                    run_id=run_id,
                    model_name=f"ingest:{job.resource}",
                    target_table=spec.table.__tablename__,
                    layer="ods",
                    status="failed",
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            self._session.add(
                OdsFetchLog(
                    platform=platform,
                    resource=job.resource,
                    window_start=window.start_at,
                    window_end=window.end_at,
                    status="failed",
                    record_count=0,
                    retry_count=retry_count,
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            await self._session.commit()
        except Exception:
            logger.exception("failed to record ingest failure for {}", job.id)
            await self._session.rollback()

    async def _advance_watermark(
        self, resource: str, platform: str, end_at: datetime
    ) -> None:
        row = await self._session.get(EtlWatermark, (resource, platform))
        if row is None:
            self._session.add(
                EtlWatermark(
                    resource=resource,
                    platform=platform,
                    last_success_at=end_at,
                )
            )
        elif end_at > row.last_success_at:
            row.last_success_at = end_at
```

- [ ] **Step 4: 扩展 JobDefinition**

修改 `app/scheduler/models.py`：

```python
@dataclass(frozen=True)
class JobDefinition:
    id: str
    lane: str
    schedule: str
    resource: str
    window: str
    depends_on: tuple[str, ...] = ()
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: int = 900
    enabled: bool = True
    kind: str = "sql"
    adapter: str = ""
```

- [ ] **Step 5: 写集成测试**

`tests/integration/test_ingest.py`：

```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.adapters.base import BaseAdapter, PermanentError, TimeWindow
from app.core.settings import Settings
from app.db.models import EtlModelRun, EtlRun, EtlWatermark
from app.db.ods_models import OdsFetchLog, OdsOrder
from app.ingest.service import IngestionService
from app.scheduler.models import JobDefinition, RetryPolicy

pytestmark = pytest.mark.integration


class FakeAdapter(BaseAdapter):
    platform = "douyin"
    lane = "csv_import"

    def __init__(self, rows: list[dict], fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail

    async def fetch_orders(self, window: TimeWindow) -> list[dict]:
        if self.fail:
            raise PermanentError("fetch failed")
        return self.rows


class FakeFactory:
    def __init__(self, adapter: FakeAdapter) -> None:
        self.adapter = adapter

    async def get(self, name: str) -> BaseAdapter:
        return self.adapter

    async def close(self) -> None:
        return None


def make_job() -> JobDefinition:
    return JobDefinition(
        id="test_ingest",
        lane="csv_import",
        schedule="0 1 * * *",
        resource="orders",
        window="day",
        retry=RetryPolicy(max_attempts=1, backoff_seconds=0),
        timeout_seconds=30,
        kind="ingest",
        adapter="csv_import",
    )


def make_row(order_id: str) -> dict:
    return {
        "order_id": order_id,
        "shop_id": "s1",
        "pay_amount": "10.00",
        "pay_at": datetime(2026, 10, 26, 10),
        "raw_json": {"order_id": order_id},
    }


async def create_run(db_session, start_at, end_at) -> int:
    run = EtlRun(
        job_id="test_ingest",
        window_start=start_at,
        window_end=end_at,
        status="running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run.id


async def test_ingest_is_idempotent_and_advances_watermark(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([make_row("o1"), make_row("o2")])),
    )

    assert await service.run(make_job(), run_id, start_at, end_at) == 2
    assert await service.run(make_job(), run_id, start_at, end_at) == 2

    orders = (await db_session.execute(select(OdsOrder))).scalars().all()
    assert len(orders) == 2

    logs = (await db_session.execute(select(OdsFetchLog))).scalars().all()
    assert len(logs) == 2
    assert all(log.status == "success" for log in logs)

    watermark = await db_session.get(EtlWatermark, ("orders", "douyin"))
    assert watermark is not None
    assert watermark.last_success_at == end_at

    model_runs = (
        await db_session.execute(
            select(EtlModelRun).where(EtlModelRun.run_id == run_id)
        )
    ).scalars().all()
    assert len(model_runs) == 2
    assert all(item.layer == "ods" for item in model_runs)


async def test_backfill_does_not_lower_watermark(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([make_row("o1")])),
    )
    await service.run(make_job(), run_id, start_at, end_at)

    older_start = start_at - timedelta(days=2)
    await service.run(make_job(), run_id, older_start, start_at)
    watermark = await db_session.get(EtlWatermark, ("orders", "douyin"))
    assert watermark.last_success_at == end_at


async def test_failure_writes_failed_log_and_reraises(db_session) -> None:
    start_at = datetime(2026, 10, 26)
    end_at = start_at + timedelta(days=1)
    run_id = await create_run(db_session, start_at, end_at)
    service = IngestionService(
        db_session,
        Settings(_env_file=None),
        adapter_factory=FakeFactory(FakeAdapter([], fail=True)),
    )

    with pytest.raises(PermanentError, match="fetch failed"):
        await service.run(make_job(), run_id, start_at, end_at)

    logs = (await db_session.execute(select(OdsFetchLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert "fetch failed" in (logs[0].error or "")
```

- [ ] **Step 6: 运行单元测试**

Run: `uv run pytest tests/unit/test_ingest_service.py tests/unit/test_job_loader.py -q`
Expected: PASS（`test_ingest_service` 需要先完成 Task 9 Step 4 的 JobDefinition 扩展）。

- [ ] **Step 7: 提交**

```bash
git add app/ingest app/scheduler/models.py tests/unit/test_ingest_service.py tests/integration/test_ingest.py
git commit -m "feat: add idempotent ODS ingestion service

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 10: Job 分派、执行器 CLI 与调度接线

**Files:**
- Modify: `app/scheduler/loader.py`
- Modify: `app/scheduler/service.py`
- Modify: `app/executor/demo.py`
- Create: `app/executor/cli.py`
- Modify: `app/main.py`
- Modify: `app/api/jobs.py`
- Test: `tests/unit/test_job_loader.py`
- Test: `tests/unit/test_api.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_job_loader.py` 追加：

```python
def test_ingest_job_requires_adapter(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "ingest.yml",
        """
id: ingest_orders
lane: csv_import
schedule: "0 1 * * *"
resource: orders
window: day
kind: ingest
""",
    )
    with pytest.raises(JobConfigError, match="adapter"):
        load_job_file(path)


def test_ingest_job_parses_adapter(tmp_path: Path) -> None:
    path = write_job(
        tmp_path,
        "ingest.yml",
        """
id: ingest_orders
lane: csv_import
schedule: "0 1 * * *"
resource: orders
window: day
kind: ingest
adapter: csv_import
""",
    )
    job = load_job_file(path)
    assert job.kind == "ingest"
    assert job.adapter == "csv_import"
```

修改 `tests/unit/test_api.py` 的 `test_jobs_endpoint`：

```python
def test_jobs_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    ids = {item["id"] for item in body["data"]}
    assert "demo_pipeline" in ids
    demo = next(item for item in body["data"] if item["id"] == "demo_pipeline")
    assert demo["kind"] == "sql"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/unit/test_job_loader.py tests/unit/test_api.py -q`
Expected: FAIL（`kind` 未解析、序列化缺少字段）。

- [ ] **Step 3: 修改 loader**

在 `app/scheduler/loader.py` 的 `enabled` 解析之后增加：

```python
    kind = str(data.get("kind", "sql"))
    if kind not in {"sql", "ingest"}:
        raise JobConfigError(f"{path}: kind must be sql or ingest")
    adapter = str(data.get("adapter", ""))
    if kind == "ingest" and not adapter:
        raise JobConfigError(f"{path}: ingest job requires adapter")
```

在 `JobDefinition(...)` 构造中增加：

```python
        kind=kind,
        adapter=adapter,
```

- [ ] **Step 4: 修改 JobService**

把 `app/scheduler/service.py` 的 `run` 方法中创建 `renderer` 到执行 quality 的整段替换为：

```python
            if job.kind == "ingest":
                from app.ingest.service import IngestionService

                ingestion = IngestionService(self._session, self._settings)
                await ingestion.run(job, run.id, start_at, end_at)
            else:
                renderer = TableRenderer(self._settings.warehouse_layout)
                models = load_models(Path(self._settings.model_dir))
                quality_checks: list[QualityCheck] = []
                if (
                    self._settings.warehouse_layout == "single_db"
                    and "ads_demo_talent_daily" in models
                ):
                    quality_checks.append(
                        QualityCheck(
                            model_name="ads_demo_talent_daily",
                            test_name="gmv_not_null",
                            sql=(
                                "SELECT COUNT(*) FROM "
                                f"{renderer.ref('ads_demo_talent_daily')} WHERE gmv IS NULL"
                            ),
                        )
                    )
                runner = PipelineRunner(
                    self._session,
                    self._settings.model_dir,
                    renderer,
                )
                await runner.run(run.id, start_at, end_at)
                quality = (
                    await run_checks(self._session, run.id, quality_checks)
                    if quality_checks
                    else []
                )
                if any(item.status == "failed" for item in quality):
                    raise RuntimeError("quality checks failed")
```

保留外层 `try` 的 success/failed 处理。最终结构应是：

```python
            try:
                if job.kind == "ingest":
                    ...
                else:
                    ...
                run.status = "success"
                run.finished_at = self._now()
                await self._session.commit()
            except Exception as exc:
                run.status = "failed"
                run.error = str(exc)
                run.finished_at = self._now()
                await self._session.commit()
                raise
```

- [ ] **Step 5: 修改 API 序列化**

`app/api/jobs.py` 的 `_serialize` 增加：

```python
        "kind": job.kind,
        "adapter": job.adapter,
```

- [ ] **Step 6: 修改调度车道**

`app/main.py` 的 `LaneManager({"demo": 1, "csv_import": 2})` 改为：

```python
            lanes=LaneManager(
                {
                    "demo": 1,
                    "douyin_shop": 1,
                    "douyin_qianchuan": 1,
                    "csv_import": 2,
                }
            ),
```

- [ ] **Step 7: 修改执行器**

`app/executor/demo.py`：

```python
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.settings import get_settings
from app.db.engine import get_session_factory
from app.scheduler.loader import load_jobs
from app.scheduler.service import JobService, default_window


async def run_job(
    job_id: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> int:
    settings = get_settings()
    jobs = load_jobs(Path(settings.job_dir))
    job = jobs[job_id]
    if (start_at is None) != (end_at is None):
        raise ValueError("start_at and end_at must be provided together")
    if start_at is None or end_at is None:
        start_at, end_at = default_window(job.window, tz=settings.timezone)
    async with get_session_factory()() as session:
        service = JobService(session, settings, owner=f"cli:{uuid4().hex}")
        return await service.run(job, start_at, end_at)


async def run_demo(job_id: str = "demo_pipeline") -> int:
    return await run_job(job_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="demo_pipeline")
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    start_at = datetime.fromisoformat(args.start) if args.start else None
    end_at = datetime.fromisoformat(args.end) if args.end else None
    run_id = asyncio.run(run_job(args.job, start_at, end_at))
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
```

`app/executor/cli.py`：

```python
from app.executor.demo import main

if __name__ == "__main__":
    main()
```

注意：`python -m app.executor.cli` 会执行 `main()`；`app/executor/demo.py` 也保留可直接运行。

- [ ] **Step 8: 运行测试**

Run: `uv run pytest tests/unit/test_job_loader.py tests/unit/test_api.py tests/unit/test_ingest_service.py -q`
Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add app/scheduler/loader.py app/scheduler/service.py app/executor/demo.py app/executor/cli.py app/main.py app/api/jobs.py tests/unit/test_job_loader.py tests/unit/test_api.py
git commit -m "feat: dispatch ingest jobs and add manual runner

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 11: Job YAML、环境变量与运行文档

**Files:**
- Create: `jobs/douyin_orders_daily.yml`
- Create: `jobs/douyin_after_sales_daily.yml`
- Create: `jobs/douyin_settlements_daily.yml`
- Create: `jobs/qianchuan_ad_cost_daily.yml`
- Create: `jobs/csv_orders_daily.yml`
- Create: `jobs/csv_after_sales_daily.yml`
- Create: `jobs/csv_settlements_daily.yml`
- Create: `jobs/csv_live_rooms_daily.yml`
- Modify: `.env.example`
- Modify: `Makefile`
- Create: `docs/ingestion.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `.gitignore`
- Modify: `docker-compose.yml`

- [ ] **Step 1: 写 Job YAML**

`jobs/douyin_orders_daily.yml`：

```yaml
id: douyin_orders_daily
lane: douyin_shop
schedule: "10 1 * * *"
resource: orders
window: day
kind: ingest
adapter: douyin_shop
depends_on: []
retry:
  max_attempts: 3
  backoff_seconds: 30
timeout_seconds: 900
enabled: false
```

`jobs/douyin_after_sales_daily.yml`：

```yaml
id: douyin_after_sales_daily
lane: douyin_shop
schedule: "20 1 * * *"
resource: after_sales
window: day
kind: ingest
adapter: douyin_shop
depends_on: []
retry:
  max_attempts: 3
  backoff_seconds: 30
timeout_seconds: 900
enabled: false
```

`jobs/douyin_settlements_daily.yml`：

```yaml
id: douyin_settlements_daily
lane: douyin_shop
schedule: "30 1 * * *"
resource: settlements
window: day
kind: ingest
adapter: douyin_shop
depends_on: []
retry:
  max_attempts: 3
  backoff_seconds: 30
timeout_seconds: 900
enabled: false
```

`jobs/qianchuan_ad_cost_daily.yml`：

```yaml
id: qianchuan_ad_cost_daily
lane: douyin_qianchuan
schedule: "40 1 * * *"
resource: ad_cost
window: day
kind: ingest
adapter: douyin_qianchuan
depends_on: []
retry:
  max_attempts: 3
  backoff_seconds: 30
timeout_seconds: 900
enabled: false
```

`jobs/csv_orders_daily.yml`：

```yaml
id: csv_orders_daily
lane: csv_import
schedule: "0 2 * * *"
resource: orders
window: day
kind: ingest
adapter: csv_import
depends_on: []
retry:
  max_attempts: 2
  backoff_seconds: 10
timeout_seconds: 600
enabled: true
```

`jobs/csv_after_sales_daily.yml`：

```yaml
id: csv_after_sales_daily
lane: csv_import
schedule: "10 2 * * *"
resource: after_sales
window: day
kind: ingest
adapter: csv_import
depends_on: []
retry:
  max_attempts: 2
  backoff_seconds: 10
timeout_seconds: 600
enabled: true
```

`jobs/csv_settlements_daily.yml`：

```yaml
id: csv_settlements_daily
lane: csv_import
schedule: "20 2 * * *"
resource: settlements
window: day
kind: ingest
adapter: csv_import
depends_on: []
retry:
  max_attempts: 2
  backoff_seconds: 10
timeout_seconds: 600
enabled: true
```

`jobs/csv_live_rooms_daily.yml`：

```yaml
id: csv_live_rooms_daily
lane: csv_import
schedule: "30 2 * * *"
resource: live_rooms
window: day
kind: ingest
adapter: csv_import
depends_on: []
retry:
  max_attempts: 2
  backoff_seconds: 10
timeout_seconds: 600
enabled: true
```

- [ ] **Step 2: 更新 `.env.example`**

在 `METRICS_FILE` 之后追加：

```bash
# 抖店开放平台（M1 可选；API Job 默认 enabled: false）
DOUYIN_APP_KEY=
DOUYIN_APP_SECRET=
DOUYIN_ACCESS_TOKEN=
DOUYIN_REFRESH_TOKEN=
DOUYIN_SHOP_ID=
DOUYIN_BASE_URL=https://openapi-fxg.jinritemai.com

# 千川开放平台（M1 使用长期 access token，不做 OAuth 刷新）
QIANCHUAN_ACCESS_TOKEN=
# advertiser_id:aweme_id，多个用逗号分隔
QIANCHUAN_ADVERTISER_PAIRS=
QIANCHUAN_BASE_URL=https://api.oceanengine.com/open_api

# CSV 兜底目录与字段映射
CSV_IMPORT_DIR=data/csv
CSV_MAPPINGS_DIR=app/adapters/csv/mappings
HTTP_TIMEOUT_SECONDS=20
```

- [ ] **Step 3: 更新 Makefile**

把 `seed` 之后增加：

```makefile
run-job:
	uv run python -m app.executor.cli --job $(JOB)
```

`.PHONY` 行增加 `run-job`。

- [ ] **Step 4: 写 `docs/ingestion.md`**

```markdown
# M1 接入层

## 能做什么

- 抖店开放平台：订单、售后、结算，按自然日窗口增量拉取，写入 ODS。
- 千川开放平台：全域投放抖音号维度消耗，按账户 × 抖音号组合拉取，写入 `ods_ad_cost`。
- CSV 兜底：订单、售后、结算、店播排期；店播排期 v1 唯一来源为 CSV。
- 所有写入幂等：ODS 按业务主键 UPSERT，`ods_fetch_log` 保留每次结果，`etl_watermark` 记录成功窗口。
- 失败重试：HTTP 5xx/超时/限流重试；鉴权失败和参数错误不重试。Job 级重试按 YAML 的 `retry` 配置。
- 超时：Job 级 `timeout_seconds`，超时后写入失败日志并将 run 标记 failed。

## 凭证

优先级：环境变量 > `sys_config` 表 > 空值。

抖店：

```bash
DOUYIN_APP_KEY=...
DOUYIN_APP_SECRET=...
DOUYIN_ACCESS_TOKEN=...        # 可选；留空时用 app key/secret 自动 token.create
DOUYIN_REFRESH_TOKEN=...       # 可选；token.create 后自动加密写回 sys_config
```

千川：

```bash
QIANCHUAN_ACCESS_TOKEN=...
QIANCHUAN_ADVERTISER_PAIRS=123:456,789:012
```

没有凭证时，`douyin_*` / `qianchuan_*` Job 保持 `enabled: false`；配置后把 YAML 的 `enabled` 改为 `true`。

## CSV 目录

```text
data/csv/
├─ orders/*.csv
├─ after_sales/*.csv
├─ settlements/*.csv
└─ live_rooms/*.csv
```

字段映射在 `app/adapters/csv/mappings/*.yml`。支持中英文表头；默认编码 `utf-8-sig`，失败时回退 `gb18030`。映射支持：

- `window_column`：按时间列过滤窗口；`live_rooms` 设为 `null`，导入未来排期。
- `key_columns`：去重与 UPSERT 主键。
- `datetime_columns` / `decimal_columns`：解析失败按 `on_error` 处理。
- `on_error: skip|raise`：默认跳过坏行并记录到 `CsvImportAdapter.errors`。

## 运行

```bash
# 昨日窗口
uv run python -m app.executor.cli --job csv_live_rooms_daily

# 手动补数
uv run python -m app.executor.cli --job douyin_orders_daily \
  --start "2026-10-24 00:00:00" --end "2026-10-25 00:00:00"
```

补数不会降低 `etl_watermark`；水位只前进。

## M1 限制

- 抖店官方没有稳定的直播场次列表接口；店播排期只走 CSV。`DouyinShopAdapter.fetch_live_rooms()` 会明确报不支持。
- 千川只支持长期 access token，不实现 OAuth 刷新。
- M1 不落订单商品行、分钟直播统计、达人档案；这些在 M2 处理。
- 真实凭证联调需要单独配置 `.env`；CI 只跑 Mock 契约测试和 CSV 集成测试。
```

- [ ] **Step 5: 更新 README 与架构文档**

README 在「快速开始」后增加：

```markdown
## M1 接入

```bash
# 可选：配置抖店/千川凭证后，把对应 jobs/*.yml 的 enabled 改为 true
cp .env.example .env

# CSV 兜底：把导出文件放到 data/csv/<dataset>/*.csv
uv run python -m app.executor.cli --job csv_live_rooms_daily
```

字段映射、凭证优先级、补数和水位规则见 [docs/ingestion.md](docs/ingestion.md)。
```

`docs/architecture.md` 在 `MySQL` 模块图后增加：

```markdown
## M1 接入层

```text
SourceAdapter
├─ DouyinShopAdapter    订单 / 售后 / 结算
├─ QianchuanAdapter     投放消耗
└─ CsvImportAdapter     订单 / 售后 / 结算 / 店播排期

IngestionService
├─ MySQL UPSERT（按业务主键幂等）
├─ ods_fetch_log（每次拉取结果）
├─ etl_watermark（成功窗口只前进）
└─ etl_model_run（layer=ods）
```

`JobDefinition.kind=ingest` 的任务走 `IngestionService`；`kind=sql` 保持 M0 的 SQL Runner 路径。
```

并在 M0 已知限制后追加 M1 限制：

```markdown
## M1 已知限制

- 店播排期只从 CSV 导入；抖店适配器不提供官方直播场次接口。
- 千川使用长期 access token，未实现 OAuth 刷新。
- 订单商品行、分钟直播统计、达人档案留待 M2。
- API Job 默认关闭，配置凭证后手动启用。
```

- [ ] **Step 6: 更新 `.gitignore` 与 compose**

`.gitignore` 追加：

```gitignore
data/csv/**/*.csv
```

`docker-compose.yml` 的 `api` 服务增加 volume：

```yaml
    volumes:
      - ./data/csv:/app/data/csv
```

- [ ] **Step 7: 运行配置与加载测试**

Run:
```bash
uv run python -c "from pathlib import Path; from app.scheduler.loader import load_jobs; jobs=load_jobs(Path('jobs')); print(sorted(jobs)); assert all(j.kind in {'sql','ingest'} for j in jobs.values()); assert all(j.adapter for j in jobs.values() if j.kind=='ingest')"
uv run pytest tests/unit/test_job_loader.py tests/unit/test_api.py -q
```
Expected: 打印 9 个 job；测试 PASS。

- [ ] **Step 8: 提交**

```bash
git add jobs .env.example Makefile docs/ingestion.md README.md docs/architecture.md .gitignore docker-compose.yml
git commit -m "feat: add M1 ingest jobs and docs

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 12: 集成验证、全量测试与操作日志

**Files:**
- Modify: `tests/conftest.py`
- Modify: `doc/操作日志.md`

- [ ] **Step 1: 让集成 fixture 建 ODS 表**

在 `tests/conftest.py` 的 `db_engine` fixture 中，`import app.db.demo_models  # noqa: F401` 之后增加：

```python
    import app.db.ods_models  # noqa: F401
```

- [ ] **Step 2: 启动 MySQL 并迁移**

Run:
```bash
docker compose up -d mysql
uv run alembic upgrade head
docker compose exec -T mysql mysql -uroot -proot ecom_ops -e "SHOW TABLES;"
```
Expected: 健康检查通过；表列表包含 `ods_order`、`ods_after_sale`、`ods_settlement`、`ods_live_room`、`ods_ad_cost`、`ods_fetch_log`。

- [ ] **Step 3: 跑集成测试**

Run: `RUN_INTEGRATION=1 uv run pytest -q`
Expected: 全部 PASS（含 `tests/integration/test_ingest.py` 3 个用例）。

- [ ] **Step 4: 做一次 CSV 端到端冒烟**

Run:
```bash
mkdir -p data/csv/live_rooms
cat > data/csv/live_rooms/demo_rooms.csv <<'CSV'
直播间ID,店铺ID,达人ID,直播间标题,开播时间,下播时间,状态
room_demo_001,shop_demo,talent_demo,演示场次,2026-10-26 20:00:00,2026-10-26 23:00:00,ended
CSV
uv run python -m app.executor.cli --job csv_live_rooms_daily --start "2026-10-26 00:00:00" --end "2026-10-27 00:00:00"
docker compose exec -T mysql mysql -uroot -proot ecom_ops -e "SELECT platform,room_id,start_at,end_at FROM ods_live_room WHERE room_id='room_demo_001'; SELECT resource,status,record_count FROM ods_fetch_log ORDER BY id DESC LIMIT 1; SELECT resource,platform,last_success_at FROM etl_watermark WHERE resource='live_rooms';"
```
Expected:
- `ods_live_room` 有 `room_demo_001`；
- 最新 fetch log：`live_rooms | success | 1`；
- watermark：`live_rooms | douyin | 2026-10-27 00:00:00`。

- [ ] **Step 5: 跑 lint/type/全量测试**

Run:
```bash
uv run ruff check .
uv run mypy app
uv run pytest -q
```
Expected: 全部通过。

- [ ] **Step 6: 更新操作日志**

在 `doc/操作日志.md` 追加：

```markdown
## 2026-10-27 M1 接入层

- 新增 ODS 表与 ORM：`ods_order`、`ods_after_sale`、`ods_settlement`、`ods_live_room`、`ods_ad_cost`、`ods_fetch_log`；迁移 `0003_ods_tables`。
- 新增适配器层：抖店签名/Token/订单/售后/结算、千川消耗、CSV 兜底（订单/售后/结算/店播排期）。
- 新增 `IngestionService`：按业务主键 MySQL UPSERT、batch_id、fetch_log、watermark、Job 级重试与超时。
- Job 定义新增 `kind: ingest` 与 `adapter`；新增 8 个接入 Job；API 类 Job 默认 `enabled: false`。
- 新增手动/补数入口：`uv run python -m app.executor.cli --job <id> [--start ... --end ...]`。
- 测试：适配器 Mock 契约、CSV 解析、凭证加密、UPSERT 编译、集成幂等/水位/失败日志。
- 范围决策：店播排期唯一来源为 CSV；抖店官方直播场次接口不实现；千川仅长期 Token。
- 真实抖店/千川凭证联调未执行（本机无凭证），留待配置 `.env` 后跑 smoke。
```

- [ ] **Step 7: 提交**

```bash
git add tests/conftest.py doc/操作日志.md
git commit -m "test: verify M1 ingestion with MySQL

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收清单

- [ ] `uv run pytest -q` 全绿。
- [ ] `RUN_INTEGRATION=1 uv run pytest -q` 全绿（含 3 个入仓集成用例）。
- [ ] `uv run ruff check .`、`uv run mypy app` 通过。
- [ ] `uv run alembic upgrade head` 在真实 MySQL 成功，ODS 表存在。
- [ ] CSV `live_rooms` 冒烟：ODS 有行、fetch log success、watermark 前进。
- [ ] 重复执行 CSV Job：ODS 行数不增长（UPSERT 幂等）。
- [ ] 失败场景：Mock 适配器抛错时 fetch log 为 failed，run 为 failed。
- [ ] `docs/ingestion.md` 说明凭证、CSV 目录、补数、M1 限制。
- [ ] 真实抖店/千川凭证 smoke 明确标注为未执行（等待凭证）。

---

## Self-Review

**1. 规格覆盖**

- 抖店订单/售后/结算：Task 3–5。
- 千川消耗：Task 6。
- 直播时段：Task 7 CSV `live_rooms`；范围决策已在开头和文档中明确「官方接口不实现」。
- CSV 兜底：Task 7。
- ODS 落库：Task 1、9。
- 失败重试：Task 2（通用）、Task 3/6（HTTP）、Task 9（Job 级）。
- 水位：Task 9。
- fetch_log：Task 1、9。
- 调度/车道：Task 10、11。
- 测试与文档：Task 12、11。

**2. 占位符扫描**

计划中没有 TBD/TODO；所有新增文件均给出完整代码或完整 YAML。适配器方法统一使用 `fetch_ad_cost`，没有遗留错误命名。

**3. 类型与命名一致性**

- 适配器方法统一为 `fetch_orders` / `fetch_after_sales` / `fetch_settlements` / `fetch_live_rooms` / `fetch_ad_cost`。
- `JobDefinition` 新增字段 `kind`、`adapter`，loader、JobService、API 序列化三处一致。
- `IngestionService` 使用 `ResourceSpec(method, table)`，与 `RESOURCE_SPECS` 的键 `orders`/`after_sales`/`settlements`/`live_rooms`/`ad_cost` 和 Job YAML 的 `resource` 一致。
- `Ods*` 表名与 CSV mapping 的 `target_table` 一致。
- 凭证键名统一为 `douyin.*` / `qianchuan.*`。
```
