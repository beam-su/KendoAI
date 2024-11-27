import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from influxdb_client import InfluxDBClient
from SecretsManager import get_secret
import time

# InfluxDB connection details
secret_data = get_secret('kendo-line-bot-secret')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "SIOT_Test"

# Function to fetch data from InfluxDB
def fetch_data_from_influxdb():
    """Fetch data from InfluxDB."""
    with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -3m)
          |> filter(fn: (r) => r["_measurement"] == "gyro_status")
          |> filter(fn: (r) => r["_field"] == "accelX" or 
                               r["_field"] == "accelY" or 
                               r["_field"] == "accelZ")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        tables = client.query_api().query(query, org=INFLUXDB_ORG)
        # Convert to Pandas DataFrame
        data = []
        for table in tables:
            for record in table.records:
                data.append(record.values)
        df = pd.DataFrame(data)
        # Rename and clean up columns
        df.rename(columns={"_time": "timestamp"}, inplace=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])  # Ensure timestamp is datetime
        return df

# Analyze smoothness
def analyze_smoothness(data, smooth_threshold=0.5):
    """Analyze the smoothness of the movement."""
    # Calculate acceleration magnitude
    data['accel_magnitude'] = np.sqrt(data['accelX']**2 + data['accelY']**2 + data['accelZ']**2)
    
    # Calculate jerk (rate of change of acceleration)
    data['jerk'] = data['accel_magnitude'].diff() / data['timestamp'].diff().dt.total_seconds()
    
    # Classify smoothness
    data['is_smooth'] = data['jerk'].abs() < smooth_threshold
    
    return data

# Streamlit configuration
st.set_page_config(page_title="Smoothness Analysis", page_icon="📈")
st.title("Smoothness Analysis for Kendo Movements")

# Initialize session state for data fetching
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Start/Stop Button
if st.button("Start/Stop Analysis"):
    st.session_state.is_running = not st.session_state.is_running

# Display current status
status = "Running" if st.session_state.is_running else "Stopped"
st.write(f"Status: **{status}**")

# Metrics
col1, col2 = st.columns(2)
with col1:
    avg_accel_metric = st.metric("Avg Acceleration (m/s²)", "0.00")
with col2:
    smoothness_metric = st.metric("Smooth Movements (%)", "0.00%")

# Plot placeholder
plot_placeholder = st.empty()

# Main loop
while st.session_state.is_running:
    # Fetch data
    data = fetch_data_from_influxdb()
    
    # Analyze smoothness
    smoothness_df = analyze_smoothness(data)
    
    # Update metrics
    avg_accel = smoothness_df['accel_magnitude'].mean()
    smooth_percentage = smoothness_df['is_smooth'].mean() * 100
    
    avg_accel_metric.metric("Avg Acceleration (m/s²)", f"{avg_accel:.2f}")
    smoothness_metric.metric("Smooth Movements (%)", f"{smooth_percentage:.2f}%")
    
    # Plot results
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(smoothness_df['timestamp'], smoothness_df['accel_magnitude'], label='Acceleration Magnitude')
    ax.scatter(smoothness_df['timestamp'], smoothness_df['is_smooth'], color='red', label='Smoothness', alpha=0.6)
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Acceleration Magnitude')
    ax.set_title('Smoothness Analysis')
    ax.legend()
    ax.grid()
    plot_placeholder.pyplot(fig)
    
    # Refresh interval
    time.sleep(0.5)
