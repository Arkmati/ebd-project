import threading
import json
import os
from datetime import datetime
import pandas as pd
import numpy as np
import joblib
import pickle
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from kafka3 import KafkaConsumer
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel

MODEL_DIR           = 'stored-models/units-prod'
UNITS_PROD_MODEL_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg.pkl')
UNITS_PROD_MODEL2_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg2.pkl')
UNITS_PROD_PIPELINE_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg-pipeline.pkl')
SCALAR2_PATH         = os.path.join(MODEL_DIR, 'scaler2.pkl')
ENC_MACHINE_PATH    = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH     = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH      = os.path.join(MODEL_DIR, 'en_alarm.pkl')
STATE_PATH          = os.path.join(MODEL_DIR, 'state.pkl')

# --- Paths to historical data ------------------------------------------------
HIST_SCADA = 'generated_data/historical-scada.csv'
HIST_IOT   = 'generated_data/historical-iot.csv'
HIST_MES   = 'generated_data/historical-mes.csv'

# ----------------------------------------
# 1. TRAINING: load data & bootstrap regressors
# ----------------------------------------
print("Loading historical SCADA, IOT and MES data for units prod regressor...")
scada = pd.read_csv(HIST_SCADA, parse_dates=['Timestamp'], keep_default_na=False)
iot   = pd.read_csv(HIST_IOT,   parse_dates=['Timestamp'], keep_default_na=False)
mes   = pd.read_csv(HIST_MES,   parse_dates=['Timestamp'], keep_default_na=False)

print("Merging dataframes on Timestamp & Machine_ID for units prod regressor...")
data = (
    scada.set_index(['Timestamp','Machine_ID'])
         .join(iot.set_index(['Timestamp','Machine_ID']), how='outer')
         .join(mes.set_index(['Timestamp','Machine_ID']), how='outer')
         .reset_index()
)
data.ffill(inplace=True)

# Label encoder helper
# def fit_encoder(series):
#     enc = LabelEncoder()
#     return enc, enc.fit_transform(series)

def load_or_fit_encoder(path, series):
    if os.path.exists(path):
        enc = joblib.load(path)
        encoded = enc.transform(series)
        print(f"Loaded encoder {path} for units prod regressor")
    else:
        enc = LabelEncoder()
        encoded = enc.fit_transform(series)
        joblib.dump(enc, path)
        print(f"Saved new encoder {path} for units prod regressor")
    return enc, encoded

print("Encoding categorical features for units prod regressor...")
en_machine, data['Machine_ID_enc'] = load_or_fit_encoder(ENC_MACHINE_PATH, data['Machine_ID'])
en_status,  data['Status_enc']      = load_or_fit_encoder(ENC_STATUS_PATH,  data['Machine_Status'])
en_alarm,   data['Alarm_enc']       = load_or_fit_encoder(ENC_ALARM_PATH,   data['Alarm_Code'])

# print("Encoding categorical features...")
# en_machine, data['Machine_ID_enc'] = fit_encoder(data['Machine_ID'])
# en_status,  data['Status_enc']      = fit_encoder(data['Machine_Status'])
# en_alarm,   data['Alarm_enc']       = fit_encoder(data['Alarm_Code'])

# Derive engineered features
# defect rate: fraction defective
data['Defect_rate']      = data['Defective_Units'] / data['Units_Produced']
# throughput: units per minute
data['Throughput']       = data['Units_Produced'] / data['Production_Time_min']
# energy efficiency: energy (kW*hours) per unit => (kW * min/60) / units
data['Energy_efficiency'] = (data['Power_Consumption_kW'] * (data['Production_Time_min']/60)) / data['Units_Produced']

# Features for all models
feature_cols = [
    'Machine_ID_enc', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar',
    'Power_Consumption_kW', 'Status_enc', 'Alarm_enc',
    'Defect_rate', 'Throughput', 'Energy_efficiency'
]
X = data[feature_cols].values
y = data['Units_Produced'].values

print("Bootstrapping regressors for Units...")
if os.path.exists(UNITS_PROD_MODEL_PATH):
    reg = joblib.load(UNITS_PROD_MODEL_PATH)
    print("Loaded persisted units prod regressor.")
else:
    reg = SGDRegressor(max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3)
    reg.partial_fit(X, y)
    joblib.dump(reg, UNITS_PROD_MODEL_PATH)
    print("Initialized and bootstrapped new units prod regressor.")

if os.path.exists(UNITS_PROD_MODEL2_PATH) and os.path.exists(SCALAR2_PATH):
    scaler = joblib.load(SCALAR2_PATH)
    reg2 = joblib.load(UNITS_PROD_MODEL2_PATH)
    print("Loaded persisted units prod scaled regressor with corresponding scaler")
else:
    print("Initializing units prod scaled regressor reg2...")
    scaler = StandardScaler().fit(X)
    reg2 = SGDRegressor(max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3)
    reg2.partial_fit(scaler.transform(X), y)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, UNITS_PROD_MODEL2_PATH)
    print("Initialized and bootstrapped new units prod scaled regressor.")

if os.path.exists(UNITS_PROD_PIPELINE_PATH):
    reg3 = joblib.load(UNITS_PROD_PIPELINE_PATH)
    print("Loaded persisted units prod pipeline regressor.")
else:
    reg3 = make_pipeline(StandardScaler(),
        SGDRegressor(max_iter=1, tol=None, warm_start=True,
            learning_rate='invscaling', eta0=1e-3, alpha=1e-4)
    )
    # bootstrap pipeline reg3
    reg3.fit(X, y)
    joblib.dump(reg3, UNITS_PROD_PIPELINE_PATH)
    print("Initialized and bootstrapped new units prod pipeline regressor.")

# reg = SGDRegressor(max_iter=1, tol=None, warm_start=True,
#         learning_rate='constant', eta0=1e-4, alpha=1e-3)
# reg.partial_fit(X, y_units)
# print("Bootstrapped all regressors.")

# ----------------------------------------
# 2. STREAMING: Kafka consumer + online update
# ----------------------------------------
# state = {}

def load_state(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            st = pickle.load(f)
        print(f"Loaded persisted state ({len(st)} machines) for units prod regressor")
        return st
    print("Init empty state buffer for units prod regressor")
    return {}

state = load_state(STATE_PATH)

def persist_all():
    joblib.dump(reg, UNITS_PROD_MODEL_PATH)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, UNITS_PROD_MODEL2_PATH)
    joblib.dump(reg3, UNITS_PROD_PIPELINE_PATH)
    with open(STATE_PATH, 'wb') as f:
        pickle.dump(state, f)
    print("Persisted all models and state for units prod regressor")

def kafka_consumer_loop():
    consumer = KafkaConsumer(
        'iot-stream','scada-stream','mes-stream',
        bootstrap_servers=['localhost:9092'], auto_offset_reset='earliest', group_id='online-units',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    print("Kafka consumer for units prod regressor started on topics...")
    for msg in consumer:
        rec = msg.value
        mid = rec['Machine_ID']
        topic = msg.topic
        if mid == "Machine_1":
            print(f"Received message on {topic} for {mid}: {rec} for units prod regressor")

        if mid not in state:
            state[mid] = {}
            print(f"Initialized state for Machine_ID {mid} for units prod regressor")

        state[mid].update(rec)

        # need raw fields to derive features
        raw = state[mid]
        if all(k in raw for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
                                  'Power_Consumption_kW','Machine_Status','Alarm_Code',
                                  'Units_Produced','Defective_Units','Production_Time_min']):
            # compute features
            defect_rate = raw['Defective_Units']/raw['Units_Produced']
            throughput  = raw['Units_Produced']/raw['Production_Time_min']
            energy_eff  = (raw['Power_Consumption_kW']*(raw['Production_Time_min']/60))/raw['Units_Produced']
            feats = np.array([
                en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
                raw['Power_Consumption_kW'], en_status.transform([raw['Machine_Status']])[0],
                en_alarm.transform([raw['Alarm_Code']])[0], defect_rate, throughput, energy_eff
            ]).reshape(1,-1)

            # predictions
            pred = round(reg.predict(feats)[0])
            pred2 = round(reg2.predict(scaler.transform(feats))[0])
            pred3 = round(reg3.predict(feats)[0])

            # print(f"event:: {topic} {mid} pred_units={pu:.0f}, pred_defect={pd_:.0f}, pred_time={pt:.0f}")

            # y_true = raw['Units_Produced']
            y_true = state[mid]['Units_Produced']
            if topic == 'mes-stream' and 'Units_Produced' in raw:
                y_true = raw['Units_Produced']
                print(f"event:: {topic} Updated model for {mid} with true units_produced: {y_true} as received in mes event")

            reg.partial_fit(feats, [y_true])
            reg2.partial_fit(scaler.transform(feats), [y_true])
            # for reg3, step into the pipeline
            scaled_feats = reg3.named_steps['standardscaler'].transform(feats)
            reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])

            if mid == "Machine_1":
                print(f"event:: {topic} Model updated for {mid} with units_produced={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
        persist_all()

threading.Thread(target=kafka_consumer_loop, daemon=True).start()

# ----------------------------------------
# 3. REST API for on-demand forecast
# ----------------------------------------
# app = FastAPI()
# class ForecastRequest(BaseModel):
#     machine_id: str
#
# @app.post('/forecast-units-prod')
# def forecast_power(req: ForecastRequest):
#     mid = req.machine_id
#     if mid not in state or not all(
#        k in state[mid] for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
#                                   'Power_Consumption_kW','Machine_Status','Alarm_Code',
#                                   'Units_Produced','Defective_Units','Production_Time_min']):
#         print(f"Missing state for {mid} for forecast units productions request")
#         result = {'Machine_ID': mid, 'Predicted_Units_Produced': None}
#     else:
#         raw = state.get(mid)
#         dr = raw['Defective_Units'] / raw['Units_Produced']
#         th = raw['Units_Produced'] / raw['Production_Time_min']
#         ee = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
#         feats = np.array([
#             en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
#             raw['Power_Consumption_kW'], en_status.transform([raw['Machine_Status']])[0],
#             en_alarm.transform([raw['Alarm_Code']])[0], dr, th, ee
#         ]).reshape(1, -1)
#         pred = round(reg.predict(feats)[0])
#         pred2 = round(reg2.predict(scaler.transform(feats))[0])
#         pred3 = round(reg3.predict(feats)[0])
#         print(f"Forecast_units produced generated for {req.machine_id} with predicted value: {pred2}")
#         result = {'Machine_ID': mid, 'Predicted_Units_Produced': pred2, "current":state[mid]['Units_Produced'],
#                   "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
#     return result
#
# if __name__=='__main__':
#     uvicorn.run(app, host='0.0.0.0', port=8000)
