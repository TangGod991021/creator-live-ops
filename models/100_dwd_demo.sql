-- @layer: dwd
-- @target: dwd_demo_order
-- @depends_on: ods_demo_order
-- @incremental_key: order_id
-- @window: day

INSERT INTO {{ ref('dwd_demo_order') }}
  (platform, order_id, pay_amount, stat_date, talent_id, room_id, etl_create_at, etl_update_at)
SELECT
  new.platform,
  new.order_id,
  new.pay_amount,
  DATE(new.pay_at),
  new.talent_id,
  new.room_id,
  NOW(),
  NOW()
FROM (
  SELECT platform, order_id, pay_amount, pay_at, talent_id, room_id
  FROM {{ ref('ods_demo_order') }}
  WHERE pay_at >= '{{ start_at }}' AND pay_at < '{{ end_at }}'
) AS new
ON DUPLICATE KEY UPDATE
  pay_amount = new.pay_amount,
  stat_date = DATE(new.pay_at),
  talent_id = new.talent_id,
  room_id = new.room_id;
