import csv
import random
from datetime import datetime, timedelta

def generate_production_data_csv(
    filename: str, start_str: str, end_str: str
):
    num_machines= 10

    # parse start/end timestamps
    start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    end   = datetime.strptime(end_str,   "%Y-%m-%d %H:%M:%S")
    delta = timedelta(minutes=60)

    # prepare IDs
    machine_ids  = [f"Machine_{i}" for i in range(1, num_machines + 1)]
    operator_ids = list(range(1000, 1010))

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Timestamp",
            "Machine_ID",
            "Operator_ID",
            "Units_Produced",
            "Defective_Units",
            "Production_Time_min"
        ])

        current = start
        while current <= end:
            ts = current.strftime("%Y-%m-%d %H:%M:%S")

            # shuffle operator IDs so each machine gets a unique one
            assigned_ops = random.sample(operator_ids, k=num_machines)

            for mid, op_id in zip(machine_ids, assigned_ops):
                produced  = random.randint(50, 500)
                defective = random.randint(0, 9)
                prod_min  = random.randint(10, 120)
                writer.writerow([
                    ts,
                    mid,
                    op_id,
                    produced,
                    defective,
                    prod_min
                ])

            current += delta

if __name__ == "__main__":
    print("Generating production data for the range 1st Jan - 14th Jan into historical-mes.csv")
    generate_production_data_csv("../generated_data/historical-mes.csv", "2024-01-01 00:00:00", "2024-01-14 23:59:00")
    print("Generating production data for the range 15th Jan - 28th Jan into future-stream-mes.csv")
    generate_production_data_csv("../generated_data/future-stream-mes.csv", "2024-01-15 00:00:00", "2024-01-28 23:59:00")
    print("MES data generated successfully with unique operators per timestamp.")
