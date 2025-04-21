import csv
import random
from datetime import datetime, timedelta

def generate_power_status_csv(
    filename: str, start_str: str, end_str: str
):
    num_machines = 10

    # parse start/end timestamps
    start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    end   = datetime.strptime(end_str,   "%Y-%m-%d %H:%M:%S")
    delta = timedelta(minutes=15)

    # prepare machine IDs
    machine_ids = [f"Machine_{i}" for i in range(1, num_machines + 1)]

    # status and alarm options with their weights
    statuses     = ["Running", "Idle", "Error"]
    status_wts   = [84, 10, 6]  # sums to 100

    alarms       = ["None", "Low Pressure", "Overheat", "Vibration High"]
    alarm_wts    = [90, 5, 3, 2]  # sums to 100

    error_alarms = ["Low Pressure", "Overheat", "Vibration High"]

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Timestamp",
            "Machine_ID",
            "Power_Consumption_kW",
            "Machine_Status",
            "Alarm_Code"
        ])

        current = start
        while current <= end:
            ts = current.strftime("%Y-%m-%d %H:%M:%S")

            for mid in machine_ids:
                power = round(random.uniform(100.00, 200.00), 2)
                status = random.choices(statuses, weights=status_wts, k=1)[0]

                if status == "Idle":
                    alarm = "None"
                elif status == "Error":
                    alarm = random.choice(error_alarms)
                else:
                    alarm = random.choices(alarms, weights=alarm_wts, k=1)[0]

                # alarm  = random.choices(alarms,   weights=alarm_wts,  k=1)[0]

                writer.writerow([
                    ts,
                    mid,
                    f"{power:.2f}",
                    status,
                    alarm
                ])

            current += delta

if __name__ == "__main__":
    print("Generating power status data for the range 1st Jan - 14th Jan into historical-scada.csv")
    generate_power_status_csv("../generated_data/historical-scada.csv", "2024-01-01 00:00:00", "2024-01-14 23:59:00")
    print("Generating power status data for the range 15th Jan - 28th Jan into future-stream-scada.csv")
    generate_power_status_csv("../generated_data/future-stream-scada.csv", "2024-01-15 00:00:00", "2024-01-28 23:59:00")
    print("Scada data generated successfully.")
