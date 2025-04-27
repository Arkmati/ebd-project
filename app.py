import numpy as np
from fastapi import FastAPI
import uvicorn
import threading
from pydantic import BaseModel

# from models.status_alarm_model import state as status_alarm_state
from models.status_alarm_model import en_machine as status_alarm_en_machine
from models.status_alarm_model import en_status as status_alarm_en_status
from models.status_alarm_model import en_alarm as status_alarm_en_alarm
from models.status_alarm_model import status_clf, alarm_clf

# from models.power_consumption_model import state as power_state
from models.power_consumption_model import en_machine as power_en_machine
from models.power_consumption_model import en_status as power_en_status
from models.power_consumption_model import en_alarm as power_en_alarm
from models.power_consumption_model import reg as power_reg
from models.power_consumption_model import reg2 as power_reg2
from models.power_consumption_model import reg3 as power_reg3
from models.power_consumption_model import scaler as power_scaler

# from models.units_prod_model import state as units_prod_state
from models.units_prod_model import en_machine as units_prod_en_machine
from models.units_prod_model import en_status as units_prod_en_status
from models.units_prod_model import en_alarm as units_prod_en_alarm
from models.units_prod_model import reg as units_prod_reg
from models.units_prod_model import reg2 as units_prod_reg2
from models.units_prod_model import reg3 as units_prod_reg3
from models.units_prod_model import scaler as units_prod_scaler

# from models.defective_units_model import state as defective_units_state
from models.defective_units_model import en_machine as def_units_en_machine
from models.defective_units_model import en_status as def_units_en_status
from models.defective_units_model import en_alarm as def_units_en_alarm
from models.defective_units_model import reg as def_units_reg
from models.defective_units_model import reg2 as def_units_reg2
from models.defective_units_model import reg3 as def_units_reg3
from models.defective_units_model import scaler as def_units_scaler

# from models.prod_time_model import state as prod_time_state
from models.prod_time_model import en_machine as prod_time_en_machine
from models.prod_time_model import en_status as prod_time_en_status
from models.prod_time_model import en_alarm as prod_time_en_alarm
from models.prod_time_model import reg as prod_time_reg
from models.prod_time_model import reg2 as prod_time_reg2
from models.prod_time_model import reg3 as prod_time_reg3
from models.prod_time_model import scaler as prod_time_scaler

from kafka_consumer_loop import state, kafka_consumer_loop

app = FastAPI()

class ForecastRequest(BaseModel):
    machine_id: str

@app.post('/forecast-status')
def forecast_status(req: ForecastRequest):
    print(f"forecast_status request received: {req}")
    mid = req.machine_id
    if mid not in status_alarm_state or not all(
            k in status_alarm_state[mid] for k in ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']):
        print(f"Missing state for {mid} for forecast status request")
        results = {'Machine_ID': mid, 'Machine_Status': None, 'Alarm_Code': None}
    else:
        feats = np.array([
            status_alarm_en_machine.transform([mid])[0],
            status_alarm_state[mid]['Power_Consumption_kW'],
            status_alarm_state[mid]['Temperature_C'],
            status_alarm_state[mid]['Vibration_mm_s'],
            status_alarm_state[mid]['Pressure_bar']
        ]).reshape(1, -1)
        ps = status_clf.predict_proba(feats)[0]
        status = status_alarm_en_status.inverse_transform([np.argmax(ps)])[0]
        # results.append({'Machine_ID': mid, 'Machine_Status': status, 'Alarm_Code': alarm})
        results = {'Machine_ID': mid, 'Machine_Status': status, 'current': status_alarm_state[mid]['Machine_Status']}
        # for ts in times:
        print(f"Forecast_status generated for {req.machine_id} with status {status}")
    return results

@app.post('/forecast-alarm')
def forecast_alarm(req: ForecastRequest):
    print(f"forecast_alarm request received: {req}")
    mid = req.machine_id
    if mid not in status_alarm_state or not all(
            k in status_alarm_state[mid] for k in ['Power_Consumption_kW', 'Temperature_C', 'Vibration_mm_s', 'Pressure_bar']):
        print(f"Missing state for {mid} for forecast alarm request")
        results = {'Machine_ID': mid, 'Machine_Status': None, 'Alarm_Code': None}
    else:
        feats = np.array([
            status_alarm_en_machine.transform([mid])[0],
            status_alarm_state[mid]['Power_Consumption_kW'],
            status_alarm_state[mid]['Temperature_C'],
            status_alarm_state[mid]['Vibration_mm_s'],
            status_alarm_state[mid]['Pressure_bar']
        ]).reshape(1, -1)
        pa = alarm_clf.predict_proba(feats)[0]
        alarm = status_alarm_en_alarm.inverse_transform([np.argmax(pa)])[0]
        # results.append({'Machine_ID': mid, 'Machine_Status': status, 'Alarm_Code': alarm})
        results = {'Machine_ID': mid, 'Alarm_Code': alarm, "current": status_alarm_state[mid]['Alarm_Code']}
        # for ts in times:
        print(f"Forecast_alarm generated for {req.machine_id} with alarm {alarm}")
    return results

@app.post('/forecast-power')
def forecast_power(req: ForecastRequest):
    mid = req.machine_id
    if mid not in power_state or not all(
       k in power_state[mid] for k in [
           'Temperature_C','Vibration_mm_s','Pressure_bar',
           'Machine_Status','Alarm_Code',
           'Units_Produced','Production_Time_min'
       ]):
        print(f"Missing state for {mid} for forecast power request")
        result = {'Machine_ID': mid, 'Predicted_Power_kW': None}
        # raise HTTPException(status_code=404, detail=f"Insufficient state for {mid}")
    else:
        feats = np.array([
            power_en_machine.transform([mid])[0],
            power_state[mid]['Temperature_C'],
            power_state[mid]['Vibration_mm_s'],
            power_state[mid]['Pressure_bar'],
            power_en_status.transform([power_state[mid]['Machine_Status']])[0],
            power_en_alarm.transform([power_state[mid]['Alarm_Code']])[0],
            power_state[mid]['Units_Produced'] / power_state[mid]['Production_Time_min'],
            power_state[mid]['Defective_Units'] / power_state[mid]['Units_Produced']
        ]).reshape(1, -1)
        pred = round(power_reg.predict(feats)[0], 2)
        pred2 = round(power_reg2.predict(power_scaler.transform(feats))[0], 2)
        pred3 = round(power_reg3.predict(feats)[0], 2)
        print(f"Forecast_power generated for {req.machine_id} with power value: {pred:.2f}")
        result = {'Machine_ID': mid, 'Predicted_Power_kW': float(pred), "current":power_state[mid]['Power_Consumption_kW'],
                  "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
    return result

@app.post('/forecast-units-prod')
def forecast_units_prod(req: ForecastRequest):
    mid = req.machine_id
    if mid not in units_prod_state or not all(
       k in units_prod_state[mid] for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
                                  'Power_Consumption_kW','Machine_Status','Alarm_Code',
                                  'Units_Produced','Defective_Units','Production_Time_min']):
        print(f"Missing state for {mid} for forecast units productions request")
        result = {'Machine_ID': mid, 'Predicted_Units_Produced': None}
    else:
        raw = units_prod_state.get(mid)
        dr = raw['Defective_Units'] / raw['Units_Produced']
        th = raw['Units_Produced'] / raw['Production_Time_min']
        ee = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            units_prod_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], units_prod_en_status.transform([raw['Machine_Status']])[0],
            units_prod_en_alarm.transform([raw['Alarm_Code']])[0], dr, th, ee
        ]).reshape(1, -1)
        pred = round(units_prod_reg.predict(feats)[0])
        pred2 = round(units_prod_reg2.predict(units_prod_scaler.transform(feats))[0])
        pred3 = round(units_prod_reg3.predict(feats)[0])
        print(f"Forecast_units produced generated for {req.machine_id} with predicted value: {pred2}")
        result = {'Machine_ID': mid, 'Predicted_Units_Produced': pred2, "current":units_prod_state[mid]['Units_Produced'],
                  "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
    return result

@app.post('/forecast-defective-units')
def forecast_defective_units(req: ForecastRequest):
    mid = req.machine_id
    if mid not in defective_units_state or not all(
       k in defective_units_state[mid] for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
                                  'Power_Consumption_kW','Machine_Status','Alarm_Code',
                                  'Units_Produced','Defective_Units','Production_Time_min']):
        print(f"Missing state for {mid} for forecast defective units request")
        result = {'Machine_ID': mid, 'Predicted_Defective_Units': None}
    else:
        raw = defective_units_state.get(mid)
        dr = raw['Defective_Units'] / raw['Units_Produced']
        th = raw['Units_Produced'] / raw['Production_Time_min']
        ee = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            def_units_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], def_units_en_status.transform([raw['Machine_Status']])[0],
            def_units_en_alarm.transform([raw['Alarm_Code']])[0], dr, th, ee
        ]).reshape(1, -1)
        pred = round(def_units_reg.predict(feats)[0])
        pred2 = round(def_units_reg2.predict(def_units_scaler.transform(feats))[0])
        pred3 = round(def_units_reg3.predict(feats)[0])
        print(f"Forecast_defective_units produced generated for {req.machine_id} with predicted value: {pred2}")
        result = {'Machine_ID': mid, 'Predicted_Defective_Units': pred2, "current":defective_units_state[mid]['Defective_Units'],
                  "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
    return result

@app.post('/forecast-production-time')
def forecast_production_time(req: ForecastRequest):
    mid = req.machine_id
    if mid not in prod_time_state or not all(
       k in prod_time_state[mid] for k in ['Temperature_C','Vibration_mm_s','Pressure_bar',
                                  'Power_Consumption_kW','Machine_Status','Alarm_Code',
                                  'Units_Produced','Defective_Units','Production_Time_min']):
        print(f"Missing state for {mid} for forecast production time request request")
        result = {'Machine_ID': mid, 'Predicted_Production_Time_min': None}
    else:
        raw = prod_time_state.get(mid)
        dr = raw['Defective_Units'] / raw['Units_Produced']
        th = raw['Units_Produced'] / raw['Production_Time_min']
        ee = (raw['Power_Consumption_kW'] * (raw['Production_Time_min'] / 60)) / raw['Units_Produced']
        feats = np.array([
            prod_time_en_machine.transform([mid])[0], raw['Temperature_C'], raw['Vibration_mm_s'], raw['Pressure_bar'],
            raw['Power_Consumption_kW'], prod_time_en_status.transform([raw['Machine_Status']])[0],
            prod_time_en_alarm.transform([raw['Alarm_Code']])[0], dr, th, ee
        ]).reshape(1, -1)
        pred = round(prod_time_reg.predict(feats)[0])
        pred2 = round(prod_time_reg2.predict(prod_time_scaler.transform(feats))[0])
        pred3 = round(prod_time_reg3.predict(feats)[0])
        print(f"Forecast_production time produced generated for {req.machine_id} with predicted value: {pred2}")
        result = {'Machine_ID': mid, 'Predicted_Production_Time_min': pred2, "current":prod_time_state[mid]['Production_Time_min'],
                  "additional_predictions":{"pred1":pred, "pred2": pred2, "pred3": pred3}}
    return result

threading.Thread(target=kafka_consumer_loop, daemon=True, name='KafkaConsumer').start()

if __name__ == '__main__':
    print("Starting FastAPI app on port 8000...")
    uvicorn.run(app, host='0.0.0.0', port=8000)