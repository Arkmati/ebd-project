# Industrial Data Pipeline

## Description
This project implements a comprehensive industrial data processing and analytics platform that integrates various technologies for collecting, storing, processing, and visualizing Operational Technology Data. The platform includes components for:

- **Data Collection**: OPC UA server with Node-RED for industrial data acquisition
- **Data Streaming**: Kafka for real-time data streaming
- **Data Storage**: MySQL for relational data, InfluxDB for time-series data, MinIO for object storage
- **Data Processing & Warehousing**: Alternative approaches using either StarRocks or Apache Spark
- **Data Visualization**: Grafana & Apache Superset dashboarding, monitoring, and ML-driven predictive analytics.
- **Development Environment**: Jupyter notebooks for ETL processes, MES stream creation.

The platform provides two alternative implementations for data warehousing: a StarRocks-based approach using its native SQL capabilities and materialized views, or a Spark-based approach leveraging PySpark for flexible data transformations. Both approaches accomplish similar goals but through different technological means, giving users the choice based on their specific needs or expertise.

### Kafka Stream Configuration

The platform handles different data streams with optimized Kafka partitioning:

| Data Source | Ingestion Frequency | Total Records | Partitions |
|-------------|---------------------|---------------|------------|
| IoT         | Every minute        | 201,600       | 4          |
| SCADA       | Every 15 minutes    | 13,440        | 2          |
| MES         | Every hour          | 3,360         | 1          |

This partitioning strategy is designed to balance processing load and ensure efficient stream handling based on the volume and frequency of each data source.

## Why? (Motivation)
Modern industrial environments generate vast amounts of data from various sources like IoT sensors, SCADA systems, and MES (Manufacturing Execution Systems). This data holds valuable insights for operational efficiency, predictive maintenance, and quality control. However, efficiently capturing, processing, and analyzing this data presents significant challenges:

1. **Data Integration**: Combining data from heterogeneous industrial systems
2. **Real-time Processing**: Handling streaming data for timely decision-making
3. **Scalable Storage**: Managing large volumes of time-series and relational data
4. **Advanced Analytics**: Enabling complex queries and machine learning on industrial data
5. **Visualization**: Providing intuitive dashboards for monitoring and analysis

This platform addresses these challenges by offering two alternative approaches for data warehousing:

- **StarRocks Approach**: Uses StarRocks' native SQL and materialized views to process data directly from Kafka streams and MySQL. This approach leverages:
  - External catalogs to access MySQL data
  - Routine loads to ingest Kafka streams
  - Materialized views for real-time data joining
  - Scheduled tasks for fact table population
  - SQL-based data marts for analytics

- **Apache Spark Approach**: Uses PySpark to read from staging tables, perform complex transformations, and load into the fact table. This approach features:
  - Flexible temporal matching with window functions
  - Complex joins and transformations in a distributed framework
  - Direct writing to the fact table
  - Scheduled execution via cron

Users can implement either approach based on their requirements, existing skill sets, or specific use cases.

## Quick Start

### Prerequisites
- Docker and Docker Compose (v1.29.0 or higher)
- Git
- At least 8GB RAM available for Docker
- At least 20GB of free disk space
- DBeaver (for database management)

### Installation Steps

1. Switch to correct folder:
   ```bash
   cd industrial-data-pipeline
   ```

2. Create the external network (required for communication between services):
   ```bash
   docker network create industrial-data-pipeline_kafka-nifi-net
   ```

3. Start the core services:
   ```bash
   docker-compose up -d
   ```

4. Start additional services as needed:
   ```bash
   # Kafka and MinIO
   docker-compose -f docker-compose-kafka.yml up -d
   
   # InfluxDB, Telegraf, and Grafana
   docker-compose -f docker-compose-influx.yml up -d
   
   # OPC UA server and Node-RED
   docker-compose -f docker-compose-opcua.yml up -d
   
   # Apache Superset
   docker-compose -f docker-compose-superset.yml up -d
   ```

5. Create Kafka topics with the optimal partitioning strategy:
   ```bash
   # Create the IoT data topic with 4 partitions
   docker exec -it kafka kafka-topics --create --bootstrap-server kafka:9092 --replication-factor 1 --partitions 4 --topic iot-data
   
   # Create the SCADA data topic with 2 partitions
   docker exec -it kafka kafka-topics --create --bootstrap-server kafka:9092 --replication-factor 1 --partitions 2 --topic scada-data
   
   # Create the MES data topic with 1 partition
   docker exec -it kafka kafka-topics --create --bootstrap-server kafka:9092 --replication-factor 1 --partitions 1 --topic mes-data
   
   # Verify the topics were created
   docker exec -it kafka kafka-topics --list --bootstrap-server kafka:9092
   ```

### Database Setup and Data Loading

#### MySQL Database Setup

MySQL database setup is performed using DBeaver. Follow these steps:

1. Connect to MySQL in DBeaver using the following settings:
   - Server Host: localhost
   - Port: 3306
   - Username: root
   - Password: rootpassword
   - Database: (leave empty initially)

2. Create and set up the industrial_data database:
   - Right-click on the MySQL connection → Create → Database
   - Name it `industrial_data` and click OK
   - Select the new database in the navigation tree

3. Create metadata and staging tables:
   - Navigate to `sql_csv/sql_files/mysql/initial_data_load.sql` in the project
   - Open the file in DBeaver
   - Execute the script by clicking the "Execute SQL Script" button (or press Ctrl+Enter)
   - This will create dimension tables (Machines, MachineStatus, AlarmCodes, Operators) and staging tables

4. Load metadata from CSV files:
   - After the tables are created, right-click on each table and select "Import Data"
   - Import the corresponding CSV files from the `sql_csv/metadata` folder:
     - `Machines.csv` → `Machines` table
     - `MachineStatus.csv` → `MachineStatus` table
     - `AlarmCodes.csv` → `AlarmCodes` table
     - `Operators_data.csv` → `Operators` table
   - Follow the DBeaver import wizard, mapping columns as needed

5. Load historical data:
   - Similarly, import the CSV files from `sql_csv/one-time_load` folder:
     - `historical-iot.csv` → `staging_iot` table
     - `historical-mes.csv` → `staging_mes` table
     - `historical-scada.csv` → `staging_scada` table

6. Create and populate final tables with resolved foreign keys:
   - Navigate to `sql_csv/sql_files/mysql/synthetic_data_insertion.sql` in the project
   - Open the file in DBeaver
   - Execute the script to create and populate the `IOT`, `synthetic_mes_data`, and `synthetic_scada_data` tables
   - This script joins the staging tables with dimension tables to resolve foreign keys

#### StarRocks Database Setup

StarRocks setup is also performed using DBeaver:

1. Connect to StarRocks in DBeaver:
   - Add a new connection with the MySQL driver
   - Server Host: localhost
   - Port: 9030
   - Username: root
   - Password: (leave empty)

2. Execute the SQL scripts in the following order:

   - **Create catalogs and dimension tables**:
     - Open and execute `sql_csv/sql_files/starrocks/create_catalogs.sql`
     - Open and execute `sql_csv/sql_files/starrocks/starrrocks_dimensions.sql`

   - **Set up historical data processing**:
     - Open and execute `sql_csv/sql_files/starrocks/starrocks-historic-table.sql`

   - **Configure streaming data processing**:
     - Open and execute `sql_csv/sql_files/starrocks/create_staging_stream_tables.sql`
     - Open and execute `sql_csv/sql_files/starrocks/materialised_view_main.sql`
     - Open and execute `sql_csv/sql_files/starrocks/submit_task_for_machine_metrics.sql`

   - **Create data marts for analytics**:
     - Open and execute `sql_csv/sql_files/starrocks/data_marts.sql`

   Note: Execute each script completely before moving to the next one. Wait for any processing tasks to complete before proceeding.

### Data Stream Configuration

7. Configure Node-RED with OPC UA and Kafka integration:
   - Access Node-RED at http://localhost:1880
   - Install required Node-RED packages:
     - Go to the menu (top-right corner) → Manage palette → Install
     - Search and install:
       - `@opcua/for-node-red` - for OPC UA connectivity
       - `@asinino/node-red-kafkajs` - for Kafka integration
   - Import the provided flow:
     - Go to the menu → Import → select "Clipboard"
     - Paste the contents of `opcua-server/node-red-flow/flows.json` or upload the file
     - Click "Import"
   - Deploy the flow by clicking the "Deploy" button in the top-right corner
   - This will start sending IOT and SCADA data to Kafka topics

8. Set up MES Data Streams:
   - Upload MES streaming data to MinIO:
     - Access MinIO console at http://localhost:9001 (login with minioadmin/minioadmin)
     - Create a new bucket named `industrial-data` if it doesn't exist
     - Upload the `opcua-server/future-stream-mes.csv` file to this bucket
   - Run the MES streams simulation:
     - Access Jupyter at http://localhost:8888
     - Open the notebook `notebooks/mes_streams_creation/MES_streams_creation.ipynb`
     - Execute the notebook cells to start generating MES data streams to Kafka
     - This will create the `mes-data` topic in Kafka which will be consumed by Telegraf and StarRocks

   - Verify all data streams are flowing to Kafka:
     ```bash
     # Check IOT data stream
     docker exec -it kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic iot-data --from-beginning
     
     # Check SCADA data stream
     docker exec -it kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic scada-data --from-beginning
     
     # Check MES data stream
     docker exec -it kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic mes-data --from-beginning
     ```

## Usage

### Accessing Services

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Jupyter Notebook | http://localhost:8888 | Requires token from container logs |
| StarRocks (MySQL client) | localhost:9030 | user: root, no password |
| MySQL | localhost:3306 | user: root, password: rootpassword |
| Kafka | localhost:9093 | N/A |
| MinIO Console | http://localhost:9001 | user: minioadmin, password: minioadmin |
| Grafana | http://localhost:3000 | user: admin, password: admin |
| InfluxDB | http://localhost:8086 | user: iot_user, password: iot_password |
| Node-RED | http://localhost:1880 | N/A |
| Superset | http://localhost:8088 | user: admin, password: admin |
| Spark Master UI | http://localhost:8090 | N/A |

#### Accessing Jupyter Notebook

To access Jupyter Notebook, you need to retrieve the access token from the container logs:

```bash
# Get the Jupyter access token from logs
docker logs jupyter 2>&1 | grep "token=" | head -n 1
```

You should see a line similar to:
```
[I 2025-05-03 09:32:35.102 ServerApp]     http://127.0.0.1:8888/lab?token=48fa134827581277004576211a3014006878a4680ff16209
```

Copy the full URL with the token and paste it in your browser, or go to http://localhost:8888 and enter the token when prompted.

#### Configuring Apache Superset

After starting Superset with Docker Compose, follow these steps to set up database connections:

1. Access Superset at http://localhost:8088
   - Username: admin
   - Password: admin

2. Configure StarRocks connection:
   - Click on "Settings" (gear icon) in the top menu, then "Database Connections"
   - Click "+ DATABASE" to add a new database connection
   - Select "MySQL" as the database type
   - Enter the following connection details:
     - Display Name: StarRocks
     - Host: host.docker.internal
     - Port: 9030
     - Database Name: industrial_warehouse
     - Username: root
     - Password: (leave empty)
   - Click "FINISH" to save the connection

3. Configure MySQL connection:
   - Click "+ DATABASE" to add another database connection
   - Select "MySQL" as the database type
   - Enter the following connection details:
     - Display Name: MySQL
     - Host: host.docker.internal
     - Port: 3306
     - Database Name: industrial_data
     - Username: root
     - Password: rootpassword
   - Click "FINISH" to save the connection

4. Create datasets:
   - Go to "SQL Lab" → "SQL Editor" to run queries against your databases
### Data Warehousing Approaches

The platform implements two complementary approaches for data warehousing:

#### StarRocks Native Approach

This approach uses StarRocks' built-in functionality for data processing:

1. **External Catalog Integration**:
   - Creates a MySQL catalog in StarRocks to access MySQL data (SCADA, IoT, MES, etc.)
   - References external tables through the catalog without duplicating data

2. **Dimension Tables**:
   - Creates dimension tables in StarRocks for AlarmCodes, Machines, MachineStatus, and Operators
   - Populates these tables from the corresponding MySQL tables via the catalog

3. **Historical Data Processing**:
   - Joins historical data from MySQL tables through the catalog
   - Creates the `machine_metrics` table for historical analytics

4. **Streaming Data Processing**:
   - Creates stream staging tables for each data type (IOT, SCADA, MES)
   - Sets up Routine Loads to continuously ingest data from Kafka topics
   - Uses a materialized view (`mv_machine_metrics_stream`) to join streams in real-time
   - Implements a scheduled task (`insert_machine_metrics`) to periodically insert joined data into the machine_metrics fact table

5. **Data Marts**:
   - Creates materialized views for various analytical perspectives (daily, weekly, monthly)
   - Automatically refreshes these views to provide up-to-date insights

#### Apache Spark Approach

This approach uses Apache Spark for flexible, scalable data processing:

1. **Stream Data Processing**:
   - Reads data from StarRocks staging tables
   - Performs complex transformations and joins across data streams
   - Uses PySpark dataframes for efficient, distributed processing

2. **Data Enrichment**:
   - Matches IoT sensor data with the closest temporal MES and SCADA data points
   - Joins with dimension tables to resolve IDs and descriptions
   - Creates a comprehensive fact table with data from all sources

3. **Data Loading**:
   - Writes the processed data back to StarRocks' machine_metrics table
   - Scheduled to run periodically via cron (e.g., every minute)

4. **Implementation**:
   - Available as a Jupyter notebook (`notebooks/mes_streams_creation/SparkETL.ipynb`)
   - Also available as a standalone Python script (`scripts/SparkETL.py`) for use without Jupyter

#### Running the Spark ETL Script

For users who prefer to run the ETL process directly without using Jupyter, a standalone Python script is provided:

```bash
# Connect to the Spark master container
docker exec -it spark-master bash

# Run the ETL script
spark-submit /scripts/SparkETL.py
```

The `SparkETL.py` script performs the same functions as the Jupyter notebook:
- Connects to StarRocks database
- Reads data from staging tables
- Joins IoT data with the closest temporal MES and SCADA data points
- Resolves references to dimension tables
- Writes the results to the machine_metrics table

This script can be scheduled to run periodically using cron for automated ETL processing:

```bash
# Example cron entry to run the ETL process every minute
* * * * * docker exec spark-master spark-submit /scripts/SparkETL.py >> /var/log/spark-etl.log 2>&1
```

### Node-RED OPC UA to Kafka Integration

The platform includes a preconfigured Node-RED flow that connects to the OPC UA server and publishes data to Kafka topics.

1. **Flow Description**:
   - The flow reads data from two OPC UA nodes: `ns=2;i=1` (IOT sensors) and `ns=2;i=3` (SCADA data)
   - Transforms the data into structured JSON format
   - Publishes the formatted data to Kafka topics: `iot-data` and `scada-data`

2. **Configuring the OPC UA Connection**:
   - The default OPC UA endpoint is `opc.tcp://localhost:4840/freeopcua/server`
   - If the OPC UA server is running on a different host, update the endpoint configuration
   - This can be done by double-clicking the "READ IOT SENSOR OPCUA NODE" or "READ SCADA OPCUA NODE" blocks

3. **Starting the Data Flow**:
   - The flow includes schedulers that automatically trigger the OPC UA nodes every second
   - You can manually trigger the flow using the inject nodes ("SCHEDULER FOR IOT STREAMS" and "SCHEDULER FOR SCADA STREAMS")
   - The debug nodes display the data being processed in the Node-RED debug panel

### Streaming Data Flow
1. The OPC UA server generates simulated industrial sensor data
2. Node-RED can be configured to subscribe to OPC UA tags and publish to Kafka topics
3. Kafka streams the data to consumers (Telegraf, Spark, etc.)
4. Telegraf processes the Kafka messages and writes to InfluxDB
5. Grafana visualizes the time-series data from InfluxDB

### Batch Data Processing
1. Load historical data into MySQL using the provided scripts
2. Run Spark jobs to process and transform data
3. Store processed data in StarRocks for analytical queries
4. Use Superset to create dashboards and reports from StarRocks data

### Development and Analysis
1. Use Jupyter notebooks for exploratory data analysis and model development
2. Connect notebooks to Spark for distributed processing
3. Access data from MySQL, StarRocks, and InfluxDB from notebooks


# Run Forecasting models
## Caution:
Before running the following commands, please ensure kafka and zookeeper are running.

Ensure events are being emitted to kafka topics:
```
iot-data
mes-data
scada-data
```
And you are present in the extracted folder: `Team01_CODE_PredictiveAnalytics`

Or Run : `cd ..`


## To run all forecasting (classification, regression and clustering) models
```
pip install --no-cache-dir -r requirements.txt
or
pip3 install --no-cache-dir -r requirements.txt

python app.py
or
python3 app.py

in new terminal:
python models/performance_energy_model.py
or
python3 models/performance_energy_model.py
```

## Note: 
After running the above command, please wait until the following is observed in logs

### For app.py 
```
Starting FastAPI app on port 8000...
INFO:     Started server process [3834]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
Kafka consumer started on topics: iot-data, scada-data, mes-data
``` 
### For performance_energy_model.py
```
INFO:     Started server process [12321]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
Kafka consumer started...

```

This means that the script is now ready to consume data and server API requests.
Please ensure that like of the pattern are being emitted:
``
event::
``

## Request Objects
Request object structure:

Here {api-route} can be one of the following:

/forecast-status
/forecast-alarm
/forecast-power
/forecast-units-prod
/forecast-defective-units
/forecast-production-time

With port 8001:

/performance-cluster
/energy-cluster
/optimal-pairings
/energy-efficiency
/performance-analysis
/forecast-energy-consumption
/detect-energy-anomalies
/model-metrics

Request object structure:
```
curl --location 'http://localhost:8000/{api-route}' \
--header 'Content-Type: application/json' \
--header 'Cookie: sessionId=4dfe4065-5df3-4edd-887a-4733254dd85a' \
--data '{
    "machine_id": "{machine id}"
}'
```
## Example:
```
curl --location 'http://localhost:8000/forecast-defective-units' \
--header 'Content-Type: application/json' \
--header 'Cookie: sessionId=4dfe4065-5df3-4edd-887a-4733254dd85a' \
--data '{
    "machine_id": "Machine_3"
}'
```

### For Api route: /forecast-performance-trend
Request object:
```
curl --location 'http://localhost:8001/forecast-defective-units' \
--header 'Content-Type: application/json' \
--header 'Cookie: sessionId=4dfe4065-5df3-4edd-887a-4733254dd85a' \
--data '{
    "machine_id": "{machine id}"
    "operator_id": "{operator id}"
}'
```

### For Api route: /retrain-models
Request object:
```
curl --location 'http://localhost:8000/forecast-defective-units' \
--header 'Content-Type: application/json' \
--header 'Cookie: sessionId=4dfe4065-5df3-4edd-887a-4733254dd85a' \
--data '{}'
```

### Acceptable values in API
```
Acceptable values for machine_id: 
Machine_1, Machine_2, Machine_3, Machine_4, Machine_5,
Machine_6, Machine_7, Machine_8, Machine_9, Machine_10

Acceptable values for operator_id:
1000, 1001, 1002, 1003, 1004,
1005, 1006, 1007, 1008, 1009
```

# Grafana Dashboards Setup
## Setting Up Grafana with InfluxDB and Machine Learning APIs using Infinity Source Data Plugin

## Prerequisites
Ensure you have the following installed and running:
- **Grafana** (Running in Docker on port `3000`)
- **InfluxDB** (Running in Docker on port `8086`)
- **Preconfigured dashboards JSONs are present in the folder `grafana-dashboard`**

---

## Step 1: Connecting InfluxDB to Grafana
1. Open **Grafana** and navigate to **Connections**.
2. Click on **Add data source** and select **InfluxDB**.
3. Configure the connection settings:
   - **URL:** `docker.internal:8086`
   - **Organization:** `iot_organization`
   - **Token:** `iot_token`
   - **Username:** `iot_user`
   - **Password:** `iot_password`
4. Click **Save & Test** to verify the connection.

---

## Step 2: Adding the Infinity Source Data Plugin
1. Go to **Connections** in Grafana.
2. Click **Add data source** and select **Infinity Source Data Plugin**.
3. Click **ADD** to finalize the integration.

> Note: The Infinity data source plugin does not require a connection ID. Instead, source URLs are specified inside dashboard files.

---

## Step 3: Importing Preconfigured Dashboards
1. Navigate to **Grafana Dashboard**.
2. Click **Import Dashboard**.
3. Select the dashboard files from the preconfigured-dashboards zip folder.
4. Click **Import** to load the dashboards.
5. Select the appropriate data source for each dashboard (InfluxDB or Infinity Source Data Plugin) as per the following:

> Use "Infinity Data Source" for dashboards:
Clustering
Forecasting And Prediction

>Use "InfluxDB Data Source" for other dashboards:
Live Machine Stats
Factory Analytics

---


### Stopping the Platform
```bash
# Stop all services
Stop both Python API scripts.

docker-compose down
docker-compose -f docker-compose-kafka.yml down
docker-compose -f docker-compose-influx.yml down
docker-compose -f docker-compose-opcua.yml down
docker-compose -f docker-compose-superset.yml down
```

To completely remove all containers and volumes:
```bash
Stop both Python API scripts.

docker-compose down -v
docker-compose -f docker-compose-kafka.yml down -v
docker-compose -f docker-compose-influx.yml down -v
docker-compose -f docker-compose-opcua.yml down -v
docker-compose -f docker-compose-superset.yml down -v
``` 

### Team Members Contact Emails:
Aakash : e1352834@u.nus.edu

Ritu : e1352995@u.nus.edu

Sasmit : e1349885@u.nus.edu

Simran : e1353006@u.nus.edu

Yatharth : e1353002@u.nus.edu
