use industrial_data;

DROP TABLE IF EXISTS  IOT;

CREATE TABLE IOT (
  Timestamp VARCHAR(50),
  Temperature_C DOUBLE,
  Vibration_mm_s DOUBLE,
  Pressure_bar DOUBLE,
  MachineID INT,
  FOREIGN KEY (MachineID) REFERENCES Machines(MachineID)
);


INSERT INTO IOT (Timestamp, Temperature_C, Vibration_mm_s, Pressure_bar, MachineID)
SELECT
  s.Timestamp,
  s.Temperature_C,
  s.Vibration_mm_s,
  s.Pressure_bar,
  m.MachineID
FROM staging_iot s
JOIN Machines m ON s.Machine_ID = m.MachineName;


DROP TABLE IF EXISTS  synthetic_mes_data;

CREATE TABLE synthetic_mes_data (
  Timestamp VARCHAR(50),
  Operator_ID INT,
  Units_Produced INT,
  Defective_Units INT,
  Production_Time_min INT,
  MachineID INT,
  FOREIGN KEY (Operator_ID) REFERENCES Operators(OperatorID),
  FOREIGN KEY (MachineID) REFERENCES Machines(MachineID)
);


INSERT INTO synthetic_mes_data (
  Timestamp, Operator_ID, Units_Produced, Defective_Units, Production_Time_min, MachineID
)
SELECT
  s.Timestamp,
  o.OperatorID,
  s.Units_Produced,
  s.Defective_Units,
  s.Production_Time_min,
  m.MachineID
FROM staging_mes s
JOIN Operators o ON s.Operator_ID  = o.OperatorID
JOIN Machines m ON s.Machine_ID  = m.MachineName;


DROP TABLE IF EXISTS  synthetic_scada_data;

CREATE TABLE synthetic_scada_data (
  Timestamp VARCHAR(50),
  Power_Consumption_kW DOUBLE,
  MachineID INT,
  ALARM_CODE_ID INT,
  Machine_Status_ID INT,
  FOREIGN KEY (MachineID) REFERENCES Machines(MachineID),
  FOREIGN KEY (ALARM_CODE_ID) REFERENCES AlarmCodes(AlarmID),
  FOREIGN KEY (Machine_Status_ID) REFERENCES MachineStatus(StatusID)
);

INSERT INTO synthetic_scada_data (
  Timestamp, Power_Consumption_kW, MachineID, ALARM_CODE_ID, Machine_Status_ID
)
SELECT

  s.Timestamp,
  s.Power_Consumption_kW,
  m.MachineID,
  a.AlarmID ,
  ms.StatusID
FROM staging_scada s
JOIN Machines m ON s.Machine_ID = m.MachineName
JOIN AlarmCodes a ON s.Alarm_Code = a.AlarmDescription
JOIN MachineStatus ms ON s.Machine_Status = ms.StatusName;