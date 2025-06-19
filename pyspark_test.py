from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_replace

# Utility function to remove extra spaces
def remove_extra_spaces(df, column_name):
    return df.withColumn(column_name, regexp_replace(col(column_name), "\\s+", " "))

# Create a SparkSession
spark = SparkSession.builder.appName("Testing PySpark Example").getOrCreate()

# Sample data
sample_data = [
    {"name": "John    D.", "age": 30},
    {"name": "Alice   G.", "age": 25},
    {"name": "Bob  T.", "age": 35},
    {"name": "Eve   A.", "age": 28}
]

# Create DataFrame
df = spark.createDataFrame(sample_data)

# Apply transformation
transformed_df = remove_extra_spaces(df, "name")

# Show result
transformed_df.show()
