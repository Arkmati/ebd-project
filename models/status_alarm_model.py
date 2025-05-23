import os
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

MODEL_DIR = 'stored-models/status-alarm'
STATUS_MODEL_PATH = os.path.join(MODEL_DIR, 'status_clf.pkl')
ALARM_MODEL_PATH  = os.path.join(MODEL_DIR, 'alarm_clf.pkl')
ENC_MACHINE_PATH  = os.path.join(MODEL_DIR, 'en_machine.pkl')
ENC_STATUS_PATH   = os.path.join(MODEL_DIR, 'en_status.pkl')
ENC_ALARM_PATH    = os.path.join(MODEL_DIR, 'en_alarm.pkl')

N_EPOCHS = 10

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


def evaluate_alarm_model_performance(num_passes):
    print(f"Evaluating model performance on training data for alarm code classifier where number of passes={num_passes}...")
    alarm_pred_labels = alarm_clf.predict(X)
    alarm_pred_proba = alarm_clf.predict_proba(X)

    accuracy = accuracy_score(y_alarm, alarm_pred_labels)
    precision = precision_score(y_alarm, alarm_pred_labels, average='weighted', zero_division=0)
    recall = recall_score(y_alarm, alarm_pred_labels, average='weighted', zero_division=0)
    f1 = f1_score(y_alarm, alarm_pred_labels, average='weighted', zero_division=0)

    auc = roc_auc_score(y_alarm, alarm_pred_proba, multi_class='ovr')

    print(f"Alarm code classifier alarm_clf -> Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1-Score: {f1:.4f}, "
        f"AUC-ROC (OvR): {auc:.4f} when number of passes={num_passes}")

def evaluate_status_model_performance(num_passes):
    print(f"Evaluating model performance on training data for machine status classifier where number of passes={num_passes}...")
    status_pred_labels = status_clf.predict(X)
    status_pred_proba = status_clf.predict_proba(X)

    accuracy = accuracy_score(y_status, status_pred_labels)
    precision = precision_score(y_status, status_pred_labels, average='weighted', zero_division=0)
    recall = recall_score(y_status, status_pred_labels, average='weighted', zero_division=0)
    f1 = f1_score(y_status, status_pred_labels, average='weighted', zero_division=0)

    auc = roc_auc_score(y_status, status_pred_proba, multi_class='ovr')

    print(f"Machine status classifier status_clf -> Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1-Score: {f1:.4f}, "
        f"AUC-ROC (OvR): {auc:.4f} when number of passes={num_passes}")

evaluate_alarm_model_performance(1)
evaluate_status_model_performance(1)

def improve_performance_of_models(passes):
    print(f"Starting doing additional {passes} passes on the models")
    for _ in range(passes):
        alarm_clf.partial_fit(X, y_alarm)
        status_clf.partial_fit(X, y_status)

    evaluate_alarm_model_performance(passes)
    evaluate_status_model_performance(passes)
    print(f"After doing additional {passes} passes on the models")

improve_performance_of_models(N_EPOCHS)


def persist_all():
    joblib.dump(status_clf, STATUS_MODEL_PATH)
    joblib.dump(alarm_clf, ALARM_MODEL_PATH)
    print("Persisted classifiers and state for status and alarm forecaster.")

