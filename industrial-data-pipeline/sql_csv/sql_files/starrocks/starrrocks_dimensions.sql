SET CATALOG default_catalog;

DROP DATABASE IF EXISTS industrial_warehouse;

CREATE DATABASE industrial_warehouse;

use industrial_warehouse;

CREATE TABLE AlarmCodes (
  AlarmID INT,
  AlarmDescription STRING
)
PRIMARY KEY(AlarmID)
DISTRIBUTED BY HASH(AlarmID) BUCKETS 4
PROPERTIES("replication_num" = "1");

INSERT INTO AlarmCodes
SELECT * FROM mysql_catalog.industrial_data.AlarmCodes;

CREATE TABLE MachineStatus (
  StatusID INT,
  StatusName STRING
)
PRIMARY KEY(StatusID)
DISTRIBUTED BY HASH(StatusID) BUCKETS 4
PROPERTIES("replication_num" = "1");

INSERT INTO MachineStatus
SELECT * FROM mysql_catalog.industrial_data.MachineStatus;


CREATE TABLE Machines (
  MachineID INT,
  MachineName STRING
)
PRIMARY KEY(MachineID)
DISTRIBUTED BY HASH(MachineID) BUCKETS 4
PROPERTIES("replication_num" = "1");

INSERT INTO Machines
SELECT * FROM mysql_catalog.industrial_data.Machines;

CREATE TABLE Operators (
  OperatorID INT
)
PRIMARY KEY(OperatorID)
DISTRIBUTED BY HASH(OperatorID) BUCKETS 4
PROPERTIES("replication_num" = "1");

INSERT INTO Operators
SELECT * FROM mysql_catalog.industrial_data.Operators;