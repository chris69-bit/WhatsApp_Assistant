# app.py
from assistant import assistant_response
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os

app = Flask(__name__)

# Initialize Google services
def initialize_services():
    creds = get_credentials()
    
    calendar_service = build('calendar', 'v3', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # Get API keys
    api_key = os.getenv('GOOGLE_API_KEY')
    news_api_key = os.getenv('NEWS_API_KEY')
    
    return {
        'calendar': calendar_service,
        'gmail': gmail_service,
        'google_api_key': api_key,
        'news_api_key': news_api_key
    }

def get_credentials():
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/gmail.readonly'
    ]
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

# Initialize services at startup
services = initialize_services()

# WhatsApp webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    user_message = data.get('message', '')
    
    # Get assistant response
    assistant_reply = assistant_response(user_message, services)
    
    return jsonify({
        'reply': assistant_reply,
        'status': 'success'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)