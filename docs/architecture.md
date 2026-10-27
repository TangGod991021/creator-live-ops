# 架构

```text
FastAPI
├─ api/            REST 接口
├─ scheduler/      任务定义、车道、DB 锁、调度
├─ executor/       任务执行入口
├─ warehouse/      SQL 模型解析、ref 渲染、DAG、Runner、质量
└─ db/             ORM、引擎、迁移

MySQL
├─ sys_* / etl_*   系统表
└─ ods_/dim_/dwd_/dws_/ads_  业务分层
```

## 一次运行的路径

1. `POST /api/v1/jobs/{id}/run` 或 APScheduler 触发。
2. `JobService` 获取 `sys_job_lock`，创建 `etl_run`。
3. `PipelineRunner` 加载 `models/*.sql`，解析头部元数据，拓扑排序。
4. 每个模型用 Jinja 渲染 `ref()` 与窗口变量，执行幂等 SQL。
5. 每个模型写 `etl_model_run`；失败则回滚并把 run 标为 failed。
6. 质量检查写 `etl_quality_result`。

## 分层与物理形态

- 逻辑层：`ods` / `dim` / `dwd` / `dws` / `ads`
- `single_db`：`dwd_order`
- `multi_schema`：`dwd.order`
- 由 `WAREHOUSE_LAYOUT` 切换。

## M0 已知限制

- `multi_schema` 仅为渲染层预留：当前迁移只在单库创建表，尚未创建 `ods/dim/dwd/dws/ads` schema，切换到多 schema 前需补迁移。
- `PipelineRunner` 统一使用 job 的窗口；模型头部的 `@window` / `@incremental_key` 已解析但尚未参与调度与增量回刷。
- `retry` / `timeout_seconds` 已进入任务定义，M0 尚未执行重试与超时取消；锁 TTL 会按 `timeout_seconds + 60` 设置。
- 质量检查目前仅内置 demo 表在 `single_db` 布局下的 `gmv_not_null`，真实业务任务需扩展为可配置检查。
