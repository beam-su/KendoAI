#streamlit run c:/Users/beam_/OneDrive/Desktop/KendoAI/Web_App/move_analysis.py
from influxdb_client import InfluxDBClient
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from SecretsManager import get_secret

# InfluxDB connection details
secret_data = get_secret('kendo-line-bot-secret')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "SIOT_Test"

# Query parameters
variables = ['accelX', 'accelY', 'accelZ', 'timestamp']


def fetch_data_from_influxdb():
    """Fetch data from InfluxDB."""
    with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -10m)
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


def analyze_smoothness(data, smooth_threshold=0.5):
    """Analyze the smoothness of the movement."""
    # Calculate acceleration magnitude
    data['accel_magnitude'] = np.sqrt(data['accelX']**2 + data['accelY']**2 + data['accelZ']**2)
    
    # Calculate jerk (rate of change of acceleration)
    data['jerk'] = data['accel_magnitude'].diff() / data['timestamp'].diff().dt.total_seconds()
    
    # Classify smoothness
    data['is_smooth'] = data['jerk'].abs() < smooth_threshold
    
    return data


def plot_results(data):
    """Plot the acceleration magnitude and smoothness classification."""
    plt.figure(figsize=(10, 6))
    plt.plot(data['timestamp'], data['accel_magnitude'], label='Acceleration Magnitude')
    plt.scatter(data['timestamp'], data['is_smooth'], color='red', label='Smoothness', alpha=0.6)
    plt.xlabel('Timestamp')
    plt.ylabel('Acceleration Magnitude')
    plt.title('Smoothness Analysis')
    plt.legend()
    plt.grid()
    plt.show()


if __name__ == "__main__":
    # Step 1: Fetch data from InfluxDB
    df = fetch_data_from_influxdb()
    
    # Step 2: Analyze smoothness
    smoothness_df = analyze_smoothness(df)
    
    # Step 3: Plot results
    plot_results(smoothness_df)
    
    # Optional: Print results for inspection
    print(smoothness_df[['timestamp', 'accel_magnitude', 'jerk', 'is_smooth']])
