# This is the streamlit script to test out the prediction model when deployed on cloud

# Import libraries
import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
from scipy.stats import skew, kurtosis
import numpy as np
import joblib
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

# Load model and scaler
model = joblib.load("Web_App/kendo_move_classifier.pkl")
scaler = joblib.load("Web_App/RobustScaler.pkl")
le = joblib.load("Web_App/label_encoder.pkl")
print("Successfully loaded model and scaler.")

# Initialize InfluxDB Client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# Parameters
window_size = 10  # Number of samples per window
fetch_interval = 0.5  # Time in seconds between fetching new data
REFRESH_INTERVAL = 0.5  # Time interval for Streamlit updates

# Variables for Streamlit
variables = ['accelX', 'accelY', 'accelZ', 'gyroX', 'gyroY', 'gyroZ', 'roll', 'pitch']

# Define feature extraction
def extract_features(window):
    features = {}
    for axis in variables:
        axis_data = window[axis]
        features[f'{axis}_mean'] = axis_data.mean()
        features[f'{axis}_std'] = axis_data.std()
        features[f'{axis}_max'] = axis_data.max()
        features[f'{axis}_min'] = axis_data.min()
        features[f'{axis}_skew'] = skew(axis_data)
        features[f'{axis}_kurtosis'] = kurtosis(axis_data, fisher=False)
    return pd.DataFrame([features])

# Define feature order
feature_order = [f'{axis}_{stat}' for axis in variables for stat in ['mean', 'std', 'max', 'min', 'skew', 'kurtosis']]

# Streamlit Configuration
st.set_page_config(page_title="KiAI - Kendo Assistant", page_icon="🤺")
st.title("KiAI - Kendo Assistant")

# Initialize Session State
if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "accel_data" not in st.session_state:
    st.session_state.accel_data = pd.DataFrame(columns=["accelX", "accelY", "accelZ"])

if "gyro_data" not in st.session_state:
    st.session_state.gyro_data = pd.DataFrame(columns=["gyroX", "gyroY", "gyroZ"])

if "last_prediction" not in st.session_state:
    st.session_state.last_prediction = None

# Start/Stop Button
if st.button("Start/Stop Data Fetching"):
    st.session_state.is_running = not st.session_state.is_running

# Display current status
status = "Running" if st.session_state.is_running else "Stopped"
st.write(f"Status: **{status}**")

# Metrics Section
col1, col2, col3, col4 = st.columns(4)
with col1:
    avg_accel_metric = st.metric("Avg Acceleration (m/s²)", "0.00")
with col2:
    jerk_metric = st.metric("Avg Jerk (m/s³)", "0.00")
with col3:
    speed_metric = st.metric("Speed (m/s)", "0.00")
with col4:
    prediction_metric = st.metric("Prediction", "None")

# Chart Placeholders
st.header("Accelerometer Data:")
accel_chart = st.line_chart(st.session_state.accel_data)

st.header("Gyroscope Data:")
gyro_chart = st.line_chart(st.session_state.gyro_data)

# Main Loop
while st.session_state.is_running:
    # Fetch data from InfluxDB
    query = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -30s)
  |> filter(fn: (r) => r._measurement == "gyro_status")
  |> filter(fn: (r) => r._field == "accelX" or r._field == "accelY" or r._field == "accelZ" or
                       r._field == "gyroX" or r._field == "gyroY" or r._field == "gyroZ" or
                       r._field == "roll" or r._field == "pitch")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> drop(columns: ["_start", "_stop", "_measurement"])
'''

    data = query_api.query_data_frame(query)

    # Check if data is retrieved
    if not data.empty:
        data["_time"] = pd.to_datetime(data["_time"])
        data.set_index("_time", inplace=True)
        st.session_state.accel_data = data[["accelX", "accelY", "accelZ"]]
        st.session_state.gyro_data = data[["gyroX", "gyroY", "gyroZ"]]

        # Update metrics
        if len(data) >= window_size:
            latest_window = data.iloc[-window_size:]
            features_df = extract_features(latest_window)
            X_new = features_df[feature_order]
            X_scaled = scaler.transform(X_new)
            prediction = model.predict(X_scaled)
            st.session_state.last_prediction = le.inverse_transform(prediction)[0]

            # Update Metrics
            avg_accel_metric.metric("Avg Acceleration (m/s²)", f"{st.session_state.accel_data.mean().mean():.2f}")
            prediction_metric.metric("Prediction", st.session_state.last_prediction)

        # Update Charts
        accel_chart.line_chart(st.session_state.accel_data)
        gyro_chart.line_chart(st.session_state.gyro_data)
    else:
        st.warning("No data available.")

    # Refresh Interval
    time.sleep(REFRESH_INTERVAL)
