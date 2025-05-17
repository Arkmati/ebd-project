import os
import pandas as pd
import joblib
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

MODEL_DIR           = 'stored-models/units-prod'
UNITS_PROD_MODEL_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg.pkl')
UNITS_PROD_MODEL2_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg2.pkl')
UNITS_PROD_PIPELINE_PATH    = os.path.join(MODEL_DIR, 'units_prod_reg-pipeline.pkl')
SCALAR2_PATH         = os.path.join(MODEL_DIR, 'scaler2.pkl')
ENC_MACHINE_PATH    = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH     = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH      = os.path.join(MODEL_DIR, 'en_alarm.pkl')

# --- Paths to historical data ------------------------------------------------
HIST_SCADA = 'generated_data/historical-scada.csv'
HIST_IOT   = 'generated_data/historical-iot.csv'
HIST_MES   = 'generated_data/historical-mes.csv'

N_EPOCHS = 2000

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
    reg3.fit(X, y)
    joblib.dump(reg3, UNITS_PROD_PIPELINE_PATH)
    print("Initialized and bootstrapped new units prod pipeline regressor.")


def evaluate_model_performance(num_passes):
    print(f"Evaluating model performance on training data for units production regressor where number of passes={num_passes}...")
    pred1 = reg.predict(X)
    pred2 = reg2.predict(scaler.transform(X))
    pred3 = reg3.predict(X)
    for name, pred in [('reg', pred1), ('reg2', pred2), ('reg3', pred3)]:
        mse = mean_squared_error(y, pred)
        mae = mean_absolute_error(y, pred)
        r2  = r2_score(y, pred)
        print(f"Units production regressor {name} -> MSE: {mse:.2f}, MAE: {mae:.2f}, R2: {r2:.3f} when number of passes={num_passes}")

print("Evaluating model performance on training data for units production regressor after just 1 partial_fit had been run...")
evaluate_model_performance(1)

def improve_performance_of_models(passes):
    print(f"Starting doing additional {passes} passes on the models")
    for _ in range(passes):
        reg.partial_fit(X, y)
    for _ in range(passes):
        reg2.partial_fit(scaler.transform(X), y)

    Xs3 = reg3.named_steps['standardscaler'].transform(X)
    for _ in range(passes):
        reg3.named_steps['sgdregressor'].partial_fit(Xs3, y)
    evaluate_model_performance(passes)
    print(f"After doing additional {passes} passes on the models")

improve_performance_of_models(2000)

def persist_all():
    joblib.dump(reg, UNITS_PROD_MODEL_PATH)
    joblib.dump(scaler, SCALAR2_PATH)
    joblib.dump(reg2, UNITS_PROD_MODEL2_PATH)
    joblib.dump(reg3, UNITS_PROD_PIPELINE_PATH)
    print("Persisted all models and state for units prod regressor")
