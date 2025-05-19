DROP MATERIALIZED VIEW IF EXISTS mv_machine_metrics_stream;

CREATE MATERIALIZED VIEW mv_machine_metrics_stream
DISTRIBUTED BY HASH(Machine_ID) BUCKETS 10
REFRESH ASYNC EVERY (INTERVAL 1 MINUTE)
AS
WITH
  mes_ranked AS (
    SELECT
      iot.Timestamp AS iot_ts,
      iot.Machine_ID AS iot_mid,
      mes.Timestamp AS mes_ts,
      mes.Machine_ID AS mes_mid,
      mes.Operator_ID,
      mes.Units_Produced,
      mes.Defective_Units,
      mes.Production_Time_min,
      ROW_NUMBER() OVER (
        PARTITION BY iot.Machine_ID, iot.Timestamp
        ORDER BY ABS(TIMESTAMPDIFF(SECOND, iot.Timestamp, mes.Timestamp))
      ) AS rn
    FROM staging_iot_stream iot
    JOIN staging_mes_stream mes
      ON iot.Machine_ID = mes.Machine_ID
     AND ABS(TIMESTAMPDIFF(SECOND, iot.Timestamp, mes.Timestamp)) <= 3600
  ),
  best_mes AS (
    SELECT *
    FROM mes_ranked
    WHERE rn = 1
  ),
  scada_ranked AS (
    SELECT
      iot.Timestamp AS iot_ts,
      iot.Machine_ID AS iot_mid,
      scada.Timestamp AS scada_ts,
      scada.Machine_ID AS scada_mid,
      scada.Power_Consumption_kW,
      scada.Machine_Status,
      scada.Alarm_Code,
      ROW_NUMBER() OVER (
        PARTITION BY iot.Machine_ID, iot.Timestamp
        ORDER BY ABS(TIMESTAMPDIFF(SECOND, iot.Timestamp, scada.Timestamp))
      ) AS rn
    FROM staging_iot_stream iot
    JOIN staging_scada_stream scada
      ON iot.Machine_ID = scada.Machine_ID
     AND ABS(TIMESTAMPDIFF(SECOND, iot.Timestamp, scada.Timestamp)) <= 900
  ),
  best_scada AS (
    SELECT *
    FROM scada_ranked
    WHERE rn = 1
  )
SELECT
  iot.Timestamp,
  iot.Machine_ID,
  iot.Temperature_C,
  iot.Vibration_mm_s,
  iot.Pressure_bar,
  mes.Operator_ID,
  mes.Units_Produced,
  mes.Defective_Units,
  mes.Production_Time_min,
  scada.Power_Consumption_kW,
  scada.Machine_Status,
  CASE
    WHEN scada.Alarm_Code = '' THEN 'None'
    ELSE scada.Alarm_Code
  END AS Alarm_Code
FROM staging_iot_stream iot
LEFT JOIN best_mes mes
  ON iot.Machine_ID = mes.iot_mid AND iot.Timestamp = mes.iot_ts
LEFT JOIN best_scada scada
  ON iot.Machine_ID = scada.iot_mid AND iot.Timestamp = scada.iot_ts;