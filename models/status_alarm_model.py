import threading
import json
from datetime import datetime
import os
import joblib
import pickle
import pandas as pd
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from kafka3 import KafkaConsumer
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel


MODEL_DIR = 'stored-models/status-alarm'
STATUS_MODEL_PATH = os.path.join(MODEL_DIR, 'status_clf.pkl')
ALARM_MODEL_PATH  = os.path.join(MODEL_DIR, 'alarm_clf.pkl')
ENC_MACHINE_PATH  = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH   = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH    = os.path.join(MODEL_DIR, 'en_alarm.pkl')
STATE_PATH        = os.path.join(MODEL_DIR, 'state.pkl')

# ----------------------------------------
# 1. TRAINING: load historical data and initialize online classifiers
# ----------------------------------------
print("Loading historical SCADA and IoT data for status and alarm classifiers...")
scada = pd.read_csv(
    'generated_data/historical-scada.csv', parse_dates=['Timestamp'], keep_default_na=False, na_values=[]
)
iot = pd.read_csv(
    'generated_data/historical-iot.csv', parse_dates=['Timestamp'], keep_default_na=False, na_values=[]
)
print("Merging SCADA and IoT dataframes for status and alarm classifiers...")
data = (
    scada.set_index(['Timestamp', 'Machine_ID'])
         .join(iot.set_index(['Timestamp', 'Machine_ID']), how='outer')
         .reset_index()
)
data.ffill(inplace=True)

# print("Encoding labels and preparing features...")
# en_machine = LabelEncoder()
# data['Machine_ID_enc'] = en_machine.fit_transform(data['Machine_ID'])
# en_status = LabelEncoder()
# data['Status_enc'] = en_status.fit_transform(data['Machine_Status'])
# en_alarm = LabelEncoder()
# data['Alarm_enc'] = en_alarm.fit_transform(data['Alarm_Code'])

# feature_cols = ['Machine_ID_enc','Power_Consumption_kW','Temperature_C','Vibration_mm_s','Pressure_bar']
# X = data[feature_cols].values
# y_status = data['Status_enc'].values
# y_alarm = data['Alarm_enc'].values

# print("Initializing online SGD classifiers and bootstrapping on historical data...")
# status_clf = SGDClassifier(loss='log_loss', max_iter=1, tol=None, warm_start=True)
# alarm_clf  = SGDClassifier(loss='log_loss', max_iter=1, tol=None, warm_start=True)
# status_clf.partial_fit(X, y_status, classes=np.unique(y_status))
# alarm_clf.partial_fit(X, y_alarm, classes=np.unique(y_alarm))
# print("Initial partial_fit complete.")



print("Encoding labels and preparing features or loading persisted encoders for status and alarm classifiers...")
# Machine encoder
if os.path.exists(ENC_MACHINE_PATH):
    en_machine = joblib.load(ENC_MACHINE_PATH)
    data['Machine_ID_enc'] = en_machine.transform(data['Machine_ID'])
    print(f"Loaded persisted encoder for Machine_ID with {len(en_machine.classes_)} classes for status and alarm classifiers.")
else:
    en_machine = LabelEncoder()
    data['Machine_ID_enc'] = en_machine.fit_transform(data['Machine_ID'])
    joblib.dump(en_machine, ENC_MACHINE_PATH)
    print(f"Saved new encoder for Machine_ID with {len(en_machine.classes_)} classes for status and alarm classifiers.")
# Status encoder
if os.path.exists(ENC_STATUS_PATH):
    en_status = joblib.load(ENC_STATUS_PATH)
    data['Status_enc'] = en_status.transform(data['Machine_Status'])
    print(f"Loaded persisted encoder for Machine_Status with {len(en_status.classes_)} classes for status and alarm classifiers.")
else:
    en_status = LabelEncoder()
    data['Status_enc'] = en_status.fit_transform(data['Machine_Status'])
    joblib.dump(en_status, ENC_STATUS_PATH)
    print(f"Saved new encoder for Machine_Status with {len(en_status.classes_)} classes for status and alarm classifiers.")
# Alarm encoder
if os.path.exists(ENC_ALARM_PATH):
    en_alarm = joblib.load(ENC_ALARM_PATH)
    data['Alarm_enc'] = en_alarm.transform(data['Alarm_Code'])
    print(f"Loaded persisted encoder for Alarm_Code with {len(en_alarm.classes_)} classes for status and alarm classifiers.")
else:
    en_alarm = LabelEncoder()
    data['Alarm_enc'] = en_alarm.fit_transform(data['Alarm_Code'])
    joblib.dump(en_alarm, ENC_ALARM_PATH)
    print(f"Saved new encoder for Alarm_Code with {len(en_alarm.classes_)} classes for status and alarm classifiers.")

feature_cols = ['Machine_ID_enc','Power_Consumption_kW','Temperature_C','Vibration_mm_s','Pressure_bar']
X = data[feature_cols].values
y_status = data['Status_enc'].values
y_alarm  = data['Alarm_enc'].values

print("Initializing or loading online SGD classifiers for status and alarm...")
# Status classifier
if os.path.exists(STATUS_MODEL_PATH):
    print("Found and hence loading persisted status classifier...")
    status_clf = joblib.load(STATUS_MODEL_PATH)
else:
    print("Did not find persisted status classifier, initializing new one...")
    status_clf = SGDClassifier(loss='log_loss', max_iter=1, tol=None, warm_start=True)
    status_clf.partial_fit(X, y_status, classes=np.unique(y_status))
    joblib.dump(status_clf, STATUS_MODEL_PATH)

# Alarm classifier
if os.path.exists(ALARM_MODEL_PATH):
    print("Found and hence loading persisted alarm classifier...")
    alarm_clf = joblib.load(ALARM_MODEL_PATH)
else:
    print("Did not find persisted alarm classifier, initializing new one...")
    alarm_clf = SGDClassifier(loss='log_loss', max_iter=1, tol=None, warm_start=True)
    alarm_clf.partial_fit(X, y_alarm, classes=np.unique(y_alarm))
    joblib.dump(alarm_clf, ALARM_MODEL_PATH)
print("Status and Alarm Classifier initialization complete.")

# Load or initialize state
if os.path.exists(STATE_PATH):
    with open(STATE_PATH, 'rb') as f:
        state = pickle.load(f)
    print(f"Loaded persisted state for {len(state)} machines for status and alarm forecaster.")
else:
    state = {}
    print("Initialized empty state for status and alarm forecaster.")


def persist_all():
    joblib.dump(status_clf, STATUS_MODEL_PATH)
    joblib.dump(alarm_clf, ALARM_MODEL_PATH)
    with open(STATE_PATH, 'wb') as f:
        pickle.dump(state, f)
    print("Persisted classifiers and state for status and alarm forecaster.")

# ----------------------------------------
# 2. STREAMING CONSUMER: inference + online update
# ----------------------------------------
# state = {}  # holds latest features per machine
def kafka_consumer_loop():
    consumer = KafkaConsumer(
        'iot-stream', 'scada-stream',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='online-status-alarm',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    print("Kafka consumer started for status and alarm forecaster, listening to topics: iot-stream, scada-stream")
    for message in consumer:
        record = message.value
        mid = record['Machine_ID']
        topic = message.topic
        # print(f"Received message on {topic} for {mid}: {record}")
        if mid not in state:
            state[mid] = {}
            print(f"Initialized state for Machine_ID {mid} status and alarm forecaster")
        state[mid].update(record)
        # if topic == 'scada-stream':
        required = ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']
        if all(k in state[mid] for k in required):
            feats = np.array([
                en_machine.transform([mid])[0],
                state[mid]['Power_Consumption_kW'],
                state[mid]['Temperature_C'],
                state[mid]['Vibration_mm_s'],
                state[mid]['Pressure_bar']
            ]).reshape(1, -1)
            # print(f"Performing inference for {mid} with features {feats.flatten()}")
            ps = status_clf.predict_proba(feats)[0]
            pa = alarm_clf.predict_proba(feats)[0]
            pred_status = en_status.inverse_transform([np.argmax(ps)])[0]
            pred_alarm = en_alarm.inverse_transform([np.argmax(pa)])[0]
            # print(f"Predicted for {mid}: Status={pred_status}, Alarm={pred_alarm}")

            status_y = state[mid]['Machine_Status']
            alarm_y = state[mid]['Alarm_Code']
            # print(f"Fetched statues {status_y} and alarm {alarm_y}")
            if "Machine_Status" in record and "Alarm_Code" in record:
                # Update the model with the true labels
                status_y = record['Machine_Status']
                alarm_y = record['Alarm_Code']
                # print(f"latest values taken from kafka message as status {status_y} and alarm {alarm_y}")

            y_s = en_status.transform([status_y])[0]
            y_a = en_alarm.transform([alarm_y])[0]
            status_clf.partial_fit(feats, [y_s])
            alarm_clf.partial_fit(feats, [y_a])
            # print(f"Model updated for {mid} with Status={status_y} and Alarm={alarm_y}")
            if mid == "Machine_1":
                print(f"event:: {topic} Model updated for {mid} with Status={status_y} and Alarm={alarm_y}, with predicted values: Status={pred_status}, Alarm={pred_alarm}")

        persist_all()
        # if mid=="Machine_1":
        #     print(f"current state: {state[mid]}")


threading.Thread(target=kafka_consumer_loop, daemon=True, name='KafkaConsumer').start()

# ----------------------------------------
# 3. REST API for on-demand forecasting
# ----------------------------------------
# app = FastAPI()
#
# class ForecastRequest(BaseModel):
#     machine_id: str
#
# @app.post('/forecast-status')
# def forecast_status(req: ForecastRequest):
#     print(f"forecast_status request received: {req}")
#     mid = req.machine_id
#     if mid not in state or not all(
#             k in state[mid] for k in ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']):
#         print(f"Missing state for {mid} for forecast status request")
#         results = {'Machine_ID': mid, 'Machine_Status': None, 'Alarm_Code': None}
#     else:
#         feats = np.array([
#             en_machine.transform([mid])[0],
#             state[mid]['Power_Consumption_kW'],
#             state[mid]['Temperature_C'],
#             state[mid]['Vibration_mm_s'],
#             state[mid]['Pressure_bar']
#         ]).reshape(1, -1)
#         ps = status_clf.predict_proba(feats)[0]
#         status = en_status.inverse_transform([np.argmax(ps)])[0]
#         # results.append({'Machine_ID': mid, 'Machine_Status': status, 'Alarm_Code': alarm})
#         results = {'Machine_ID': mid, 'Machine_Status': status, 'current': state[mid]['Machine_Status']}
#         # for ts in times:
#         print(f"Forecast_status generated for {req.machine_id} with status {status}")
#     return results
#
# @app.post('/forecast-alarm')
# def forecast_alarm(req: ForecastRequest):
#     print(f"forecast_alarm request received: {req}")
#     mid = req.machine_id
#     if mid not in state or not all(
#             k in state[mid] for k in ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']):
#         print(f"Missing state for {mid} for forecast alarm request")
#         results = {'Machine_ID': mid, 'Machine_Status': None, 'Alarm_Code': None}
#     else:
#         feats = np.array([
#             en_machine.transform([mid])[0],
#             state[mid]['Power_Consumption_kW'],
#             state[mid]['Temperature_C'],
#             state[mid]['Vibration_mm_s'],
#             state[mid]['Pressure_bar']
#         ]).reshape(1, -1)
#         pa = alarm_clf.predict_proba(feats)[0]
#         alarm = en_alarm.inverse_transform([np.argmax(pa)])[0]
#         # results.append({'Machine_ID': mid, 'Machine_Status': status, 'Alarm_Code': alarm})
#         results = {'Machine_ID': mid, 'Alarm_Code': alarm, "current": state[mid]['Alarm_Code']}
#         # for ts in times:
#         print(f"Forecast_alarm generated for {req.machine_id} with alarm {alarm}")
#     return results
#
# if __name__ == '__main__':
#     print("Starting FastAPI app on port 8000...")
#     uvicorn.run(app, host='0.0.0.0', port=8000)
