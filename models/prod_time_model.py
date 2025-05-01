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
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from kafka3 import KafkaConsumer
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel

MODEL_DIR           = 'stored-models/prod-time'
PROD_TIME_MODEL_PATH    = os.path.join(MODEL_DIR, 'prod_time_reg.pkl')
PROD_TIME_MODEL2_PATH    = os.path.join(MODEL_DIR, 'prod_time_reg2.pkl')
PROD_TIME_PIPELINE_PATH    = os.path.join(MODEL_DIR, 'prod_time_reg-pipeline.pkl')
SCALAR2_PATH         = os.path.join(MODEL_DIR, 'scaler2.pkl')
ENC_MACHINE_PATH    = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH     = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH      = os.path.join(MODEL_DIR, 'en_alarm.pkl')
# STATE_PATH          = os.path.join(MODEL_DIR, 'state.pkl')

# --- Paths to historical data ------------------------------------------------
HIST_SCADA = 'generated_data/historical-scada.csv'
HIST_IOT   = 'generated_data/historical-iot.csv'
HIST_MES   = 'generated_data/historical-mes.csv'

N_EPOCHS = 2000

# ----------------------------------------
# 1. TRAINING: load data & bootstrap regressors
# ----------------------------------------
print("Loading historical SCADA, IOT and MES data for production time regressor...")
scada = pd.read_csv(HIST_SCADA, parse_dates=['Timestamp'], keep_default_na=False)
iot   = pd.read_csv(HIST_IOT,   parse_dates=['Timestamp'], keep_default_na=False)
mes   = pd.read_csv(HIST_MES,   parse_dates=['Timestamp'], keep_default_na=False)

print("Merging dataframes on Timestamp & Machine_ID for production time regressor...")
data = (
    scada.set_index(['Timestamp','Machine_ID'])
         .join(iot.set_index(['Timestamp','Machine_ID']), how='outer')
         .join(mes.set_index(['Timestamp','Machine_ID']), how='outer')
         .reset_index()
)
data.ffill(inplace=True)

def load_or_fit_encoder(path, series):
    if os.path.exists(path):
        enc = joblib.load(path)
        encoded = enc.transform(series)
        print(f"Loaded encoder {path} for production time regressor")
    else:
        enc = LabelEncoder()
        encoded = enc.fit_transform(series)
        joblib.dump(enc, path)
        print(f"Saved new encoder {path} for production time regressor")
    return enc, encoded

print("Encoding categorical features for production time regressor...")
en_machine, data['Machine_ID_enc'] = load_or_fit_encoder(ENC_MACHINE_PATH, data['Machine_ID'])
en_status,  data['Status_enc']      = load_or_fit_encoder(ENC_STATUS_PATH,  data['Machine_Status'])
en_alarm,   data['Alarm_enc']       = load_or_fit_encoder(ENC_ALARM_PATH,   data['Alarm_Code'])

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
y = data['Production_Time_min'].values

print("Bootstrapping regressors for Prod time...")
if os.path.exists(PROD_TIME_MODEL_PATH):
    reg = joblib.load(PROD_TIME_MODEL_PATH)
    print("Loaded persisted prod. time regressor.")
else:
    reg = SGDRegressor(max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3)
    reg.partial_fit(X, y)
    joblib.dump(reg, PROD_TIME_MODEL_PATH)
    print("Initialized and bootstrapped new prod. time regressor.")

if os.path.exists(PROD_TIME_MODEL2_PATH) and os.path.exists(SCALAR2_PATH):
    scaler = joblib.load(SCALAR2_PATH)
    reg2 = joblib.load(PROD_TIME_MODEL2_PATH)
    print("Loaded persisted prod. time scaled regressor with corresponding scaler")
else:
    print("Initializing prod. time scaled regressor reg2...")
    scaler = StandardScaler().fit(X)
    reg2 = SGDRegressor(max_iter=1, tol=None, warm_start=True,
        learning_rate='constant', eta0=1e-4, alpha=1e-3)
    reg2.partial_fit(scaler.transform(X), y)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, PROD_TIME_MODEL2_PATH)
    print("Initialized and bootstrapped new prod. time scaled regressor.")

if os.path.exists(PROD_TIME_PIPELINE_PATH):
    reg3 = joblib.load(PROD_TIME_PIPELINE_PATH)
    print("Loaded persisted prod. time pipeline regressor.")
else:
    reg3 = make_pipeline(StandardScaler(),
        SGDRegressor(max_iter=1, tol=None, warm_start=True,
            learning_rate='invscaling', eta0=1e-4, alpha=1e-4) #decreased eta0 by 10
    )
    reg3.fit(X, y)
    joblib.dump(reg3, PROD_TIME_PIPELINE_PATH)
    print("Initialized and bootstrapped new prod. time pipeline regressor.")

def evaluate_model_performance(num_passes):
    print(f"Evaluating model performance on training data for production time regressor where number of passes={num_passes}...")
    pred1 = reg.predict(X)
    pred2 = reg2.predict(scaler.transform(X))
    pred3 = reg3.predict(X)
    for name, pred in [('reg', pred1), ('reg2', pred2), ('reg3', pred3)]:
        mse = mean_squared_error(y, pred)
        mae = mean_absolute_error(y, pred)
        r2  = r2_score(y, pred)
        print(f"Production time regressor {name} -> MSE: {mse:.2f}, MAE: {mae:.2f}, R2: {r2:.3f} when number of passes={num_passes}")

print("Evaluating model performance on training data for production time regressor after just 1 partial_fit had been run...")
evaluate_model_performance(1)

def improve_performance_of_models(passes):
    print(f"Starting doing additional {passes} passes on the models")
    # reg
    for _ in range(passes):
        reg.partial_fit(X, y)

    # reg2
    for _ in range(passes):
        reg2.partial_fit(scaler.transform(X), y)
    # reg3
    # reg3.named_steps['standardscaler'].fit(X)
    Xs3 = reg3.named_steps['standardscaler'].transform(X)
    for _ in range(passes):
        reg3.named_steps['sgdregressor'].partial_fit(Xs3, y)
    evaluate_model_performance(passes)
    print(f"After doing additional {passes} passes on the models")

improve_performance_of_models(N_EPOCHS)

def persist_all():
    joblib.dump(reg, PROD_TIME_MODEL_PATH)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, PROD_TIME_MODEL2_PATH)
    joblib.dump(reg3, PROD_TIME_PIPELINE_PATH)
    print("Persisted all models and state for production time regressor")









# def kafka_consumer_loop():
#     consumer = KafkaConsumer(
#         'iot-stream','scada-stream','mes-stream',
#         bootstrap_servers=['localhost:9092'], auto_offset_reset='earliest', group_id='online-prod-time',
#         value_deserializer=lambda m: json.loads(m.decode('utf-8'))
#     )
#     print("Kafka consumer for production time regressor started on topics...")
#     for msg in consumer:
#         rec = msg.value
#         mid = rec['Machine_ID']
#         topic = msg.topic
#         if mid == "Machine_1":
#             print(f"Received message on {topic} for {mid}: {rec} for production time regressor")
#
#         if mid not in state:
#             state[mid] = {}
#             print(f"Initialized state for Machine_ID {mid} for production time regressor")
#
#         state[mid].update(rec)
#
#         # need raw fields to derive features
#         raw = state[mid]
#         if all(k in raw for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
#                                   'Power_Consumption_kW','Machine_Status','Alarm_Code',
#                                   'Units_Produced','Defective_Units','Production_Time_min']):
#             # compute features
#             defect_rate = raw['Defective_Units']/raw['Units_Produced']
#             throughput  = raw['Units_Produced']/raw['Production_Time_min']
#             energy_eff  = (raw['Power_Consumption_kW']*(raw['Production_Time_min']/60))/raw['Units_Produced']
#             feats = np.array([
#                 en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
#                 raw['Power_Consumption_kW'], en_status.transform([raw['Machine_Status']])[0],
#                 en_alarm.transform([raw['Alarm_Code']])[0], defect_rate, throughput, energy_eff
#             ]).reshape(1,-1)
#
#             # predictions
#             pred = round(reg.predict(feats)[0])
#             pred2 = round(reg2.predict(scaler.transform(feats))[0])
#             pred3 = round(reg3.predict(feats)[0])
#
#             # print(f"event:: {topic} {mid} pred_units={pu:.0f}, pred_defect={pd_:.0f}, pred_time={pt:.0f}")
#
#             # y_true = raw['Production_Time_min']
#             y_true = raw['Production_Time_min']
#             if topic == 'mes-stream' and 'Production_Time_min' in rec:
#                 y_true = rec['Production_Time_min']
#                 print(f"event:: {topic} Updated model for {mid} with true production_time: {y_true} as received in mes event")
#
#             reg.partial_fit(feats, [y_true])
#             reg2.partial_fit(scaler.transform(feats), [y_true])
#             # for reg3, step into the pipeline
#             scaled_feats = reg3.named_steps['standardscaler'].transform(feats)
#             reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])
#
#             if mid == "Machine_1":
#                 print(f"event:: {topic} Model updated for {mid} with production_time={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
#         persist_all()
#
# threading.Thread(target=kafka_consumer_loop, daemon=True).start()

# ----------------------------------------
# 3. REST API for on-demand forecast
# ----------------------------------------
# app = FastAPI()
# class ForecastRequest(BaseModel):
#     machine_id: str
#
# @app.post('/forecast-production-time')
# def forecast_power(req: ForecastRequest):
#     mid = req.machine_id
#     if mid not in state or not all(
#        k in state[mid] for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
#                                   'Power_Consumption_kW','Machine_Status','Alarm_Code',
#                                   'Units_Produced','Defective_Units','Production_Time_min']):
#         print(f"Missing state for {mid} for forecast production time request request")
#         result = {'Machine_ID': mid, 'Predicted_Production_Time_min': None}
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
#         print(f"Forecast_production time produced generated for {req.machine_id} with predicted value: {pred2}")
#         result = {'Machine_ID': mid, 'Predicted_Production_Time_min': pred2, "current":state[mid]['Production_Time_min'],
#                   "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
#     return result
#
# if __name__=='__main__':
#     uvicorn.run(app, host='0.0.0.0', port=8000)
