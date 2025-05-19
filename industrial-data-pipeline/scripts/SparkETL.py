from pyspark.sql.functions import when
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, abs, unix_timestamp, row_number
from pyspark.sql.window import Window

# Initialize SparkSession
spark = SparkSession.builder \
    .appName("MergeToMachineMetrics") \
    .master("spark://spark-master:7077") \
    .config("spark.jars", "/home/jovyan/jars/mysql-connector-j-8.0.33.jar") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# JDBC configs
jdbc_url = "jdbc:mysql://starrocks-allin1:9030/industrial_warehouse"
jdbc_props = {"user": "root", "password": "", "driver": "com.mysql.cj.jdbc.Driver"}

# Load staging and dimension tables
iot_df = spark.read.jdbc(jdbc_url, "staging_iot_stream", properties=jdbc_props).withColumn("Timestamp", col("Timestamp").cast("timestamp"))
mes_df = spark.read.jdbc(jdbc_url, "staging_mes_stream", properties=jdbc_props).withColumn("Timestamp", col("Timestamp").cast("timestamp"))
scada_df = spark.read.jdbc(jdbc_url, "staging_scada_stream", properties=jdbc_props).withColumn("Timestamp", col("Timestamp").cast("timestamp"))
status_df = spark.read.jdbc(jdbc_url, "MachineStatus", properties=jdbc_props)
alarm_df = spark.read.jdbc(jdbc_url, "AlarmCodes", properties=jdbc_props)

# Best MES within ±1 hour
mes_join = iot_df.alias("i").join(mes_df.alias("m"), "Machine_ID") \
    .withColumn("time_diff", abs(unix_timestamp(col("i.Timestamp")) - unix_timestamp(col("m.Timestamp")))) \
    .filter(col("time_diff") <= 3600)

mes_window = Window.partitionBy("i.Machine_ID", "i.Timestamp").orderBy("time_diff")
mes_best = mes_join.withColumn("rn", row_number().over(mes_window)).filter(col("rn") == 1) \
    .select(
        col("i.Timestamp").alias("iot_Timestamp"),
        col("i.Machine_ID"),
        col("i.Temperature_C"),
        col("i.Vibration_mm_s"),
        col("i.Pressure_bar"),
        col("m.Operator_ID"),
        col("m.Units_Produced"),
        col("m.Defective_Units"),
        col("m.Production_Time_min")
    )

# Best SCADA within ±15 minutes
scada_join = iot_df.alias("i").join(scada_df.alias("s"), "Machine_ID") \
    .withColumn("time_diff", abs(unix_timestamp(col("i.Timestamp")) - unix_timestamp(col("s.Timestamp")))) \
    .filter(col("time_diff") <= 900)

scada_window = Window.partitionBy("i.Machine_ID", "i.Timestamp").orderBy("time_diff")
scada_best = scada_join.withColumn("rn", row_number().over(scada_window)).filter(col("rn") == 1) \
    .select(
        col("i.Timestamp").alias("iot_Timestamp"),
        col("i.Machine_ID"),
        col("s.Power_Consumption_kW"),
        col("s.Machine_Status").alias("Machine_Status_Name"),
        when(col("s.Alarm_Code") == "", "None").otherwise(col("s.Alarm_Code")).alias("Alarm_Code_Desc")
    )

# Join all and enrich with IDs
final_df = mes_best.alias("m").join(scada_best.alias("s"),
    (col("m.Machine_ID") == col("s.Machine_ID")) & (col("m.iot_Timestamp") == col("s.iot_Timestamp")),
    how="left"
).join(status_df.alias("ms"), col("s.Machine_Status_Name") == col("ms.StatusName"), "left") \
 .join(alarm_df.alias("ac"), col("s.Alarm_Code_Desc") == col("ac.AlarmDescription"), "left") \
 .select(
    col("m.iot_Timestamp").alias("Timestamp"),
    col("m.Machine_ID"),
    col("m.Temperature_C"),
    col("m.Vibration_mm_s"),
    col("m.Pressure_bar"),
    col("m.Operator_ID"),
    col("m.Units_Produced"),
    col("m.Defective_Units"),
    col("m.Production_Time_min"),
    col("s.Power_Consumption_kW"),
    col("ms.StatusID").alias("Machine_Status_ID"),
    col("ms.StatusName").alias("Machine_Status"),
    col("ac.AlarmID").alias("Alarm_ID"),
    col("ac.AlarmDescription").alias("Alarm_Code")
)

# Write to StarRocks
try:
    final_df.write.mode("append").format("jdbc") \
        .option("url", jdbc_url) \
        .option("dbtable", "machine_metrics") \
        .option("user", "root") \
        .option("password", "") \
        .option("driver", "com.mysql.cj.jdbc.Driver") \
        .save()
    print("Data inserted into machine_metrics.")
except Exception as e:
    print("Failed to write to StarRocks:", e)