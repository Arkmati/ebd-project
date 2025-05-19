SHOW CATALOGS;

SET CATALOG default_catalog;

SHOW DATABASES;

use industrial_warehouse;

SHOW TABLES;

DROP TABLE IF EXISTS machine_metrics;

-- final machine metrics table

CREATE TABLE machine_metrics (
  Timestamp DATETIME,
  Machine_ID VARCHAR(100),
  Temperature_C DOUBLE,
  Vibration_mm_s DOUBLE,
  Pressure_bar DOUBLE,
  Operator_ID VARCHAR(100),
  Units_Produced INT,
  Defective_Units INT,
  Production_Time_min DOUBLE,
  Power_Consumption_kW DOUBLE,
  Machine_Status_ID INT,
  Machine_Status VARCHAR(100),
  Alarm_ID INT,
  Alarm_Code VARCHAR(255)
)
ENGINE=OLAP
PRIMARY KEY(Timestamp, Machine_ID)
DISTRIBUTED BY HASH(Machine_ID) BUCKETS 10
PROPERTIES (
  "replication_num" = "1"
);

-- final machine metrics table data


INSERT INTO machine_metrics
WITH iot_data AS (
  SELECT * 
  FROM mysql_catalog.industrial_data.IOT
),
mes_ranked AS (
  SELECT 
    i.MachineID,
    i.Timestamp,
    m.Operator_ID,
    m.Units_Produced,
    m.Defective_Units,
    m.Production_Time_min,
    ROW_NUMBER() OVER (
      PARTITION BY i.MachineID, i.Timestamp
      ORDER BY ABS(TIMESTAMPDIFF(SECOND,
        STR_TO_DATE(i.Timestamp, '%Y-%m-%d %H:%i:%s'),
        STR_TO_DATE(m.Timestamp, '%Y-%m-%d %H:%i:%s')))
    ) AS rn
  FROM iot_data i
  JOIN mysql_catalog.industrial_data.synthetic_mes_data m
    ON i.MachineID = m.MachineID
   AND ABS(TIMESTAMPDIFF(SECOND,
        STR_TO_DATE(i.Timestamp, '%Y-%m-%d %H:%i:%s'),
        STR_TO_DATE(m.Timestamp, '%Y-%m-%d %H:%i:%s'))) <= 3600
),
best_mes AS (
  SELECT * FROM mes_ranked WHERE rn = 1
),
scada_ranked AS (
  SELECT 
    i.MachineID,
    i.Timestamp,
    s.Power_Consumption_kW,
    s.Machine_Status_ID,
    s.ALARM_CODE_ID,
    ROW_NUMBER() OVER (
      PARTITION BY i.MachineID, i.Timestamp
      ORDER BY ABS(TIMESTAMPDIFF(SECOND,
        STR_TO_DATE(i.Timestamp, '%Y-%m-%d %H:%i:%s'),
        STR_TO_DATE(s.Timestamp, '%Y-%m-%d %H:%i:%s')))
    ) AS rn
  FROM iot_data i
  JOIN mysql_catalog.industrial_data.synthetic_scada_data s
    ON i.MachineID = s.MachineID
   AND ABS(TIMESTAMPDIFF(SECOND,
        STR_TO_DATE(i.Timestamp, '%Y-%m-%d %H:%i:%s'),
        STR_TO_DATE(s.Timestamp, '%Y-%m-%d %H:%i:%s'))) <= 900
),
best_scada AS (
  SELECT * FROM scada_ranked WHERE rn = 1
)
SELECT
  i.Timestamp,
  i.MachineID,
  i.Temperature_C,
  i.Vibration_mm_s,
  i.Pressure_bar,
  m.Operator_ID,
  m.Units_Produced,
  m.Defective_Units,
  m.Production_Time_min,
  s.Power_Consumption_kW,
  s.Machine_Status_ID,
  ms.StatusName AS Machine_Status,
  s.ALARM_CODE_ID,
  ac.AlarmDescription AS Alarm_Code
FROM iot_data i
LEFT JOIN best_mes m ON i.MachineID = m.MachineID AND i.Timestamp = m.Timestamp
LEFT JOIN best_scada s ON i.MachineID = s.MachineID AND i.Timestamp = s.Timestamp
LEFT JOIN industrial_warehouse.MachineStatus ms ON s.Machine_Status_ID = ms.StatusID
LEFT JOIN industrial_warehouse.AlarmCodes ac ON s.ALARM_CODE_ID = ac.AlarmID;