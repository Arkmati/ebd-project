## Commands for docker files to run
docker-compose -f docker-compose.yml -f docker-compose-kafka-nifi.yml -f docker-compose-superset.yml up -d

## To delete without deleting volumes
docker-compose -f docker-compose.yml -f docker-compose-kafka-nifi.yml -f docker-compose-superset.yml down

## Access Superset at http://localhost:8088/superset
## Access Starocks at http://localhost:8030/
