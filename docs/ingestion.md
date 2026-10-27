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
