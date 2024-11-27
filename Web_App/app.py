# Install dependencies before running (streamlit, pandas, influxdb-client, json, boto3)
# streamlit run c:/Users/beam_/OneDrive/Desktop/KendoAI/Web_App/app.py
#---------------------------------------------#
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

if "last_avg_accel" not in st.session_state:
    st.session_state.last_avg_accel = 0.00
if "last_avg_jerk" not in st.session_state:
    st.session_state.last_avg_jerk = 0.00
if "last_smoothness" not in st.session_state:
    st.session_state.last_smoothness = 0.00
if "last_prediction" not in st.session_state:
    st.session_state.last_prediction = "None"
if "last_mic" not in st.session_state:
    st.session_state.last_mic = "N/A"
if "last_temperature" not in st.session_state:
    st.session_state.last_temperature = "N/A"
if "last_humidity" not in st.session_state:
    st.session_state.last_humidity = "N/A"


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

# Define movement smoothness calculation
def calculate_smoothness(data, smooth_threshold=0.5):
    # Calculate acceleration magnitude
    data['accel_magnitude'] = np.sqrt(data['accelX']**2 + data['accelY']**2 + data['accelZ']**2)
    
    # Calculate jerk (rate of change of acceleration)
    data['jerk'] = data['accel_magnitude'].diff() / data.index.to_series().diff().dt.total_seconds()
    
    # Classify smoothness
    smooth_movements = data['jerk'].abs() < smooth_threshold
    smooth_percentage = smooth_movements.mean() * 100 if not data.empty else 0
    return smooth_percentage

def fetch_environment_data():
    """
    Fetch the latest environment data (mic, temperature, humidity) from InfluxDB.
    """
    query = f'''
    from(bucket: "environment_data")
      |> range(start: -1m)  // Fetch data from the last minute
      |> filter(fn: (r) => r["_measurement"] == "sensor_data")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 1)
    '''
    try:
        query_api = client.query_api()
        tables = query_api.query(query)
        if tables:
            records = [record.values for table in tables for record in table.records]
            if records:
                return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error fetching environment data from InfluxDB: {e}")
    return pd.DataFrame()

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
    avg_accel_metric = st.metric("Avg Acceleration (m/s²)", f"{st.session_state.last_avg_accel:.2f}")
    mic_metric = st.metric("Mic Status", st.session_state.last_mic)
with col2:
    jerk_metric = st.metric("Avg Jerk (m/s³)", f"{st.session_state.last_avg_jerk:.2f}")
    temp_metric = st.metric("Temperature (°C)", st.session_state.last_temperature)
with col3:
    smoothness_metric = st.metric("Smooth Movements (%)", f"{st.session_state.last_smoothness:.2f}")
    hum_metric = st.metric("Humidity (%)", st.session_state.last_humidity)
with col4:
    prediction_metric = st.metric("Prediction", st.session_state.last_prediction)

# Chart Placeholders
st.header("Accelerometer Data:")
accel_chart = st.line_chart(st.session_state.accel_data)

st.header("Gyroscope Data:")
gyro_chart = st.line_chart(st.session_state.gyro_data)

#Live Feed
st.header("Live Video Feed")

# Embed the video feed from ESP32
video_feed_url = secret_data.get('esp32cam_link')
st.markdown(
    f"""
    <div style="text-align:center;">
        <iframe src="{video_feed_url}" width="640" height="480" frameborder="0" allowfullscreen></iframe>
    </div>
    """,
    unsafe_allow_html=True
)

# Main Loop
while st.session_state.is_running:
    # Fetch environment data
    environment_data = fetch_environment_data()

    if not environment_data.empty:
        # Parse the latest environment data
        env_latest = environment_data.iloc[0]
        mic = env_latest.get("mic", None)
        mic_status = "High" if mic == 1 else "Low" if mic == 0 else "N/A"
        temperature = env_latest.get("temperature", "N/A")
        humidity = env_latest.get("humidity", "N/A")

        # Update Session State for Environment Metrics
        st.session_state.last_mic = mic_status
        st.session_state.last_temperature = temperature
        st.session_state.last_humidity = humidity

    # Continue with existing accelerometer and gyroscope data fetching...
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

    # Check if accelerometer/gyroscope data is retrieved
    if not data.empty:
        data["_time"] = pd.to_datetime(data["_time"])
        data.set_index("_time", inplace=True)
        st.session_state.accel_data = data[["accelX", "accelY", "accelZ"]]
        st.session_state.gyro_data = data[["gyroX", "gyroY", "gyroZ"]]

        if len(data) >= window_size:
            latest_window = data.iloc[-window_size:]
            features_df = extract_features(latest_window)
            X_new = features_df[feature_order]
            X_scaled = scaler.transform(X_new)
            prediction = model.predict(X_scaled)
            st.session_state.last_prediction = le.inverse_transform(prediction)[0]

            # Calculate smoothness
            smooth_percentage = calculate_smoothness(data)

            # Calculate average jerk
            data['jerk'] = data['accel_magnitude'].diff() / data.index.to_series().diff().dt.total_seconds()
            avg_jerk = data['jerk'].mean() if 'jerk' in data else 0

            # Update Metrics
            avg_accel_metric.metric("Avg Acceleration (m/s²)", f"{st.session_state.accel_data.mean().mean():.2f}")
            smoothness_metric.metric("Smooth Movements (%)", f"{smooth_percentage:.2f}")
            jerk_metric.metric("Avg Jerk (m/s³)", f"{avg_jerk:.2f}")
            prediction_metric.metric("Prediction", st.session_state.last_prediction)

            # Update Session State
            st.session_state.last_avg_accel = st.session_state.accel_data.mean().mean()
            st.session_state.last_avg_jerk = avg_jerk
            st.session_state.last_smoothness = smooth_percentage
            st.session_state.last_prediction = st.session_state.last_prediction

    else:
        st.warning("No accelerometer/gyroscope data available.")

    # Refresh Interval
    time.sleep(REFRESH_INTERVAL)