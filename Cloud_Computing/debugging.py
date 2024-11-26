#app.py initially had a data export problem with influxdb where the ML results when applied directly is not as accurate as having the data exported as csv then tested on the jupyter notebook.

import pandas as pd
from influxdb_client import InfluxDBClient
import time

from SecretsManager import get_secret

#---------------------------------------------#
# Fetch the secrets from AWS Secrets Manager
secret_data = get_secret('kendo-line-bot-secret')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "SIOT_Test"
#---------------------------------------------#

# Connect to InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()
print("Successfully connected to InfluxDB")

# Define the query to fetch the last 1 minute of data
query = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -1m)
  |> filter(fn: (r) => r._measurement == "gyro_status")
  |> filter(fn: (r) => r._field == "accelX" or r._field == "accelY" or r._field == "accelZ" or
                       r._field == "gyroX" or r._field == "gyroY" or r._field == "gyroZ" or
                       r._field == "pitch" or r._field == "roll")
  |> sort(columns: ["_time"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> drop(columns: ["_start", "_stop", "_measurement"])
'''

# Filepath for the output CSV
output_csv_path = 'last_minute_data.csv'

try:
    # Query the data
    df = query_api.query_data_frame(query)

    # Check if the DataFrame is empty
    if df.empty:
        print("No data found in the last 1 minute.")
    else:
        # Ensure numeric conversion
        variables = ['accelX', 'accelY', 'accelZ', 'gyroX', 'gyroY', 'gyroZ', 'roll', 'pitch']
        for var in variables:
            df[var] = pd.to_numeric(df[var], errors='coerce')

        # Check for missing values
        if df[variables].isnull().values.any():
            print("Missing values detected in the data.")

        # Export to CSV
        df.to_csv(output_csv_path, index=False)
        print(f"Data successfully exported to {output_csv_path}")

except Exception as e:
    print(f"Error during data export: {e}")
