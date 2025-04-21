from pyspark.sql import SparkSession

# Step 1: Start Spark session
spark = SparkSession.builder \
    .appName("ReadFromStarRocks") \
    .getOrCreate()

# Step 2: Read from StarRocks using JDBC
df = spark.read \
    .format("jdbc") \
    .option("url", "jdbc:mysql://starrocks:9030/industrial_warehouse") \
    .option("dbtable", "machine_metrics") \
    .option("user", "root") \
    .option("password", "") \
    .option("driver", "com.mysql.cj.jdbc.Driver") \
    .load()

# Step 3: Show data
df.show(10)