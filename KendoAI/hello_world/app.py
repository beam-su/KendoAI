import json
import os
import requests
import boto3

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImagemapSendMessage

from SecretsManager import get_secret

#####################################
secrets = get_secret('kendo-line-bot-secret')
access_token = secrets.get('Channel_Access_Token')
channel_secret = secrets.get('Channel_Secret')
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)
######################################
def update_displayName(user_id): #Find the name of the user
    headers = {
        "Authorization": f'Bearer {access_token}'
    }
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_profile = response.json()
        display_name = user_profile.get("displayName", "Display Name Not Found")
        print("User Display Name:", display_name)
        return display_name
    else:
        print("Error retrieving user profile:", response.status_code)
        print(response.text)

def update_user_role(user_id, new_role):
    try:
        response = dynamodb.update_item(
            TableName = 'KendoAIUser',
            Key={'line_id':{'S':user_id}},
            UpdateExpression='SET #r = :new_role',
            ExpressionAttributeNames={'#r':'role'},
            ExpressionAttributeValues={':new_role': {'S':new_role}},
            ReturnValues="UPDATED_NEW"
        )
        return response

    except Exception as e:
        print(f"Error updating role for user {user_id}:{str(e)}")
        return None

def push_message(message):
    # LINE API endpoint
        LINE_API_URL = 'https://api.line.me/v2/bot/message/push'

        # Prepare the HTTP headers with the authorization token
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
        }

        # Prepare the message payload
        data = {
            'to': line_id,
            'messages': [
                {
                    'type': 'text',
                    'text': message,
                }
            ],
        }

        # Send the push message request
        response = requests.post(LINE_API_URL, json=data, headers=headers)

        # Check the response
        if response.status_code == 200:
            print('Unauthorized user message sent successfully.')
        else:
            print(f'Failed to send unauthorized user message. Status code: {response.status_code}')
            print(response.text)

def load_json(json_file):
    try:
        with open(json_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("JSON File not found")
        return None

def send_imagemap_message(json_file,user_id, reply_token):
    imagemap_message = load_json(json_file)
    if imagemap_message:
        # Use the ImagemapSendMessage class to send the imagemap
        message = ImagemapSendMessage(
            base_url=imagemap_message["baseUrl"],
            alt_text=imagemap_message["altText"],
            base_size=imagemap_message["baseSize"],
            actions=imagemap_message["actions"]
        )
        line_bot_api.reply_message(reply_token, message)
    else:
        print("Error loading imagemap message.")

def message_listener(user_id, user_message, reply_token):
    if user_message == "Armour Registeration":
        push_message("Begin Armour Registeration")

    if user_message == "Role Change":
        json_file_path = os.path.join("richobject", "rolemenu.json")
        send_imagemap_message(json_file_path, user_id, reply_token)
        #update_user_role(user_id, new_role)

######################################

def lambda_handler(event, context):
    # Check if the 'body' field exists in the event
    if 'body' not in event:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Missing 'body' in event"})
        }

    # Load the body as JSON
    msg = json.loads(event['body'])

    # Ensure there are events in the message
    if 'events' not in msg or len(msg['events']) == 0:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "No events in request body"})
        }

    # Declare Variables for DynamoDB
    dynamodb = boto3.client('dynamodb')
    global line_id
    line_id = msg['events'][0]['source']['userId']
    display_name = update_displayName(line_id)
    user_message = msg['events'][0]['message']['text']
    reply_token = msg['events'][0]['replyToken']

    # Check if user is registered
    try:
        #Query
        response = dynamodb.query(
            TableName="KendoAIUser",
            KeyConditionExpression="line_id = :line_id",
            ExpressionAttributeValues = {
                ":line_id": {"S":line_id}
            }
        )

        if "Items" not in response or len(response["Items"]) == 0:
            #New User Registration
            dynamodb.put_item(
                TableName="KendoAIUser",
                Item={
                    "line_id": {"S": line_id},
                    "role": {"S":"solo"},
                    "display_name":{"S": display_name}
                    }
            )

    except Exception as e:
        print("Error interacting with DynamoDB:", str(e))

    message_listener(line_id, user_message, reply_token)

    # # Mirror the user's message back (Use this to check if the bot is working)
    # line_bot_api.reply_message(
    #     msg['events'][0]['replyToken'],
    #     TextSendMessage(text=msg['events'][0]['message']['text'])
    # )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": 'ok'})
    }
