import json
import requests
from SecretsManager import get_secret

secrets = get_secret('kendo-line-bot-secret')
access_token = secrets.get('Channel_Access_Token')\

####################################
# Change the json file depending on what we're deploying
with open('rolemenu.json', 'r') as file:
    deployment_data = json.load(file)

#Channel Access Token
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

response = requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=deployment_data)

# Response Check
if response.status_code == 200:
    print("Richobject deployed successfully")

else:
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)

###