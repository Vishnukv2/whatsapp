import logging
import json
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import hashlib
import hmac
import aiohttp
import asyncio
import subprocess
import time
import os
import ngrok
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pyodbc
db_connection_string = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=103.239.89.99,21433;"
    "Database=HospinsApp_DB_AE;"
    "UID=AE_Hospins_usr;"
    "PWD=7LNw37*Qm;"
)
db_string = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=103.239.89.99,21433;"
    "Database=PMO360_DB;"
    "UID=PMOlogbook_Usr;"
    "PWD=aPMO86#iaxh;"
)
app = Flask(__name__)
load_dotenv()
CORS(app, resources={"/*": {"origins": "*"}})
ACCESS_TOKEN = os.getenv("access_token")
PHONE_NUMBER_ID_1 = os.getenv("phone_number_id_1")
PHONE_NUMBER_ID_2 = os.getenv("phone_number_id_2")
ng=os.getenv("authtoken")
VERSION = "v19.0"
# Send a custom text WhatsApp message asynchronously
async def send_message(recipient, data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID_1}/messages"
        try:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    return {"status": response.status, "response": html}
                else:
                    return {"status": response.status, "response": str(response)}
        except aiohttp.ClientConnectorError as e:
            return {"status": 500, "response": str(e)}

session_ids = {}
def generate_session_id(phone_number):
    url = "https://testapi.unomiru.com/api/Waysbot/generate_sessionid"
    response = requests.request("GET", url)
    if response.status_code == 200:
        session_id=response.text 
        return session_id
    else:
        return None

@app.route("/send-message", methods=["POST"])
def send_whatsapp_message():
    try:
        content = request.get_json()
        recipient = content.get("recipient")
        attachment_id = content.get("attachment_id")  # Assuming attachment ID is provided in the request
        
        if recipient and attachment_id:
            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": "intel",
                    "language": {
                        "code": "en"
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {
                                        "id": attachment_id
                                    }
                                }
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": "https://www.waysaheadglobal.com/index.html"
                                }
                            ]
                        }
                    ]
                }
            }

            data_json = json.dumps(data)  # Convert the dictionary to a JSON string
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(send_message(recipient, data_json))
            loop.close()
            return jsonify(result)
        else:
            return jsonify({"error": "Recipient and attachment_id are required"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/send-custom-message", methods=["POST"])
def send_custom_whatsapp_message():
    try:
        content = request.get_json()
        recipient = content.get("recipient")
        text = content.get("text")

        if recipient and text:
            data = json.dumps({
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            })
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(send_message(recipient, data))
            loop.close()

            return jsonify(result)
        else:
            return jsonify({"error": "Recipient and text are required"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_db_connection():
    try:
        connection = pyodbc.connect(db_string)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None
        
@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()

        # SQL query to fetch records from dbo.Wayschat_hist table
        cursor.execute("""
            SELECT phone_number
            FROM dbo.Wayschat_hist
            WHERE phone_number IS NOT NULL
            ORDER BY phone_number, Date DESC
        """)
        rows = cursor.fetchall()

        # Group by phone_number and extract unique phone numbers
        phone_numbers = set(row.phone_number for row in rows)

        total_phone_numbers = len(phone_numbers)
        phone_numbers_json = json.dumps(list(phone_numbers))

        return jsonify({
            "phoneNumbersJson": phone_numbers_json,
            "totalPhoneNumbers": total_phone_numbers
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/fetchMessages', methods=['GET'])
def fetch_messages():
    phone_number = request.args.get('phone_number')

    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400
    conn = get_db_connection()
    try:
        
        if conn is None:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT User_input, Bot_response, response_time, Date, session_id
            FROM dbo.Wayschat_hist
            WHERE phone_number = ?
            ORDER BY Date
        """, (phone_number,))
        
        rows = cursor.fetchall()
        messages = [
            {
                "User_input": row.User_input,
                "Bot_response": row.Bot_response,
                "response_time": row.response_time,
                "Date": row.Date.strftime('%Y-%m-%d %H:%M:%S'),
                "session_id": row.session_id
            }
            for row in rows
        ]
        return jsonify(messages)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()
            
@app.route('/save_response', methods=['POST'])
def send_message_user():
    data = request.get_json()
    if not data or 'text' not in data or 'recipient' not in data:
        return jsonify({'error': 'Invalid input'}), 400
    
    text = data['text']
    recipient = data['recipient']
    
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Wayschat_hist ( Bot_response, phone_number, Date)
            VALUES (?, ?, ?)
        """, (text, recipient, datetime.now()))
        
        conn.commit()
        return jsonify({'message': 'Message sent'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal Server Error', 'details': str(e)}), 500


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    })

def generate_response(sender_number, response):
    headers = {
        'session-id': session_ids.get(sender_number),
        'Content-Type': 'application/json'
    }
    data = {'user_input': response}
    api_response = requests.post('https://testapi.unomiru.com/api/Waysbot/chat', headers=headers, data=json.dumps(data))
    if api_response.status_code == 200:
        response_json = api_response.json()  # Parse the JSON response
        c_response = response_json.get('response')
        return c_response
    else:
        logging.error(f"Error calling API. Status code: {api_response.status_code}, Error response: {api_response.text}")
        return None


def send_messages(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID_2}/messages"

    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        log_http_response(response)
        return response

def process_text_for_whatsapp(text):
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()

    pattern = r"\\(.?)\\*"
    replacement = r"\1"
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

def check_guest_in_db(sender_number):
    try:
        logging.info(f"Checking guest with mobile number: {sender_number}")

        connection = pyodbc.connect(db_connection_string)
        cursor = connection.cursor()

        query = "SELECT COUNT(*) FROM tbPMS_Guest WHERE GuestMobile = ?"
        cursor.execute(query, (sender_number,))
        result = cursor.fetchone()

        if result[0] > 0:
            update_query = "UPDATE tbPMS_Guest SET isconnected = 1 , Flag = 0  WHERE GuestMobile = ?"
            cursor.execute(update_query, (sender_number,))
            connection.commit()
            logging.info(f"Guest with mobile number: {sender_number} is connected.")
        else:
            logging.info(f"Guest with mobile number: {sender_number} not found.")
        connection.close()
    except Exception as e:
        logging.error(f"Error checking guest in DB: {e}")
        raise e
        
@app.route("/check-guest", methods=["POST"])
def check_guest():
    try:
        content = request.get_json()
        sender_number = content.get("sender_number")

        if not sender_number:
            return jsonify({"error": "Sender number is required"}), 400

        check_guest_in_db(sender_number)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error in /check-guest endpoint: {e}")
        return jsonify({"error": str(e)}), 500

def insert_chat_history(user_input, bot_response, session_id, phone_number):
    try:
        current_datetime = datetime.utcnow()
        formatted_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        connection = pyodbc.connect(db_string)
        cursor = connection.cursor()
        insert_query = """
            INSERT INTO Wayschat_hist (User_input, Bot_response, Date, session_id, phone_number)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (user_input, bot_response, formatted_date, session_id, phone_number))
        connection.commit()
        connection.close()
    except Exception as e:
        logging.error(f"Error inserting chat history into DB: {e}")
        raise e

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]
    sender_number = message["from"]
    if sender_number not in session_ids:
        session_id = generate_session_id(sender_number)
        if session_id:
            session_ids[sender_number] = session_id
    check_guest_in_db(sender_number)
    response = generate_response(sender_number, message_body)
    data = get_text_message_input(sender_number, response)
    send_messages(data)
    insert_chat_history(message_body, response, session_ids[sender_number], sender_number)

def is_valid_whatsapp_message(body):
    return (body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0])

# Security

def validate_signature(payload, signature):
    expected_signature = hmac.new(
        bytes("172b45d7233fa576bfed08cf742b5259", "latin-1"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

def signature_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get("X-Hub-Signature-256", "")[7:]
        if not validate_signature(request.data.decode("utf-8"), signature):
            logging.info("Signature verification failed!")
            return jsonify({"status": "error", "message": "Invalid signature"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Views

@app.route("/webhook", methods=["GET"])
def webhook_get():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == "12345":
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

@app.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    body = request.get_json()
    if (body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")):
        logging.info("Received a WhatsApp status update.")
        return jsonify({"status": "ok"}), 200
    try:
        if is_valid_whatsapp_message(body):
            process_whatsapp_message(body)
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error", "message": "Not a WhatsApp API event"}), 404
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400

import subprocess
import threading
def run_ngrok():
    try:
        subprocess.run(["ngrok", "http", "--domain=intent-sharply-kodiak.ngrok-free.app", "8000"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        # Handle the error, if needed
        pass

if __name__ == "__main__":
    # Start ngrok in a separate thread
    ngrok_thread = threading.Thread(target=run_ngrok)
    ngrok_thread.start()

    # Start Flask app
    app.run(port=8000, debug=False)
