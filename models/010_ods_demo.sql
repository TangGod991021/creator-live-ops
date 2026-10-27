-- @layer: ods
-- @target: ods_demo_order
-- @depends_on:
-- @incremental_key: order_id
-- @window: day

INSERT INTO {{ ref('ods_demo_order') }}
  (platform, order_id, pay_amount, pay_at, talent_id, room_id, raw_json, fetched_at)
VALUES
  ('douyin', 'demo-1001', 199.00, DATE_ADD('{{ start_at }}', INTERVAL 10 MINUTE), 'talent_a', 'room_1', '{}', NOW()),
  ('douyin', 'demo-1002', 299.00, DATE_ADD('{{ start_at }}', INTERVAL 20 MINUTE), 'talent_a', 'room_1', '{}', NOW()),
  ('douyin', 'demo-1003', 99.00,  DATE_ADD('{{ start_at }}', INTERVAL 30 MINUTE), 'talent_b', 'room_2', '{}', NOW()),
  ('douyin', 'demo-1004', 399.00, DATE_ADD('{{ start_at }}', INTERVAL 40 MINUTE), 'talent_b', 'room_2', '{}', NOW())
AS new
ON DUPLICATE KEY UPDATE
  pay_amount = new.pay_amount,
  pay_at = new.pay_at,
  talent_id = new.talent_id,
  room_id = new.room_id,
  fetched_at = new.fetched_at;
