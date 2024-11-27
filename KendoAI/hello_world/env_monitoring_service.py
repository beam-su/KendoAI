import time
import json
import boto3
import pandas as pd
from influxdb_client import InfluxDBClient
from SecretsManager import get_secret

# Fetch Secrets
secrets = get_secret('kendo-line-bot-secret')
influxdb_token = secrets.get('InfluxDB_Token')
influxdb_org = secrets.get('InfluxDB_organisation')
account_id = secrets.get('aws_id')

# InfluxDB Configuration
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_BUCKET = "environment_data"

# AWS SNS Configuration
sns_client = boto3.client('sns', region_name='eu-west-2')
SNS_TOPIC_ARN = f"arn:aws:sns:eu-west-2:{account_id}:NoiseAlertTopic"

# Initialize InfluxDB Client
client = InfluxDBClient(url=INFLUXDB_URL, token=influxdb_token, org=influxdb_org)
query_api = client.query_api()

def check_environment_noise():
    """
    Check the InfluxDB bucket for the last 10 mic readings and determine if the average is greater than 0.2.
    """
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1m)
        |> filter(fn: (r) => r._measurement == "sensor_data" and r._field == "mic")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: 10)
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    try:
        df = query_api.query_data_frame(org=influxdb_org, query=query)
        
        if not df.empty:
            # Convert mic values to numeric
            df['mic'] = pd.to_numeric(df['mic'], errors='coerce')
            
            # Calculate the average
            mic_average = df['mic'].mean()
            print(f"Average mic value: {mic_average}")

            if mic_average > 0.2:
                print("Environment is too loud! Publishing to SNS...")
                sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=json.dumps({"message": "Environment too loud", "average_mic": mic_average}),
                    Subject="Noise Alert"
                )
        else:
            print("No data retrieved for mic.")
    except Exception as e:
        print(f"Error querying InfluxDB: {e}")

def main():
    while True:
        check_environment_noise()
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    main()
