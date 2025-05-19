SHOW CATALOGS;

SET CATALOG default_catalog;

SHOW DATABASES;

use industrial_warehouse;

CREATE TABLE staging_scada_stream (
  Timestamp DATETIME,
  Machine_ID VARCHAR(100),
  Power_Consumption_kW DOUBLE,
  Machine_Status VARCHAR(100),
  Alarm_Code VARCHAR(255)
)
ENGINE=OLAP
PRIMARY KEY(Timestamp, Machine_ID)
DISTRIBUTED BY HASH(Machine_ID) BUCKETS 10
PROPERTIES (
  "replication_num" = "1"
);

CREATE TABLE staging_iot_stream (
  Timestamp DATETIME,
  Machine_ID VARCHAR(100),
  Temperature_C DOUBLE,
  Vibration_mm_s DOUBLE,
  Pressure_bar DOUBLE
)
ENGINE=OLAP
PRIMARY KEY(Timestamp, Machine_ID)
DISTRIBUTED BY HASH(Machine_ID) BUCKETS 10
PROPERTIES (
  "replication_num" = "1"
);

CREATE TABLE staging_mes_stream (
  Timestamp DATETIME,
  Machine_ID VARCHAR(100),
  Operator_ID INT,
  Units_Produced INT,
  Defective_Units INT,
  Production_Time_min DOUBLE
)
ENGINE=OLAP
PRIMARY KEY(Timestamp, Machine_ID)
DISTRIBUTED BY HASH(Machine_ID) BUCKETS 10
PROPERTIES (
  "replication_num" = "1"
);


CREATE ROUTINE LOAD industrial_warehouse.load_scada_stream
ON staging_scada_stream
COLUMNS(Timestamp, Machine_ID, Power_Consumption_kW, Machine_Status, Alarm_Code)
PROPERTIES (
  "desired_concurrent_number" = "1",
  "format" = "json",
  "strip_outer_array" = "false",
  "timezone" = "Asia/Singapore"
)
FROM KAFKA (
  "kafka_broker_list" = "kafka:9092",
  "kafka_topic" = "scada-data",
  "property.kafka_default_offsets" = "OFFSET_BEGINNING"
);


CREATE ROUTINE LOAD industrial_warehouse.load_iot_stream
ON staging_iot_stream
COLUMNS(Timestamp, Machine_ID, Temperature_C, Vibration_mm_s, Pressure_bar)
PROPERTIES (
  "desired_concurrent_number" = "1",
  "format" = "json",
  "strip_outer_array" = "false",
  "timezone" = "Asia/Singapore"
)
FROM KAFKA (
  "kafka_broker_list" = "kafka:9092",
  "kafka_topic" = "iot-data",
  "property.kafka_default_offsets" = "OFFSET_BEGINNING"
);


CREATE ROUTINE LOAD industrial_warehouse.load_mes_stream
ON staging_mes_stream
COLUMNS(Timestamp, Machine_ID, Operator_ID, Units_Produced, Defective_Units, Production_Time_min)
PROPERTIES (
  "desired_concurrent_number" = "1",
  "format" = "json",
  "strip_outer_array" = "false",
  "timezone" = "Asia/Singapore"
)
FROM KAFKA (
  "kafka_broker_list" = "kafka:9092",
  "kafka_topic" = "mes-data",
  "property.kafka_default_offsets" = "OFFSET_BEGINNING"
);


SHOW ROUTINE LOAD FOR industrial_warehouse.load_mes_stream;

SHOW ROUTINE LOAD FOR industrial_warehouse.load_iot_stream;

SHOW ROUTINE LOAD FOR industrial_warehouse.load_scada_stream;