import serial
import json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from SecretsManager import get_secret

# InfluxDB configurations
secret_data = get_secret('kendo-line-bot-secret')

INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = secret_data.get('InfluxDB_Token')
INFLUXDB_ORG = secret_data.get('InfluxDB_organisation')
INFLUXDB_BUCKET = "environment_data"

# Serial port configurations
SERIAL_PORT = "COM4"
BAUD_RATE = 9600

def initialize_client():
    """
    Initialize the InfluxDB client with extended timeout and synchronous write options.
    """
    return InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, timeout=300_000)

def write_to_influxdb(write_api, data):
    """
    Write parsed sensor data to InfluxDB and handle errors.
    """
    try:
        point = Point("sensor_data") \
            .field("mic", data["mic"]) \
            .field("temperature", data.get("temperature", None)) \
            .field("humidity", data.get("humidity", None))

        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        print("Data written to InfluxDB:", point)
    except Exception as e:
        print(f"Failed to write to InfluxDB: {e}")

def main():
    """
    Main loop to read from the serial port and write to InfluxDB.
    """
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("Connected to serial port:", SERIAL_PORT)

        client = initialize_client()
        write_api = client.write_api(write_options=SYNCHRONOUS)

        while True:
            try:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    print("Raw data:", line)

                    # Parse the JSON data
                    try:
                        data = json.loads(line)
                        print("Parsed data:", data)

                        if "error" in data:
                            print("Sensor error:", data["error"])
                            continue

                        # Write data to InfluxDB
                        write_to_influxdb(write_api, data)

                    except json.JSONDecodeError:
                        print("Failed to parse JSON:", line)

            except serial.SerialException as e:
                print(f"Serial port error: {e}")
                print("Attempting to reconnect...")
                ser.close()
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

    except KeyboardInterrupt:
        print("Stopping script.")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        try:
            ser.close()
            print("Serial port closed.")
        except Exception:
            pass
        try:
            client.close()
            print("Disconnected from InfluxDB.")
        except Exception:
            pass

if __name__ == "__main__":
    main()
