## Commands for docker files to run
docker-compose -f docker-compose.yml -f docker-compose-kafka.yml -f docker-compose-superset.yml up -d

## To delete without deleting volumes
docker-compose -f docker-compose.yml -f docker-compose-kafka.yml -f docker-compose-superset.yml down

## Access Superset at http://localhost:8088/superset
## Access Starocks at http://localhost:8030/

## Caution:
Before running the following commands, please ensure kafka and zookeeper are running.

Ensure events are being emitted to kafka topics:
```
iot-data
mes-data
scada-data
```


## To run all forecasting (classification and regression) models
```
pip install --no-cache-dir -r requirements.txt

python3 app.py

in new terminal:
python performance_energy_model.py
```

## Note: 
After running the above command, please wait until the following is observed in logs
```
Starting FastAPI app on port 8000...
INFO:     Started server process [3834]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
Kafka consumer started on topics: iot-stream, scada-stream, mes-stream
``` 
This means that the script is now ready to consume data and server API requests.
Please ensure that like of the pattern are being emitted:
``
event::
``

## Request Objects
Request object structure:

Here {api-route} can be one of the following:
forecast-status
forecast-alarm
forecast-power
forecast-units-prod
forecast-defective-units
forecast-production-time
performance-cluster
energy-cluster
optimal-pairings
energy-efficiency
performance-analysis
forecast-energy-consumption
detect-energy-anomalies
model-metrics
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
curl --location 'http://localhost:8000/forecast-defective-units' \
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