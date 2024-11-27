# Install dependencies before running (streamlit, pandas, influxdb-client, json, boto3)
# streamlit run c:/Users/beam_/OneDrive/Desktop/KendoAI/Web_App/app.py
import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
from scipy.stats import skew, kurtosis
import numpy as np
import joblib
import time

from SecretsManager import get_secret

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
REFRESH_INTERVAL = 0.5  # Time interval for updates
# Install dependencies before running (streamlit, pandas, influxdb-client, json, boto3)
# streamlit run c:/Users/beam_/OneDrive/Desktop/KendoAI/Web_App/app.py
import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
from scipy.stats import skew, kurtosis
import numpy as np
import joblib
import time

from SecretsManager import get_secret

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
REFRESH_INTERVAL = 0.5  # Time interval for updates

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

# Initialize last updated values for metrics in session state
metrics_defaults = {
    "last_avg_accel": 0.00,
    "last_mic_status": "N/A",
    "last_jerk": 0.00,
    "last_temp": "N/A",
    "last_humidity": "N/A",
    "last_smoothness": 0.00,
    "last_prediction": "None",
}

for key, default in metrics_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Define feature extraction
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

# Define movement smoothness calculation
def calculate_smoothness(data, smooth_threshold=0.5):
    data['accel_magnitude'] = np.sqrt(data['accelX']**2 + data['accelY']**2 + data['accelZ']**2)
    data['jerk'] = data['accel_magnitude'].diff().fillna(0) / data.index.to_series().diff().dt.total_seconds().fillna(1)
    smooth_movements = data['jerk'].abs() < smooth_threshold
    return smooth_movements.mean() * 100 if not data.empty else 0

# Fetch environment data
def fetch_environment_data():
    query = f'''
    from(bucket: "environment_data")
      |> range(start: -1m)
      |> filter(fn: (r) => r["_measurement"] == "sensor_data")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 1)
    '''
    try:
        tables = query_api.query(query)
        if tables:
            records = [record.values for table in tables for record in table.records]
            if records:
                return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error fetching environment data from InfluxDB: {e}")
    return pd.DataFrame()

# Start/Stop Button
if st.button("Start/Stop Data Fetching"):
    st.session_state.is_running = not st.session_state.is_running

status = "Running" if st.session_state.is_running else "Stopped"
st.write(f"Status: **{status}**")

# Metrics Section
col1, col2, col3, col4 = st.columns(4)
avg_accel_metric = col1.metric("Avg Acceleration (m/s²)", f"{st.session_state.last_avg_accel:.2f}")
mic_metric = col1.metric("Mic Status", st.session_state.last_mic_status)
jerk_metric = col2.metric("Avg Jerk (m/s³)", f"{st.session_state.last_jerk:.2f}")
temp_metric = col2.metric("Temperature (°C)", st.session_state.last_temp)
smoothness_metric = col3.metric("Smooth Movements (%)", f"{st.session_state.last_smoothness:.2f}")
hum_metric = col3.metric("Humidity (%)", st.session_state.last_humidity)
prediction_metric = col4.metric("Prediction", st.session_state.last_prediction)

# Chart Placeholders
st.header("Accelerometer Data:")
accel_chart = st.line_chart(st.session_state.accel_data)

st.header("Gyroscope Data:")
gyro_chart = st.line_chart(st.session_state.gyro_data)

while st.session_state.is_running:
    # Fetch environmental data
    environment_data = fetch_environment_data()
    if not environment_data.empty:
        latest = environment_data.iloc[0]
        mic_status = "High" if latest.get("mic", None) == 1 else "Low"
        st.session_state.last_mic_status = mic_status
        st.session_state.last_temp = latest.get("temperature", "N/A")
        st.session_state.last_humidity = latest.get("humidity", "N/A")

        mic_metric.metric("Mic Status", st.session_state.last_mic_status)
        temp_metric.metric("Temperature (°C)", st.session_state.last_temp)
        hum_metric.metric("Humidity (%)", st.session_state.last_humidity)

    # Fetch movement data
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -30s)
      |> filter(fn: (r) => r._measurement == "gyro_status")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    data = query_api.query_data_frame(query)
    if not data.empty:
        data["_time"] = pd.to_datetime(data["_time"])
        data.set_index("_time", inplace=True)
        
        st.session_state.accel_data = data[["accelX", "accelY", "accelZ"]]
        st.session_state.gyro_data = data[["gyroX", "gyroY", "gyroZ"]]
        
        # Update Charts
        accel_chart.line_chart(st.session_state.accel_data)
        gyro_chart.line_chart(st.session_state.gyro_data)

        # Calculate and update metrics
        if len(data) >= window_size:
            # Average Acceleration
            avg_accel = st.session_state.accel_data.mean().mean()
            st.session_state.last_avg_accel = avg_accel

            # Jerk Calculation
            data['accel_magnitude'] = np.sqrt(data['accelX']**2 + data['accelY']**2 + data['accelZ']**2)
            data['jerk'] = data['accel_magnitude'].diff().fillna(0) / data.index.to_series().diff().dt.total_seconds().fillna(1)
            avg_jerk = data['jerk'].mean()
            st.session_state.last_jerk = avg_jerk

            # Smoothness
            smoothness = calculate_smoothness(data)
            st.session_state.last_smoothness = smoothness

            # Prediction
            latest_window = data.iloc[-window_size:]
            features_df = extract_features(latest_window)
            prediction = model.predict(scaler.transform(features_df))[0]
            st.session_state.last_prediction = le.inverse_transform([prediction])[0]

            # Update metrics on the dashboard
            avg_accel_metric.metric("Avg Acceleration (m/s²)", f"{st.session_state.last_avg_accel:.2f}")
            jerk_metric.metric("Avg Jerk (m/s³)", f"{st.session_state.last_jerk:.2f}")
            smoothness_metric.metric("Smooth Movements (%)", f"{st.session_state.last_smoothness:.2f}")
            prediction_metric.metric("Prediction", st.session_state.last_prediction)

    time.sleep(REFRESH_INTERVAL)

# Live Video Feed
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
