# creator-live-ops

达人店播经营数据底座。M0 骨架开发中。

## 快速开始（M0 Task 1 阶段）

```bash
uv sync
cp .env.example .env
uv run pytest -q
uv run uvicorn app.main:app --reload --port 8000
curl http://127.0.0.1:8000/health
```

> `Makefile` 为可选快捷方式，需要 GNU Make；`docker compose`、数据库迁移与演示管道会在后续 M0 任务中加入。
