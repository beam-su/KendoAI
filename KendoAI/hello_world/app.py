import json
import os
import requests

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from secrets_manager import get_secret

#####################################

secrets = get_secret(os.getenv('kendo-line-bot-secret'))
line_bot_api = LineBotApi(os.getenv('Channel_Access_Token'))
handler = WebhookHandler(os.getenv('Channel_Secret'))


def lambda_handler(event, context):
    signature = event['headers']['X-Line-Signature']
    
    body = event['body']
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': 'Invalid signature'
        }

    return {
        'statusCode': 200,
        'body': json.dumps('OK')
    }

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text)
    )