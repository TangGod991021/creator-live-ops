-- @layer: ads
-- @target: ads_demo_talent_daily
-- @depends_on: dws_demo_talent_daily
-- @incremental_key: stat_date
-- @window: day

INSERT INTO {{ ref('ads_demo_talent_daily') }}
  (platform, talent_id, stat_date, gmv, order_count, rank_no, etl_create_at, etl_update_at)
SELECT
  new.platform,
  new.talent_id,
  new.stat_date,
  new.gmv,
  new.order_count,
  new.rank_no,
  NOW(),
  NOW()
FROM (
  SELECT
    platform,
    talent_id,
    stat_date,
    gmv,
    order_count,
    RANK() OVER (PARTITION BY platform, stat_date ORDER BY gmv DESC) AS rank_no
  FROM {{ ref('dws_demo_talent_daily') }}
  WHERE stat_date = DATE('{{ start_at }}')
) AS new
ON DUPLICATE KEY UPDATE
  gmv = new.gmv,
  order_count = new.order_count,
  rank_no = new.rank_no;
