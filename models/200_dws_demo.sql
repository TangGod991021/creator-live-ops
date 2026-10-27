-- @layer: dws
-- @target: dws_demo_talent_daily
-- @depends_on: dwd_demo_order
-- @incremental_key: stat_date
-- @window: day

INSERT INTO {{ ref('dws_demo_talent_daily') }}
  (platform, talent_id, stat_date, gmv, order_count, etl_create_at, etl_update_at)
SELECT
  new.platform,
  new.talent_id,
  new.stat_date,
  new.gmv,
  new.order_count,
  NOW(),
  NOW()
FROM (
  SELECT
    platform,
    talent_id,
    stat_date,
    SUM(pay_amount) AS gmv,
    COUNT(*) AS order_count
  FROM {{ ref('dwd_demo_order') }}
  WHERE stat_date = DATE('{{ start_at }}')
  GROUP BY platform, talent_id, stat_date
) AS new
ON DUPLICATE KEY UPDATE
  gmv = new.gmv,
  order_count = new.order_count;
