# Install dependencies before running (streamlit, influxdb-client)
# streamlit run environment_dashboard.py
import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
from datetime import datetime
import time

from SecretsManager import get_secret

# InfluxDB configurations
secret_data = get_secret('kendo-line-bot-secret')

INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "environment_data"

# Streamlit page configuration
st.set_page_config(page_title="Environment Dashboard", page_icon="🌍")

# Title
st.title("Environment Dashboard")
st.write("Real-time monitoring of environment data.")

# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)

def fetch_latest_data():
    """
    Fetch the latest environment data from InfluxDB.
    """
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
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
        st.error(f"Error fetching data from InfluxDB: {e}")
    return pd.DataFrame()

# Metrics Section
col1, col2, col3 = st.columns(3)

# Main Loop
if "is_running" not in st.session_state:
    st.session_state.is_running = True

if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

if st.button("Start/Stop"):
    st.session_state.is_running = not st.session_state.is_running

status = "Running" if st.session_state.is_running else "Stopped"
st.write(f"Status: **{status}**")

while st.session_state.is_running:
    data = fetch_latest_data()

    if not data.empty:
        # Parse the latest data
        latest_data = data.iloc[0]
        mic = latest_data.get("mic", None)
        mic_status = "High" if mic == 1 else "Low" if mic == 0 else "N/A"
        temperature = latest_data.get("temperature", "N/A")
        humidity = latest_data.get("humidity", "N/A")
        timestamp = latest_data.get("_time", datetime.now())

        # Update metrics
        with col1:
            st.metric(label="Mic Status", value=mic_status)
        with col2:
            st.metric(label="Temperature (°C)", value=f"{temperature}")
        with col3:
            st.metric(label="Humidity (%)", value=f"{humidity}")

        # Display last update time
        st.session_state.last_updated = timestamp
    else:
        st.warning("No data available.")
        st.session_state.last_updated = datetime.now()

    # Display last updated time
    st.write(f"Last updated: {st.session_state.last_updated}")

    # Refresh interval
    time.sleep(1)
