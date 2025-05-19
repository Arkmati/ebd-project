FROM python:3.9-slim-buster

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y gcc

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY sensor_data.csv .
COPY future-stream-scada.csv .

EXPOSE 4840

CMD ["python", "server.py"]