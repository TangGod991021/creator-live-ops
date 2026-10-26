# creator-live-ops

达人店播经营数据底座。M0 骨架开发中。

## 快速开始

```bash
cp .env.example .env
uv sync
docker compose up -d mysql
make migrate
make dev
curl http://127.0.0.1:8000/health
```
