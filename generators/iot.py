import csv
import random
from datetime import datetime, timedelta

def generate_machine_data_csv(
    filename: str, start_str: str, end_str:   str,
    interval_min: int, num_machines: int
):
    # parse our start/end times
    start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    end   = datetime.strptime(end_str,   "%Y-%m-%d %H:%M:%S")
    delta = timedelta(minutes=interval_min)

    # prepare machine IDs
    machine_ids = [f"Machine_{i}" for i in range(1, num_machines + 1)]

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        # write headers
        writer.writerow([
            "Timestamp",
            "Machine_ID",
            "Temperature_C",
            "Vibration_mm_s",
            "Pressure_bar"
        ])

        current = start
        while current <= end:
            ts = current.strftime("%Y-%m-%d %H:%M:%S")
            for mid in machine_ids:
                temp = round(random.uniform(60.00, 80.00), 2)
                vib  = round(random.uniform(0.40, 2.70),  2)
                pres = round(random.uniform(3.00,  7.50),  2)
                # ensure two decimal places
                writer.writerow([
                    ts,
                    mid,
                    f"{temp:.2f}",
                    f"{vib:.2f}",
                    f"{pres:.2f}"
                ])
            current += delta

if __name__ == "__main__":
    print("Generating data for the range 1st Jan - 14th Jan into historical-iot.csv")
    generate_machine_data_csv("../generated_data/historical-iot.csv", "2024-01-01 00:00:00", "2024-01-14 23:59:00", 1, 10)
    print("Generating data for the range 15th Jan - 28th Jan into future-stream-iot.csv")
    generate_machine_data_csv("../generated_data/future-stream-iot.csv", "2024-01-15 00:00:00", "2024-01-28 23:59:00", 1, 10)
    print("IOT data generated successfully.")
