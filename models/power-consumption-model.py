import threading
import json
import os
from datetime import datetime

import joblib
import pickle
import pandas as pd
import numpy as np
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from kafka3 import KafkaConsumer
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel

MODEL_DIR           = '../stored-models/power'
POWER_MODEL_PATH    = os.path.join(MODEL_DIR, 'power_reg.pkl')
POWER_MODEL2_PATH    = os.path.join(MODEL_DIR, 'power_reg2.pkl')
POWER_PIPELINE_PATH    = os.path.join(MODEL_DIR, 'power_reg-pipeline.pkl')
SCALAR2_PATH         = os.path.join(MODEL_DIR, 'scaler2.pkl')
ENC_MACHINE_PATH    = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH     = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH      = os.path.join(MODEL_DIR, 'en_alarm.pkl')
STATE_PATH          = os.path.join(MODEL_DIR, 'state.pkl')

# --- Paths ------------------------------------------------
HIST_SCADA = '../generated_data/historical-scada.csv'
HIST_IOT   = '../generated_data/historical-iot.csv'
HIST_MES   = '../generated_data/historical-mes.csv'

# ----------------------------------------
# 1. TRAINING: load historical data & init online regressor
# ----------------------------------------
print("Loading historical SCADA, IOT and MES data for power consumption regressor...")
scada = pd.read_csv(HIST_SCADA, parse_dates=['Timestamp'], keep_default_na=False)
iot   = pd.read_csv(HIST_IOT,   parse_dates=['Timestamp'], keep_default_na=False)
mes   = pd.read_csv(HIST_MES,   parse_dates=['Timestamp'], keep_default_na=False)

print("Merging dataframes on Timestamp & Machine_ID for power consumption regressor...")
data = (
    scada.set_index(['Timestamp','Machine_ID'])
         .join(iot.set_index(['Timestamp','Machine_ID']), how='outer')
         .join(mes.set_index(['Timestamp','Machine_ID']), how='outer')
         .reset_index()
)
data.ffill(inplace=True)

# Label encoders
# def fit_encoder(series):
#     enc = LabelEncoder()
#     return enc, enc.fit_transform(series)

def load_or_fit_encoder(path, series):
    if os.path.exists(path):
        enc = joblib.load(path)
        encoded = enc.transform(series)
        print(f"Loaded encoder {path}")
    else:
        enc = LabelEncoder()
        encoded = enc.fit_transform(series)
        joblib.dump(enc, path)
        print(f"Saved new encoder {path}")
    return enc, encoded

# print("Encoding categorical features...")
# en_machine, data['Machine_ID_enc'] = fit_encoder(data['Machine_ID'])
# en_status,  data['Status_enc']      = fit_encoder(data['Machine_Status'])
# en_alarm,   data['Alarm_enc']       = fit_encoder(data['Alarm_Code'])

# encode categories
print("Encoding categorical features for power consumption regressor...")
en_machine, data['Machine_ID_enc'] = load_or_fit_encoder(ENC_MACHINE_PATH, data['Machine_ID'])
en_status,  data['Status_enc']      = load_or_fit_encoder(ENC_STATUS_PATH,  data['Machine_Status'])
en_alarm,   data['Alarm_enc']       = load_or_fit_encoder(ENC_ALARM_PATH,   data['Alarm_Code'])

# Derive throughput and defect rate
data['Throughput']  = data['Units_Produced'] / data['Production_Time_min']
data['Defect_rate'] = data['Defective_Units'] / data['Units_Produced']

# Selected features & target
feature_cols = [
    'Machine_ID_enc', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar',
    'Status_enc', 'Alarm_enc', 'Throughput', 'Defect_rate'
]
X = data[feature_cols].values
y = data['Power_Consumption_kW'].values

print("Initializing or loading online SGDRegressor for power consumption regressor...")
if os.path.exists(POWER_MODEL_PATH):
    reg = joblib.load(POWER_MODEL_PATH)
    print("Loaded persisted power regressor.")
else:
    reg = SGDRegressor(
        max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3)
    reg.partial_fit(X, y)
    joblib.dump(reg, POWER_MODEL_PATH)
    print("Initialized and bootstrapped new power regressor.")

def build_scaled_regressor(X, y):
    scaler = StandardScaler().fit(X)
    reg2 = SGDRegressor(
        max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3
    )
    reg2.partial_fit(scaler.transform(X), y)
    return scaler, reg2


if os.path.exists(POWER_MODEL2_PATH) and os.path.exists(SCALAR2_PATH):
    scaler = joblib.load(SCALAR2_PATH)
    reg2 = joblib.load(POWER_MODEL2_PATH)
    print("Loaded persisted power scaled regressor with corresponding scaler")
else:
    print("Initializing power scaled regressor reg2...")
    scaler, reg2 = build_scaled_regressor(X, y)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, POWER_MODEL2_PATH)
    print("Initialized and bootstrapped new power scaled regressor.")


if os.path.exists(POWER_PIPELINE_PATH):
    reg3 = joblib.load(POWER_PIPELINE_PATH)
    print("Loaded persisted power pipeline regressor.")
else:
    reg3 = make_pipeline(
        StandardScaler(),
        SGDRegressor(
            max_iter=1, tol=None, warm_start=True,
            learning_rate='invscaling', eta0=1e-3, alpha=1e-4
        )
    )
    # bootstrap pipeline reg3
    reg3.fit(X, y)
    joblib.dump(reg3, POWER_PIPELINE_PATH)
    print("Initialized and bootstrapped new power pipeline regressor.")


# print("Initializing online SGDRegressor and bootstrapping on historical data...")
# reg = SGDRegressor(
#     max_iter=1, tol=None, warm_start=True,
#     learning_rate='constant', eta0=1e-4, alpha=1e-3)
# reg.partial_fit(X, y)
# print("Bootstrapped regressor.")
# print("Initializing scaled regressor reg2...")
# scaler, reg2 = build_scaled_regressor(X, y)
# reg3 = make_pipeline(
#     StandardScaler(),
#     SGDRegressor(
#         max_iter=1,
#         tol=None,
#         warm_start=True,
#         learning_rate='invscaling',
#         eta0=1e-3,
#         alpha=1e-4
#     )
# )
# # bootstrap pipeline reg3
# reg3.fit(X, y)
# print("Bootstrapped pipeline regressor reg3.")

def load_state(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            st = pickle.load(f)
        print(f"Loaded persisted state ({len(st)} machines) for power consumption regressor")
        return st
    print("Init empty state buffer for power consumption regressor")
    return {}

state = load_state(STATE_PATH)

def persist_all():
    joblib.dump(reg, POWER_MODEL_PATH)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, POWER_MODEL2_PATH)
    joblib.dump(reg3, POWER_PIPELINE_PATH)
    with open(STATE_PATH, 'wb') as f:
        pickle.dump(state, f)
    print("Persisted all models and state for power consumption regressor")

# ----------------------------------------
# 2. STREAMING: Kafka consumer + online update
# ----------------------------------------
# state = {}
def kafka_consumer_loop():
    consumer = KafkaConsumer(
        'iot-stream', 'scada-stream', 'mes-stream',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='online-power',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    print("Kafka consumer for power consumption regressor started on topics: iot-stream, scada-stream, mes-stream")
    for msg in consumer:
        rec = msg.value
        mid = rec['Machine_ID']
        topic = msg.topic
        if mid == "Machine_1":
            print(f"Received message on {topic} for {mid}: {rec} for power consumption regressor")
        # print(f"Received message on {topic} for {mid}: {rec}")
        if mid not in state:
            state[mid] = {}
            print(f"Initialized state for Machine_ID {mid} for power consumption regressor")

        state[mid].update(rec)

        # once full feature set is available
        required = [
            'Temperature_C','Vibration_mm_s','Pressure_bar', 'Machine_Status',
            'Alarm_Code', 'Units_Produced','Production_Time_min'
        ]
        if all(k in state[mid] for k in required):
            # build features
            feats = np.array([
                en_machine.transform([mid])[0],
                state[mid]['Temperature_C'],
                state[mid]['Vibration_mm_s'],
                state[mid]['Pressure_bar'],
                en_status.transform([state[mid]['Machine_Status']])[0],
                en_alarm.transform([state[mid]['Alarm_Code']])[0],
                state[mid]['Units_Produced']/state[mid]['Production_Time_min'],
                state[mid]['Defective_Units']/state[mid]['Units_Produced']
            ]).reshape(1, -1)
            # print(f"Performing inference for {mid} with features {feats.flatten()}")

            # predict next power
            pred = round(reg.predict(feats)[0], 2)
            pred2 = round(reg2.predict(scaler.transform(feats))[0], 2)
            pred3 = round(reg3.predict(feats)[0], 2)
            # print(f"event:: {topic} Predicted next power for {mid}: {pred:.2f} kW")

            y_true = state[mid]['Power_Consumption_kW']
            if topic == 'scada-stream' and 'Power_Consumption_kW' in rec:
                y_true = rec['Power_Consumption_kW']
                print(f"event:: {topic} Updated model for {mid} with true power {y_true} as received in scada event")
            reg.partial_fit(feats, [y_true])

            reg2.partial_fit(scaler.transform(feats), [y_true])
            # for reg3, step into the pipeline
            scaled_feats = reg3.named_steps['standardscaler'].transform(feats)
            reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])


            # print(f"event:: {topic} Updated model for {mid} with true power {y_true}")

            # update on actual SCADA events
            # if topic == 'scada-stream' and 'Power_Consumption_kW' in rec:
            #     y_true = rec['Power_Consumption_kW']
            #     reg.partial_fit(feats, [y_true])
            #     print(f"event:: {topic} Updated model for {mid} with true power {y_true}")

            if mid == "Machine_1":
                print(f"event:: {topic} Model updated for {mid} with power={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")

        persist_all()

threading.Thread(target=kafka_consumer_loop, daemon=True, name='KafkaConsumer').start()

# ----------------------------------------
# 3. REST API for on-demand forecast
# ----------------------------------------
app = FastAPI()

class ForecastRequest(BaseModel):
    machine_id: str

@app.post('/forecast-power')
def forecast_power(req: ForecastRequest):
    mid = req.machine_id
    if mid not in state or not all(
       k in state[mid] for k in [
           'Temperature_C','Vibration_mm_s','Pressure_bar',
           'Machine_Status','Alarm_Code',
           'Units_Produced','Production_Time_min'
       ]):
        print(f"Missing state for {mid} for forecast power request")
        result = {'Machine_ID': mid, 'Predicted_Power_kW': None}
        # raise HTTPException(status_code=404, detail=f"Insufficient state for {mid}")
    else:
        feats = np.array([
            en_machine.transform([mid])[0],
            state[mid]['Temperature_C'],
            state[mid]['Vibration_mm_s'],
            state[mid]['Pressure_bar'],
            en_status.transform([state[mid]['Machine_Status']])[0],
            en_alarm.transform([state[mid]['Alarm_Code']])[0],
            state[mid]['Units_Produced'] / state[mid]['Production_Time_min'],
            state[mid]['Defective_Units'] / state[mid]['Units_Produced']
        ]).reshape(1, -1)
        pred = round(reg.predict(feats)[0], 2)
        pred2 = round(reg2.predict(scaler.transform(feats))[0], 2)
        pred3 = round(reg3.predict(feats)[0], 2)
        print(f"Forecast_power generated for {req.machine_id} with power value: {pred:.2f}")
        result = {'Machine_ID': mid, 'Predicted_Power_kW': float(pred), "current":state[mid]['Power_Consumption_kW'],
                  "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
    return result

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)