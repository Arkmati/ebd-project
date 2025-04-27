
# Spark, StarRocks, and MySQL Setup with Docker Compose

This document outlines the complete setup of a system that integrates **Apache Spark**, **StarRocks**, and **MySQL** using Docker Compose.

---

## 🧱 1. Docker Compose Setup

### 📄 `docker-compose.yml`
```yaml
version: '3.8'

services:
  starrocks:
    image: starrocks/allin1-ubuntu:3.4.1
    container_name: starrocks-allin1
    restart: unless-stopped
    ports:
      - "8030:8030"
      - "9020:9020"
      - "9030:9030"
      - "8040:8040"
      - "9050:9050"
    volumes:
      - ./starrocks/fe/meta:/data/deploy/starrocks/fe/meta
      - ./starrocks/be/storage:/data/deploy/starrocks/be/storage
    environment:
      - FE_CONF=enable_external_catalog=true;persistent_index.enable=true
    networks:
      - kafka-nifi-net

  spark-master:
    image: bitnami/spark:3.3.2
    container_name: spark-master
    environment:
      - SPARK_MODE=master
      - SPARK_RPC_AUTHENTICATION_ENABLED=no
      - SPARK_RPC_ENCRYPTION_ENABLED=no
      - SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED=no
      - SPARK_SSL_ENABLED=no
      - SPARK_EXTRA_CLASSPATH=/extra-jars
    ports:
      - "8090:8080"
      - "7077:7077"
    volumes:
      - ./data:/data
      - ./scripts:/scripts
      - ./jars:/extra-jars
    networks:
      - kafka-nifi-net

  spark-worker:
    image: bitnami/spark:3.3.2
    container_name: spark-worker
    depends_on:
      - spark-master
    environment:
      - SPARK_MODE=worker
      - SPARK_MASTER_URL=spark://spark-master:7077
      - SPARK_WORKER_MEMORY=2G
      - SPARK_WORKER_CORES=2
      - SPARK_RPC_AUTHENTICATION_ENABLED=no
      - SPARK_RPC_ENCRYPTION_ENABLED=no
      - SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED=no
      - SPARK_SSL_ENABLED=no
      - SPARK_EXTRA_CLASSPATH=/extra-jars
    volumes:
      - ./data:/data
      - ./scripts:/scripts
      - ./jars:/extra-jars
    networks:
      - kafka-nifi-net

  mysql:
    image: mysql:8.0
    container_name: mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: industrial_data
      MYSQL_USER: user
      MYSQL_PASSWORD: userpassword
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - kafka-nifi-net

volumes:
  starrocks_data:
  mysql_data:

networks:
  kafka-nifi-net:
    external: true
    name: industrial-data-pipeline_kafka-nifi-net
```

---

## 📦 2. JARs Directory

Place the required JARs inside the `./jars` folder:
- `mysql-connector-j-8.0.33.jar`
- `starrocks-spark3_2.12-1.0.0.jar`

---

## 🚀 3. Running Spark Job

### Manual Run Command
```bash
docker exec -it spark-master spark-submit \
  --master spark://spark-master:7077 \
  --jars /extra-jars/mysql-connector-j-8.0.33.jar,/extra-jars/starrocks-spark3_2.12-1.0.0.jar \
  /scripts/read_from_starrocks.py
```

---

## ✅ 4. Sample Output

The top 10 rows will be printed from your `read_from_starrocks.py` job if setup is successful.

---

## 💡 Tips

- Use `--jars` explicitly even if `SPARK_EXTRA_CLASSPATH` is configured.
- Confirm JARs exist via `docker exec -it spark-master ls /extra-jars`.
- To prevent MySQL data loss, avoid `docker-compose down -v`. Use `docker-compose stop` or `restart` instead.
- we use industrial-data-pipeline/starrocks/ for starrocks data persistence

## Create a topic

docker exec -it kafka kafka-topics --create \
--topic mes-data \
--bootstrap-server kafka:9092 \
--partitions 1 \
--replication-factor 1

## writing to kafka topic 

docker exec -it kafka kafka-console-producer \
--broker-list kafka:9092 \
--topic mes-data

# reading from kafka topic

docker exec -it kafka kafka-console-consumer \
--bootstrap-server kafka:9092 \
--topic mes-data \
--from-beginning

kafka-console-consumer \
--bootstrap-server kafka:9092 \
--topic iot-data \
--from-beginning \
--max-messages 1

kafka-console-consumer \
--bootstrap-server kafka:9092 \
--topic iot-data \
--from-beginning \
--max-messages 1

kafka-console-consumer \
--bootstrap-server kafka:9092 \
--topic scada-data \
--from-beginning \
--max-messages 1


kafka-console-consumer --bootstrap-server kafka:9092 \
--topic iot-data \
--offset latest \
--max-messages 1

kafka-console-consumer --bootstrap-server kafka:9092 \
--topic scada-data \
--offset latest \
--max-messages 1
--partition 1

kafka-topics --list --bootstrap-server kafka:9092
kafka-topics --create --topic scada-data --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic iot-data --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic mes-data --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
kafka-console-consumer --bootstrap-server kafka:9092 --topic scada-data --from-beginning --max-messages 1

kafka-console-consumer --bootstrap-server kafka:9092 --topic mes-data --from-beginning --timeout-ms 15000 --property print.value=true > mes-data-messages.json