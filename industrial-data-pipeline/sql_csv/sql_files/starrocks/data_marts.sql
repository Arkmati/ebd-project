use industrial_warehouse;

DROP MATERIALIZED VIEW IF EXISTS mv_unit_production_daily;

-- Daily
CREATE MATERIALIZED VIEW mv_unit_production_daily
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE(Timestamp) AS Day,
  SUM(Units_Produced) AS Units_Produced
FROM machine_metrics
GROUP BY Machine_ID, Day;


SELECT * from mv_unit_production_daily order by Day, Machine_ID;

-- Weekly

DROP MATERIALIZED VIEW IF EXISTS mv_unit_production_weekly;

CREATE MATERIALIZED VIEW mv_unit_production_weekly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(DATE_TRUNC('week', Timestamp), '%x-W%v') AS ISO_Week,
  SUM(Units_Produced) AS Units_Produced
FROM machine_metrics
GROUP BY Machine_ID, ISO_Week;

SELECT * from mv_unit_production_weekly order by ISO_Week,Machine_ID;

-- Monthly

DROP MATERIALIZED VIEW IF EXISTS mv_unit_production_monthly;

CREATE MATERIALIZED VIEW mv_unit_production_monthly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(Timestamp, '%Y-%m') AS Month,
  SUM(Units_Produced) AS Units_Produced
FROM machine_metrics
GROUP BY Machine_ID, Month;

SELECT * from mv_unit_production_monthly order by Month,Machine_ID;

-- Machine Failures


-- Daily

DROP MATERIALIZED VIEW IF EXISTS mv_machine_failures_daily;


CREATE MATERIALIZED VIEW mv_machine_failures_daily
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE(Timestamp) AS Day,
  COUNT(*) AS Failure_Count
FROM machine_metrics
WHERE NOT (
  (Machine_Status = 'Idle' AND Alarm_Code = 'None') OR
  (Machine_Status = 'Running' AND Alarm_Code = 'None')
)
GROUP BY Machine_ID, Day;

SELECT * from mv_machine_failures_daily order by Day, Machine_ID;


-- Weekly


DROP MATERIALIZED VIEW IF EXISTS mv_machine_failures_weekly;

CREATE MATERIALIZED VIEW mv_machine_failures_weekly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(DATE_TRUNC('week', Timestamp), '%x-W%v') AS ISO_Week,
  COUNT(*) AS Failure_Count
FROM machine_metrics
WHERE NOT (
  (Machine_Status = 'Idle' AND Alarm_Code = 'None') OR
  (Machine_Status = 'Running' AND Alarm_Code = 'None')
)
GROUP BY Machine_ID, ISO_Week;

SELECT * from mv_machine_failures_weekly order by ISO_Week, Machine_ID;


-- Monthly

DROP MATERIALIZED VIEW IF EXISTS  mv_machine_failures_monthly;

CREATE MATERIALIZED VIEW mv_machine_failures_monthly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(Timestamp, '%Y-%m') AS Month,
  COUNT(*) AS Failure_Count
FROM machine_metrics
WHERE NOT (
  (Machine_Status = 'Idle' AND Alarm_Code = 'None') OR
  (Machine_Status = 'Running' AND Alarm_Code = 'None')
)
GROUP BY Machine_ID, Month;

SELECT * from mv_machine_failures_monthly order by Month, Machine_ID;


-- Machine Efficiency

-- Daily

DROP MATERIALIZED VIEW IF EXISTS  mv_machine_efficiency_daily;

CREATE MATERIALIZED VIEW mv_machine_efficiency_daily
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE(Timestamp) AS Day,
  ROUND(SUM(Units_Produced - Defective_Units) / NULLIF(SUM(Units_Produced), 0) * 100, 2) AS Efficiency_Percentage
FROM machine_metrics
GROUP BY Machine_ID, Day;

select * from mv_machine_efficiency_daily order by Day, Machine_ID;

-- Weekly

DROP MATERIALIZED VIEW IF EXISTS  mv_machine_efficiency_weekly;

CREATE MATERIALIZED VIEW mv_machine_efficiency_weekly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(DATE_TRUNC('week', Timestamp), '%x-W%v') AS ISO_Week,
  ROUND(SUM(Units_Produced - Defective_Units) / NULLIF(SUM(Units_Produced), 0) * 100, 2) AS Efficiency_Percentage
FROM machine_metrics
GROUP BY Machine_ID, ISO_Week;

select * from mv_machine_efficiency_weekly order by ISO_Week, Machine_ID;

-- Monthly

DROP MATERIALIZED VIEW IF EXISTS  mv_machine_efficiency_monthly;

CREATE MATERIALIZED VIEW mv_machine_efficiency_monthly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(Timestamp, '%Y-%m') AS Month,
  ROUND(SUM(Units_Produced - Defective_Units) / NULLIF(SUM(Units_Produced), 0) * 100, 2) AS Efficiency_Percentage
FROM machine_metrics
GROUP BY Machine_ID, Month;

select * from mv_machine_efficiency_monthly order by Month, Machine_ID;


-- Power Consumption per Machine


-- Daily

DROP MATERIALIZED VIEW IF EXISTS  mv_power_consumption_daily;

CREATE MATERIALIZED VIEW mv_power_consumption_daily
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE(Timestamp) AS Day,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY Machine_ID, Day;

select * from mv_power_consumption_daily order by Day, Machine_ID;


-- Weekly

DROP MATERIALIZED VIEW IF EXISTS  mv_power_consumption_weekly;

CREATE MATERIALIZED VIEW mv_power_consumption_weekly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(DATE_TRUNC('week', Timestamp), '%x-W%v') AS ISO_Week,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY Machine_ID, ISO_Week;

select * from mv_power_consumption_weekly order by ISO_Week, Machine_ID;

-- Monthly

DROP MATERIALIZED VIEW IF EXISTS  mv_power_consumption_monthly;

CREATE MATERIALIZED VIEW mv_power_consumption_monthly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  Machine_ID,
  DATE_FORMAT(Timestamp, '%Y-%m') AS Month,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY Machine_ID, Month;

select * from mv_power_consumption_monthly order by Month, Machine_ID;


-- Total Plant Daily consumption

DROP MATERIALIZED VIEW IF EXISTS  mv_total_power_consumption_daily;

CREATE MATERIALIZED VIEW mv_total_power_consumption_daily
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  DATE(Timestamp) AS Day,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY Day;

select * from mv_total_power_consumption_daily order by Day;

-- Total Plant Weekly consumption

DROP MATERIALIZED VIEW IF EXISTS  mv_total_power_consumption_weekly;

CREATE MATERIALIZED VIEW mv_total_power_consumption_weekly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  DATE_FORMAT(DATE_TRUNC('week', Timestamp), '%x-W%v') AS ISO_Week,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY ISO_Week;

select * from mv_total_power_consumption_weekly order by ISO_Week;

-- Total Plant Monthly consumption

DROP MATERIALIZED VIEW IF EXISTS  mv_total_power_consumption_monthly;

CREATE MATERIALIZED VIEW mv_total_power_consumption_monthly
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
SELECT
  DATE_FORMAT(Timestamp, '%Y-%m') AS Month,
  SUM(Power_Consumption_kW) AS Total_Power_kW
FROM machine_metrics
GROUP BY Month;

select * from mv_total_power_consumption_monthly order by Month;