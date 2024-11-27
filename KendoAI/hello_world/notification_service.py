import json
import requests
import boto3
from linebot import LineBotApi
from SecretsManager import get_secret

# Fetch Secrets
secrets = get_secret('kendo-line-bot-secret')
access_token = secrets.get('Channel_Access_Token')
line_bot_api = LineBotApi(access_token)

def push_message(user_id, message):
    """
    Send a message to the user via LINE.
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
    }

    data = {
        'to': user_id,
        'messages': [
            {
                'type': 'text',
                'text': message,
            }
        ],
    }

    response = requests.post('https://api.line.me/v2/bot/message/push', json=data, headers=headers)

    if response.status_code == 200:
        print('Notification sent successfully.')
    else:
        print(f'Failed to send notification. Status code: {response.status_code}')
        print(response.text)

def lambda_handler(event, context):
    """
    AWS Lambda handler to process SNS messages.
    """
    for record in event['Records']:
        sns_message = json.loads(record['Sns']['Message'])
        mic_average = sns_message.get("average_mic", 0)
        print(f"Received noise alert with average mic value: {mic_average}")

        # Send a LINE notification
        # Replace "USER_ID" with the target user's LINE ID
        push_message("Ue452e730b401252d5f2246cc57ea6366", f"Noise Alert!")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Notifications sent successfully."})
    }
