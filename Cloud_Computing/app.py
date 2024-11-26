import joblib
import pandas as pd
from influxdb_client import InfluxDBClient
from scipy.stats import skew, kurtosis
import time
import math

from SecretsManager import get_secret

#---------------------------------------------#
# Fetch the secrets from AWS Secrets Manager
secret_data = get_secret('kendo-line-bot-secret')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "SIOT_Test"

# Load model and scaler
model = joblib.load("Cloud_Computing\kendo_move_classifier.pkl")
scaler = joblib.load("Cloud_Computing\RobustScaler.pkl")
le = joblib.load("Cloud_Computing\label_encoder.pkl")
print("Successfully loaded model and scaler.")
#---------------------------------------------#

def extract_features(window):
    features = {}
    for axis in ['accelX', 'accelY', 'accelZ', 'gyroX', 'gyroY', 'gyroZ', 'roll', 'pitch']:
        axis_data = window[axis]
        features[f'{axis}_mean'] = axis_data.mean()
        features[f'{axis}_std'] = axis_data.std()
        features[f'{axis}_max'] = axis_data.max()
        features[f'{axis}_min'] = axis_data.min()
        features[f'{axis}_skew'] = skew(axis_data)
        features[f'{axis}_kurtosis'] = kurtosis(axis_data, fisher=False)
    return pd.DataFrame([features])

# Define the feature order explicitly
feature_order = [
    'accelX_mean', 'accelX_std', 'accelX_max', 'accelX_min', 'accelX_skew', 'accelX_kurtosis',
    'accelY_mean', 'accelY_std', 'accelY_max', 'accelY_min', 'accelY_skew', 'accelY_kurtosis',
    'accelZ_mean', 'accelZ_std', 'accelZ_max', 'accelZ_min', 'accelZ_skew', 'accelZ_kurtosis',
    'gyroX_mean', 'gyroX_std', 'gyroX_max', 'gyroX_min', 'gyroX_skew', 'gyroX_kurtosis',
    'gyroY_mean', 'gyroY_std', 'gyroY_max', 'gyroY_min', 'gyroY_skew', 'gyroY_kurtosis',
    'gyroZ_mean', 'gyroZ_std', 'gyroZ_max', 'gyroZ_min', 'gyroZ_skew', 'gyroZ_kurtosis',
    'roll_mean', 'roll_std', 'roll_max', 'roll_min', 'roll_skew', 'roll_kurtosis',
    'pitch_mean', 'pitch_std', 'pitch_max', 'pitch_min', 'pitch_skew', 'pitch_kurtosis'
]

# Parameters
window_size = 10  # Number of samples per window
fetch_interval = 0.2  # Time in seconds between fetching new data

# Connect to InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()
print("Successfully connected to InfluxDB.")


# Loop for real-time predictions
try:
    while True:
        # Query InfluxDB to fetch the last 30s of data
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -30s)
          |> filter(fn: (r) => r._measurement == "gyro_status")
          |> filter(fn: (r) => r._field == "accelX" or r._field == "accelY" or r._field == "accelZ" or
                               r._field == "gyroX" or r._field == "gyroY" or r._field == "gyroZ" or
                               r._field == "roll" or r._field == "pitch")
          |> sort(columns: ["_time"])
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> drop(columns: ["_start", "_stop", "_measurement"])
        '''

        # Fetch data from InfluxDB
        df = query_api.query_data_frame(query)

        # Check if data is empty
        if df.empty:
            print("No data retrieved, waiting for more data...")
            time.sleep(fetch_interval)
            continue

        # Ensure numeric conversion
        variables = ['accelX', 'accelY', 'accelZ', 'gyroX', 'gyroY', 'gyroZ', 'roll', 'pitch']
        for var in variables:
            df[var] = pd.to_numeric(df[var], errors='coerce')

        # Reset index
        df = df.reset_index(drop=True)

        # Extract the latest window of data
        if len(df) < window_size:
            print(f"Not enough data for a window of size {window_size}, waiting for more data...")
            time.sleep(fetch_interval)
            continue

        # Check for missing values in the window
        if df[variables].isnull().values.any():
            print("Missing data detected in the latest window, waiting for more data...")
            time.sleep(fetch_interval)
            continue

        # Extract features
        features_df = extract_features(df.iloc[-window_size:])
        X_new = features_df[feature_order]

        # Scale the features
        X_new_scaled = scaler.transform(X_new)

        # Make prediction
        prediction = model.predict(X_new_scaled)
        predicted_move = le.inverse_transform(prediction)[0]

        # Output the latest prediction
        print(f'Latest Predicted Move: {predicted_move}')

        # Wait for the next fetch
        time.sleep(fetch_interval)

except KeyboardInterrupt:
    print("Real-time prediction stopped by user.")
except Exception as e:
    print(f"Error: {e}")
