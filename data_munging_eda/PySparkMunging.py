import json
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import  *
import re


def quoter(row):
    """
    Takes a JSON row and will replace the occurrences of double-double quotes ("") with a single double quote (")
    :param row: A cell from the Targets Column
    :return: a valid JSON format String
    """
    return [row[0], re.sub('""', '"', row[1])]


def col_name_extractor(row):
    row1 = json.loads(row[1])
    result = []
    for item in row1:
        if " " not in item["target"]:
            result.append("target" + "_" + item["target"])
    return [row[0], result]


def value_extractor(row):
    row1 = json.loads(row[1])
    result = []
    for item in row1:
        try:
            result.append(item["segment"])
        except:
            result.append(" ")
    return result


def flattner(rdd):
    """

    :param rdd: the RDD Of either the Columns or the Values extracted from the targets column
    :return: A flat list of those values
    """
    flattened_rdd = rdd.flatMap(lambda x: x[1])
    unique_set = set(flattened_rdd.collect())

    return list(unique_set)


def json_ready(df):
    """
    Takes the Targets Columns and returns in
    :param df: The Dataframe of the targets column
    :return: a cleaned up and JSON processing ready PySpark RDD of that column
    """
    rdd = df.select("targets").rdd
    rdd2 = rdd.zipWithIndex().map(lambda x: (x[1], x[0][0]))
    rdd3 = rdd2.map(quoter)

    return rdd3


file_path = "/home/fneffati/DataSets/propublica_1000.csv"

spark = SparkSession.builder \
    .master('local[1]') \
    .getOrCreate()
df = spark.read.csv(file_path, header=True, inferSchema=True, multiLine=True, sep=',', escape='"',
                    ignoreLeadingWhiteSpace=True)
df.select("targets").show(5, truncate=False)

jsoned_rdd = json_ready(df)

cols = jsoned_rdd.map(col_name_extractor)  # 2D RDD of the columns per cell
flat_cols_unique_list = flattner(cols)     # list of unique column names
print(flat_cols_unique_list)

"""# Add the unique columns as empty columns to the Dataframe
for col_name in flat_cols_unique_list:
    df = df.withColumn(col_name, lit(" "))"""

vals = jsoned_rdd.map(value_extractor)     # 2D RDD of the values per cell
print(vals.take(5))
print("\n")
columns_list = cols.collect()
values_list = vals.collect()

rdd = df.rdd
modified_rdd = rdd
# TODO: Turn this bit into MAP function
# Create an empty dataframe
new_rows = []
for item in columns_list:
    column_index = item[0]
    col_group = item[1]
    for index2, col_name in enumerate(col_group):
        row_index = index2
        value = values_list[column_index][row_index]
        new_row = Row(col_name=col_name, value=value)
        new_rows.append(new_row)

# Create a new DataFrame using the new rows
df = spark.createDataFrame(new_rows)


# Add a unique row identifier
df = df.withColumn("row_id", monotonically_increasing_id())

# Pivot the dataframe to convert it to wide format
wide_df = df.groupBy("row_id").pivot("col_name").agg(first("value"))

# Show the resulting dataframe
wide_df.show(truncate=False)