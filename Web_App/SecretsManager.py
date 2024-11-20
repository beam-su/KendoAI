import json
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    client = boto3.client("secretsmanager", region_name="eu-west-2")
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        # Check if 'SecretString' is in the response
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            raise Exception(f"SecretString not found in the response for {secret_name}")
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            raise Exception(f"Secret '{secret_name}' not found.")
        else:
            raise Exception(f"Could not retrieve secret: {str(e)}")
    except Exception as e:
        raise Exception(f"An unknown error occurred: {str(e)}")