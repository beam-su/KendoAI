import json
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    client = boto3.client("secretsmanager")
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    except ClientError as e:
        raise Exception(f"Could not retrive secret: {str(e)}")