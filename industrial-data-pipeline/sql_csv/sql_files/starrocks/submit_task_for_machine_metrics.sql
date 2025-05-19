SELECT * FROM information_schema.tasks WHERE task_name = 'insert_machine_metrics';

-- only run DROP TASK if the task exists, else below drop task gives error
DROP TASK insert_machine_metrics;

SUBMIT TASK insert_machine_metrics
SCHEDULE EVERY(INTERVAL 1 MINUTE)
AS
INSERT INTO machine_metrics
SELECT
  mv.Timestamp,
  CAST(SUBSTRING_INDEX(mv.Machine_ID, '_', -1) AS INT) AS Machine_ID,
  mv.Temperature_C,
  mv.Vibration_mm_s,
  mv.Pressure_bar,
  mv.Operator_ID,
  mv.Units_Produced,
  mv.Defective_Units,
  mv.Production_Time_min,
  mv.Power_Consumption_kW,
  ms.StatusID AS Machine_Status_ID,
  ms.StatusName AS Machine_Status,
  ac.AlarmID AS Alarm_ID,
  mv.Alarm_Code
FROM mv_machine_metrics_stream mv
LEFT JOIN industrial_warehouse.MachineStatus ms
  ON mv.Machine_Status = ms.StatusName
LEFT JOIN industrial_warehouse.AlarmCodes ac
  ON mv.Alarm_Code = ac.AlarmDescription
WHERE NOT EXISTS (
  SELECT 1 FROM machine_metrics t
  WHERE t.Timestamp = mv.Timestamp
    AND t.Machine_ID = CAST(SUBSTRING_INDEX(mv.Machine_ID, '_', -1) AS INT)
);

-- change abve schedule to every 1 minute
-- also add task for data marts/ stream machine metrics for every minute
  SELECT *
FROM information_schema.task_runs;