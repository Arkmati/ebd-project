import json
import os
import pickle
import numpy as np
from kafka3 import KafkaConsumer

from models.status_alarm_model import en_machine as status_alarm_en_machine
from models.status_alarm_model import en_status as status_alarm_en_status
from models.status_alarm_model import en_alarm as status_alarm_en_alarm
from models.status_alarm_model import status_clf, alarm_clf
from models.status_alarm_model import persist_all as status_alarm_persist_all

from models.power_consumption_model import en_machine as power_en_machine
from models.power_consumption_model import en_status as power_en_status
from models.power_consumption_model import en_alarm as power_en_alarm
from models.power_consumption_model import reg as power_reg
from models.power_consumption_model import reg2 as power_reg2
from models.power_consumption_model import reg3 as power_reg3
from models.power_consumption_model import scaler as power_scaler
from models.power_consumption_model import persist_all as power_consumption_persist_all

from models.units_prod_model import en_machine as units_prod_en_machine
from models.units_prod_model import en_status as units_prod_en_status
from models.units_prod_model import en_alarm as units_prod_en_alarm
from models.units_prod_model import reg as units_prod_reg
from models.units_prod_model import reg2 as units_prod_reg2
from models.units_prod_model import reg3 as units_prod_reg3
from models.units_prod_model import scaler as units_prod_scaler
from models.units_prod_model import persist_all as units_prod_persist_all

from models.defective_units_model import en_machine as def_units_en_machine
from models.defective_units_model import en_status as def_units_en_status
from models.defective_units_model import en_alarm as def_units_en_alarm
from models.defective_units_model import reg as def_units_reg
from models.defective_units_model import reg2 as def_units_reg2
from models.defective_units_model import reg3 as def_units_reg3
from models.defective_units_model import scaler as def_units_scaler
from models.defective_units_model import persist_all as def_units_persist_all

from models.prod_time_model import en_machine as prod_time_en_machine
from models.prod_time_model import en_status as prod_time_en_status
from models.prod_time_model import en_alarm as prod_time_en_alarm
from models.prod_time_model import reg as prod_time_reg
from models.prod_time_model import reg2 as prod_time_reg2
from models.prod_time_model import reg3 as prod_time_reg3
from models.prod_time_model import scaler as prod_time_scaler
from models.prod_time_model import persist_all as prod_time_persist_all

MODEL_DIR = 'stored-models'
STATE_PATH = os.path.join(MODEL_DIR, 'state.pkl')

def load_state(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            st = pickle.load(f)
        print(f"Loaded persisted state ({len(st)} machines) for power consumption regressor")
        return st
    print("Init empty state buffer for power consumption regressor")
    return {}

state = load_state(STATE_PATH)

def kafka_consumer_loop():
    consumer = KafkaConsumer(
        'iot-data', 'scada-data', 'mes-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='online-processor',
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

        if mid == "Machine_1":
            print(f"event:: {topic} state for {mid} before updates as {state[mid]}")

        state[mid].update(rec)

        if mid == "Machine_1":
            print(f"event:: {topic} state for {mid} post updates as {state[mid]}")

        process_status_alarm_style(rec, mid, topic)
        process_power_consumption_style(rec, mid, topic)
        process_units_prod_style(rec, mid, topic)
        process_defective_units_style(rec, mid, topic)
        process_production_time_style(rec, mid, topic)

        with open(STATE_PATH, 'wb') as f:
            pickle.dump(state, f)
        ##

def process_status_alarm_style(record, mid, topic):
    print(f"{topic} :: {mid} Processing for status and alarm model part")
    if topic=='mes-stream':
        print(f"As topic is {topic}, so no need to process here, skipping it.")
        return

    required = ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']
    if all(k in state[mid] for k in required):
        feats = np.array([
            status_alarm_en_machine.transform([mid])[0],
            state[mid]['Power_Consumption_kW'],
            state[mid]['Temperature_C'],
            state[mid]['Vibration_mm_s'],
            state[mid]['Pressure_bar']
        ]).reshape(1, -1)
        # print(f"Performing inference for {mid} with features {feats.flatten()}")
        ps = status_clf.predict_proba(feats)[0]
        pa = alarm_clf.predict_proba(feats)[0]
        pred_status = status_alarm_en_status.inverse_transform([np.argmax(ps)])[0]
        pred_alarm = status_alarm_en_alarm.inverse_transform([np.argmax(pa)])[0]
        # print(f"Predicted for {mid}: Status={pred_status}, Alarm={pred_alarm}")

        status_y = state[mid]['Machine_Status']
        alarm_y = state[mid]['Alarm_Code']
        # print(f"Fetched statues {status_y} and alarm {alarm_y}")
        if "Machine_Status" in record and "Alarm_Code" in record:
            # Update the model with the true labels
            status_y = record['Machine_Status']
            alarm_y = record['Alarm_Code']
            # print(f"latest values taken from kafka message as status {status_y} and alarm {alarm_y}")

        y_s = status_alarm_en_status.transform([status_y])[0]
        y_a = status_alarm_en_alarm.transform([alarm_y])[0]
        status_clf.partial_fit(feats, [y_s])
        alarm_clf.partial_fit(feats, [y_a])
        # print(f"Model updated for {mid} with Status={status_y} and Alarm={alarm_y}")
        if mid == "Machine_1":
            print(
                f"event:: {topic} Model updated for {mid} with Status={status_y} and Alarm={alarm_y}, with predicted values: Status={pred_status}, Alarm={pred_alarm}")

    status_alarm_persist_all()

def process_power_consumption_style(rec, mid, topic):
    print(f"{topic} :: {mid} Processing for power_consumption model part")
    # once full feature set is available
    required = [
        'Temperature_C', 'Vibration_mm_s', 'Pressure_bar', 'Machine_Status',
        'Alarm_Code', 'Units_Produced', 'Production_Time_min'
    ]
    if all(k in state[mid] for k in required):
        # build features
        feats = np.array([
            power_en_machine.transform([mid])[0],
            state[mid]['Temperature_C'],
            state[mid]['Vibration_mm_s'],
            state[mid]['Pressure_bar'],
            power_en_status.transform([state[mid]['Machine_Status']])[0],
            power_en_alarm.transform([state[mid]['Alarm_Code']])[0],
            state[mid]['Units_Produced'] / state[mid]['Production_Time_min'],
            state[mid]['Defective_Units'] / state[mid]['Units_Produced']
        ]).reshape(1, -1)
        # print(f"Performing inference for {mid} with features {feats.flatten()}")

        # predict next power
        pred = round(power_reg.predict(feats)[0], 2)
        pred2 = round(power_reg2.predict(power_scaler.transform(feats))[0], 2)
        pred3 = round(power_reg3.predict(feats)[0], 2)
        # print(f"event:: {topic} Predicted next power for {mid}: {pred:.2f} kW")

        y_true = state[mid]['Power_Consumption_kW']
        if topic == 'scada-stream' and 'Power_Consumption_kW' in rec:
            y_true = rec['Power_Consumption_kW']
            print(f"event:: {topic} Updated model for {mid} with true power {y_true} as received in scada event")
        power_reg.partial_fit(feats, [y_true])

        power_reg2.partial_fit(power_scaler.transform(feats), [y_true])
        # for reg3, step into the pipeline
        scaled_feats = power_reg3.named_steps['standardscaler'].transform(feats)
        power_reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])

        if mid == "Machine_1":
            print(f"event:: {topic} Model updated for {mid} with power={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
    power_consumption_persist_all()

def process_units_prod_style(record, mid, topic):
    print(f"{topic} :: {mid} Processing for units production model part")
    raw = state[mid]
    if all(k in raw for k in ['Temperature_C', 'Vibration_mm_s', 'Pressure_bar',
                              'Power_Consumption_kW', 'Machine_Status', 'Alarm_Code',
                              'Units_Produced', 'Defective_Units', 'Production_Time_min']):
        # compute features
        defect_rate = raw['Defective_Units'] / raw['Units_Produced']
        throughput = raw['Units_Produced'] / raw['Production_Time_min']
        energy_eff = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            units_prod_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], units_prod_en_status.transform([raw['Machine_Status']])[0],
            units_prod_en_alarm.transform([raw['Alarm_Code']])[0], defect_rate, throughput, energy_eff
        ]).reshape(1, -1)

        # predictions
        pred = round(units_prod_reg.predict(feats)[0])
        pred2 = round(units_prod_reg2.predict(units_prod_scaler.transform(feats))[0])
        pred3 = round(units_prod_reg3.predict(feats)[0])

        # print(f"event:: {topic} {mid} pred_units={pu:.0f}, pred_defect={pd_:.0f}, pred_time={pt:.0f}")

        y_true = raw['Units_Produced']
        if topic == 'mes-stream' and 'Units_Produced' in record:
            y_true = record['Units_Produced']
            print(
                f"event:: {topic} Updated model for {mid} with true units_produced: {y_true} as received in mes event")

        units_prod_reg.partial_fit(feats, [y_true])
        units_prod_reg2.partial_fit(units_prod_scaler.transform(feats), [y_true])
        # for reg3, step into the pipeline
        scaled_feats = units_prod_reg3.named_steps['standardscaler'].transform(feats)
        units_prod_reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])

        if mid == "Machine_1":
            print(
                f"event:: {topic} Model updated for {mid} with units_produced={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
    units_prod_persist_all()

def process_defective_units_style(record, mid, topic):
    print(f"{topic} :: {mid} Processing for defective units model part")
    raw = state[mid]
    if all(k in raw for k in ['Temperature_C', 'Vibration_mm_s', 'Pressure_bar',
                              'Power_Consumption_kW', 'Machine_Status', 'Alarm_Code',
                              'Units_Produced', 'Defective_Units', 'Production_Time_min']):
        # compute features
        defect_rate = raw['Defective_Units'] / raw['Units_Produced']
        throughput = raw['Units_Produced'] / raw['Production_Time_min']
        energy_eff = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            def_units_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], def_units_en_status.transform([raw['Machine_Status']])[0],
            def_units_en_alarm.transform([raw['Alarm_Code']])[0], defect_rate, throughput, energy_eff
        ]).reshape(1, -1)

        # predictions
        pred = round(def_units_reg.predict(feats)[0])
        pred2 = round(def_units_reg2.predict(def_units_scaler.transform(feats))[0])
        pred3 = round(def_units_reg3.predict(feats)[0])

        # print(f"event:: {topic} {mid} pred_units={pu:.0f}, pred_defect={pd_:.0f}, pred_time={pt:.0f}")

        y_true = raw['Defective_Units']
        if topic == 'mes-stream' and 'Defective_Units' in record:
            y_true = record['Defective_Units']
            print(
                f"event:: {topic} Updated model for {mid} with true defective_units: {y_true} as received in mes event")

        def_units_reg.partial_fit(feats, [y_true])
        def_units_reg2.partial_fit(def_units_scaler.transform(feats), [y_true])
        # for reg3, step into the pipeline
        scaled_feats = def_units_reg3.named_steps['standardscaler'].transform(feats)
        def_units_reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])

        if mid == "Machine_1":
            print(
                f"event:: {topic} Model updated for {mid} with defective_units={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
    def_units_persist_all()

def process_production_time_style(record, mid, topic):
    print(f"{topic} :: {mid} Processing for production time model part")
    raw = state[mid]
    if all(k in raw for k in ['Temperature_C', 'Vibration_mm_s', 'Pressure_bar',
                              'Power_Consumption_kW', 'Machine_Status', 'Alarm_Code',
                              'Units_Produced', 'Defective_Units', 'Production_Time_min']):
        # compute features
        defect_rate = raw['Defective_Units'] / raw['Units_Produced']
        throughput = raw['Units_Produced'] / raw['Production_Time_min']
        energy_eff = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            prod_time_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], prod_time_en_status.transform([raw['Machine_Status']])[0],
            prod_time_en_alarm.transform([raw['Alarm_Code']])[0], defect_rate, throughput, energy_eff
        ]).reshape(1, -1)

        # predictions
        pred = round(prod_time_reg.predict(feats)[0])
        pred2 = round(prod_time_reg2.predict(prod_time_scaler.transform(feats))[0])
        pred3 = round(prod_time_reg3.predict(feats)[0])

        # print(f"event:: {topic} {mid} pred_units={pu:.0f}, pred_defect={pd_:.0f}, pred_time={pt:.0f}")

        y_true = raw['Production_Time_min']
        if topic == 'mes-stream' and 'Production_Time_min' in record:
            y_true = record['Production_Time_min']
            print(
                f"event:: {topic} Updated model for {mid} with true production_time: {y_true} as received in mes event")

        prod_time_reg.partial_fit(feats, [y_true])
        prod_time_reg2.partial_fit(prod_time_scaler.transform(feats), [y_true])
        # for reg3, step into the pipeline
        scaled_feats = prod_time_reg3.named_steps['standardscaler'].transform(feats)
        prod_time_reg3.named_steps['sgdregressor'].partial_fit(scaled_feats, [y_true])

        if mid == "Machine_1":
            print(
                f"event:: {topic} Model updated for {mid} with production_time={y_true}, with pred1={pred}, pred2={pred2}, pred3={pred3}")
    prod_time_persist_all()