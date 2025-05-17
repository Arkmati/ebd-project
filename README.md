## Commands for docker files to run
docker-compose -f docker-compose.yml -f docker-compose-kafka.yml -f docker-compose-superset.yml up -d

## To delete without deleting volumes
docker-compose -f docker-compose.yml -f docker-compose-kafka.yml -f docker-compose-superset.yml down

## Access Superset at http://localhost:8088/superset
## Access Starocks at http://localhost:8030/

## Caution:
Before running the following commands, please ensure kafka and zookeeper are running.


## To run all forecasting (classification and regression) models
```
pip install --no-cache-dir -r requirements.txt

python3 app.py
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
This means that the script is now ready to consume data and 