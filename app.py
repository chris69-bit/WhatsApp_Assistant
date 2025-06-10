from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pickle

app = Flask(__name__)

# Load the assistant model
with open('whatsapp_assitant-3.0.pkl', 'rb') as f:
    assistant = pickle.load(f)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Get incoming message from WhatsApp
    incoming_msg = request.values.get('Body', '').lower()
    
    # Get sender's number
    sender = request.values.get('From', '')
    
    # Process the message with the assistant
    try:
        response_text = assistant.assistant_response(incoming_msg)
    except Exception as e:
        response_text = f"Sorry, I encountered an error: {str(e)}"
    
    # Create Twilio response
    resp = MessagingResponse()
    resp.message(response_text)
    
    return str(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)