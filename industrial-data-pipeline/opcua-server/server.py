import asyncio
from asyncua import Server
from asyncua.ua import VariantType
import pandas as pd
from datetime import datetime

async def publish_sensor(server, idx, df_sensor):
    objects = server.get_objects_node()
    sensor_node = await objects.get_child([f"{idx}:Sensors"])
    ts_sensor = await sensor_node.get_child([f"{idx}:Timestamp_Sensor"])
    sensors = {}
    for m in df_sensor['Machine_ID'].unique():
        obj = await sensor_node.get_child([f"{idx}:{m}"])
        sensors[m] = {
            'Temperature_C': await obj.get_child([f"{idx}:Temperature_C"]),
            'Vibration_mm_s': await obj.get_child([f"{idx}:Vibration_mm_s"]),
            'Pressure_bar': await obj.get_child([f"{idx}:Pressure_bar"]),
        }

    for ts in sorted(df_sensor['Timestamp'].unique()):
        await ts_sensor.write_value(ts.to_pydatetime(), VariantType.DateTime)
        batch = df_sensor[df_sensor['Timestamp'] == ts]
        for _, row in batch.iterrows():
            m = row['Machine_ID']
            await sensors[m]['Temperature_C'].write_value(float(row['Temperature_C']))
            await sensors[m]['Vibration_mm_s'].write_value(float(row['Vibration_mm_s']))
            await sensors[m]['Pressure_bar'].write_value(float(row['Pressure_bar']))
        print(f"{datetime.now().isoformat()} – Sensor published {len(batch)} records @ {ts}")
        await asyncio.sleep(2)

async def publish_scada(server, idx, df_scada):
    objects = server.get_objects_node()
    scada_node = await objects.get_child([f"{idx}:SCADA"])
    ts_scada = await scada_node.get_child([f"{idx}:Timestamp_SCADA"])
    scadas = {}
    for m in df_scada['Machine_ID'].unique():
        obj = await scada_node.get_child([f"{idx}:{m}"])
        scadas[m] = {
            'Power_Consumption_kW': await obj.get_child([f"{idx}:Power_Consumption_kW"]),
            'Machine_Status': await obj.get_child([f"{idx}:Machine_Status"]),
            'Alarm_Code': await obj.get_child([f"{idx}:Alarm_Code"]),
        }

    for ts in sorted(df_scada['Timestamp'].unique()):
        await ts_scada.write_value(ts.to_pydatetime(), VariantType.DateTime)
        batch = df_scada[df_scada['Timestamp'] == ts]
        for _, row in batch.iterrows():
            m = row['Machine_ID']
            await scadas[m]['Power_Consumption_kW'].write_value(float(row['Power_Consumption_kW']))
            # default to empty string if missing
            status = row['Machine_Status'] if pd.notna(row['Machine_Status']) else ""
            alarm = row['Alarm_Code'] if pd.notna(row['Alarm_Code']) and row['Alarm_Code'] not in ("", "None") else ""
            await scadas[m]['Machine_Status'].write_value(status)
            await scadas[m]['Alarm_Code'].write_value(alarm)
        print(f"{datetime.now().isoformat()} – SCADA published {len(batch)} records @ {ts}")
        await asyncio.sleep(2)

async def main():
    # Load CSVs
    df_sensor = pd.read_csv('sensor_data.csv', parse_dates=['Timestamp'])
    df_sensor['Machine_ID'] = df_sensor['Machine_ID'].astype(str)
    df_scada = pd.read_csv('future-stream-scada.csv', parse_dates=['Timestamp'])
    df_scada['Machine_ID'] = df_scada['Machine_ID'].astype(str)

    # OPC UA server setup
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    idx = await server.register_namespace("iot_sensors_scada")
    objects = server.get_objects_node()

    # Create root nodes and timestamp variables
    sensor_node = await objects.add_object(idx, "Sensors")
    ts_sensor = await sensor_node.add_variable(idx, "Timestamp_Sensor",
                                              df_sensor['Timestamp'].iloc[0].to_pydatetime())
    await ts_sensor.set_writable()

    scada_node = await objects.add_object(idx, "SCADA")
    ts_scada = await scada_node.add_variable(idx, "Timestamp_SCADA",
                                            df_scada['Timestamp'].iloc[0].to_pydatetime())
    await ts_scada.set_writable()

    # Create machine variables
    for m in df_sensor['Machine_ID'].unique():
        obj = await sensor_node.add_object(idx, m)
        for meas in ['Temperature_C', 'Vibration_mm_s', 'Pressure_bar']:
            var = await obj.add_variable(idx, meas, 0.0)
            await var.set_writable()

    for m in df_scada['Machine_ID'].unique():
        obj = await scada_node.add_object(idx, m)
        pow_var = await obj.add_variable(idx, 'Power_Consumption_kW', 0.0)
        await pow_var.set_writable()
        status_var = await obj.add_variable(idx, 'Machine_Status', "")
        alarm_var = await obj.add_variable(idx, 'Alarm_Code', "")
        await status_var.set_writable()
        await alarm_var.set_writable()

    # Start server and publishing
    await server.start()
    print(f"Server started at {server.endpoint}")

    try:
        await asyncio.gather(
            publish_sensor(server, idx, df_sensor),
            publish_scada(server, idx, df_scada)
        )
    except Exception as e:
        print("Error:", e)
    finally:
        await server.stop()
        print("Server stopped")

if __name__ == "__main__":
    asyncio.run(main())
