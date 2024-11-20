# Install dependencies before running (streamlit, pandas, influxdb-client, json, boto3)
# streamlit run c:/Users/beam_/OneDrive/Desktop/KendoAI/KendoAI/app.py
#---------------------------------------------#
# Import libraries
import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
import time
import numpy as np

from SecretsManager import get_secret

#---------------------------------------------#
# Declare Variables

# Fetch the secrets from AWS Secrets Manager
secret_data = get_secret('kendo-line-bot-secret')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "SIOT_Test"

# Refresh Interval (sec)
REFRESH_INTERVAL = 1

# Initialize InfluxDB Client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

#---------------------------------------------#
# Declare Functions

# Query Function
def get_sensor_data():
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -1m)
      |> filter(fn: (r) => r._measurement == "gyro_status")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    '''
    tables = query_api.query_data_frame(org=INFLUXDB_ORG, query=query)
    if not tables.empty:
        return tables
    else:
        return pd.DataFrame()
    
# Calculate Average Acceleration
def calculate_avg_acceleration(data):
    acc_mag = np.sqrt(data["accelX"]**2 + data["accelY"]**2 + data["accelZ"]**2)
    return acc_mag.mean()* 9.80665

# Calculate Jerk
def calculate_jerk(data):
    if len(data) < 2:  # Ensure there are at least two rows
        return 0.0
    
    # Calculate time differences
    time_deltas = (data.index[1:] - data.index[:-1]).total_seconds()
    
    # Ensure time_deltas is a numpy array
    time_deltas = np.array(time_deltas)
    
    # Calculate acceleration differences
    accel_diff = np.diff(data[["accelX", "accelY", "accelZ"]].values* 9.80665, axis=0)
    
    # Calculate jerk magnitude for each time interval
    jerk_magnitudes = np.linalg.norm(accel_diff, axis=1) / time_deltas
    return np.mean(jerk_magnitudes)

def calculate_speed(data):
    if len(data) < 2:  # Ensure there are at least two rows
        return 0.0
    
    # Calculate time differences
    time_deltas = (data.index[1:] - data.index[:-1]).total_seconds()
    time_deltas = np.array(time_deltas)

    # Calculate acceleration magnitudes and convert to m/s²
    acc_magnitudes = np.sqrt(data["accelX"]**2 + data["accelY"]**2 + data["accelZ"]**2) * 9.80665
    acc_deltas = np.diff(acc_magnitudes)

    # Approximate speed changes
    speed_changes = acc_deltas * time_deltas  # Δv = a * Δt
    return abs(np.sum(speed_changes))

#---------------------------------------------#

# Set the title and favicon on the tab
st.set_page_config(
    page_title='KiAI',
    page_icon='🤺',
)

#---------------------------------------------#
# Streamlit Configuration
st.title("KiAI - Kendo Assistant")

# Initialize Session State
if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "accel_data" not in st.session_state:
    st.session_state.accel_data = pd.DataFrame(columns=["accelX", "accelY", "accelZ"])

if "gyro_data" not in st.session_state:
    st.session_state.gyro_data = pd.DataFrame(columns=["gyroX", "gyroY", "gyroZ"])

# Start/Stop Button
if st.button("Start/Stop Data Fetching"):
    st.session_state.is_running = not st.session_state.is_running

# Display current status
status = "Running" if st.session_state.is_running else "Stopped"
st.write(f"Status: **{status}**")

# Insights Section
col1, col2, col3 = st.columns(3)

if "avg_acceleration" not in st.session_state:
    st.session_state.avg_acceleration = 0.0

if "jerk" not in st.session_state:
    st.session_state.jerk = 0.0

if "speed" not in st.session_state:
    st.session_state.speed = 0.0

if "prev_speed" not in st.session_state:
    st.session_state.prev_speed = 0.0

with col1:
    speed_change = st.session_state.speed - st.session_state.prev_speed
    speed_metric = st.metric(
        "Speed (m/s)",
        f"{st.session_state.speed:.2f}",
        delta=f"{speed_change:.2f}",
        delta_color="normal"
    )

with col2:
    avg_accel_metric = st.metric("Average Acceleration (m/s²)", f"{st.session_state.avg_acceleration:.2f}")

with col3:
    jerk_metric = st.metric("Average Jerk (m/s³)", f"{st.session_state.jerk:.2f}")

#---------------------------------------------#
# Graph Plotting

# Line Chart Placeholders
st.header("Accelerometer Data:")
accel_chart = st.line_chart(st.session_state.accel_data)

st.header("Gyroscope Data:")
gyro_chart = st.line_chart(st.session_state.gyro_data)

# Main Loop
while st.session_state.is_running:
    # Fetch Data
    data = get_sensor_data()

    if not data.empty:
        # Prepare Data
        data["_time"] = pd.to_datetime(data["_time"])  # Convert to datetime
        data.set_index("_time", inplace=True)

        # Update Session State with the latest data
        st.session_state.accel_data = data[["accelX", "accelY", "accelZ"]]
        st.session_state.gyro_data = data[["gyroX", "gyroY", "gyroZ"]]

        # Update Metrics
        if len(st.session_state.accel_data) > 1:
            st.session_state.avg_acceleration = calculate_avg_acceleration(st.session_state.accel_data)
            st.session_state.jerk = calculate_jerk(st.session_state.accel_data)

            # Update speed
            st.session_state.prev_speed = st.session_state.speed
            st.session_state.speed = calculate_speed(st.session_state.accel_data)

        # Display metrics
        avg_accel_metric.metric("Average Acceleration (m/s²)", f"{st.session_state.avg_acceleration:.2f}")
        jerk_metric.metric("Average Jerk (m/s³)", f"{st.session_state.jerk:.2f}")
        speed_metric.metric(
            "Speed (m/s)",
            f"{st.session_state.speed:.2f}",
            delta=f"{st.session_state.speed - st.session_state.prev_speed:.2f}",
            delta_color="normal"
        )

        # Update Line Charts
        accel_chart.line_chart(st.session_state.accel_data)
        gyro_chart.line_chart(st.session_state.gyro_data)
    else:
        st.warning("No data available.")

    # Refresh Interval
    time.sleep(REFRESH_INTERVAL)

# When stopped, display the last data fetched
if not st.session_state.is_running:
    avg_accel_metric.metric("Average Acceleration (m/s²)", f"{st.session_state.avg_acceleration:.2f}")
    jerk_metric.metric("Average Jerk (m/s³)", f"{st.session_state.jerk:.2f}")
    speed_metric.metric(
        "Speed (m/s)",
        f"{st.session_state.speed:.2f}",
        delta=f"{st.session_state.speed - st.session_state.prev_speed:.2f}",
        delta_color="normal"
    )
    accel_chart.line_chart(st.session_state.accel_data)
    gyro_chart.line_chart(st.session_state.gyro_data)