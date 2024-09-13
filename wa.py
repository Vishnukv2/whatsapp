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
VERSION = "v20.0"
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
        
@app.route("/api/dashboard", methods=["GET"])
def get_unique_phone_numbers():
    try:
        with pyodbc.connect(db_string) as conn:
            cursor = conn.cursor()
            query = """
                SELECT c.PhoneNumber AS phone_number, 
                       ISNULL(c.Name, c.PhoneNumber) AS display_name,
                       MAX(ch.[Date]) AS last_conversation_date,
                       (SELECT TOP 1 Bot_response
                        FROM tbWhatsAppChat
                        WHERE tbWhatsAppChat.ClientID = c.ClientID
                        AND tbWhatsAppChat.Bot_response IS NOT NULL
                        ORDER BY [Date] DESC) AS last_bot_response
                FROM tbWhatsAppClients c
                LEFT JOIN tbWhatsAppChat ch ON c.ClientID = ch.ClientID
                GROUP BY c.PhoneNumber, c.Name, c.ClientID
            """
            cursor.execute(query)
            users = cursor.fetchall()

            phone_numbers_json = []
            last_conversation_dates = {}

            for user in users:
                # Store the last conversation date in dd-mm format (without the year)
                last_conversation_dates[user.phone_number] = user.last_conversation_date.strftime("%d-%m") if user.last_conversation_date else None
                
                user_info = {
                    "phone_number": user.phone_number,
                    "last_bot_response": user.last_bot_response
                }
                
                # Include name only if it's not null
                if user.display_name != user.phone_number:
                    user_info["name"] = user.display_name
                
                phone_numbers_json.append(user_info)
            
            # Sort the phone numbers by last conversation date (latest first)
            sorted_phone_numbers_json = sorted(phone_numbers_json, key=lambda x: last_conversation_dates.get(x['phone_number'], ""), reverse=True)

        return jsonify({
            "lastConversationDates": dict(sorted(last_conversation_dates.items(), key=lambda item: item[1], reverse=True)),
            "phoneNumbersJson": sorted_phone_numbers_json,
            "totalPhoneNumbers": len(phone_numbers_json)
        }), 200
    except pyodbc.Error as e:
        logging.error(f"Failed to retrieve unique phone numbers: {e}")
        return jsonify({"error": "Failed to retrieve data"}), 500

@app.route("/api/fetch_chat", methods=["POST"])
def fetch_chat_by_phone_number():
    try:
        content = request.get_json()
        phone_number = content.get("phone_number")

        if phone_number:
            with pyodbc.connect(db_string) as conn:
                cursor = conn.cursor()

                # Get the ClientID from the tbWhatsAppClients table using the provided phone number
                client_query = "SELECT ClientID FROM tbWhatsAppClients WHERE PhoneNumber = ?"
                cursor.execute(client_query, phone_number)
                client = cursor.fetchone()

                if client is None:
                    return jsonify({"error": "Phone number not found"}), 404

                client_id = client.ClientID

                # Fetch the chat messages for the provided phone number using the ClientID, ordered by date ASC
                message_query = """
                    SELECT User_input, Bot_response, [Date], IsAdminMessage
                    FROM tbWhatsAppChat
                    WHERE ClientID = ?
                    ORDER BY [Date] ASC
                """
                cursor.execute(message_query, client_id)

                # Group chats by date
                chats_by_date = {}
                for row in cursor.fetchall():
                    timestamp = row.Date
                    date = timestamp.strftime("%d-%m-%Y")  # Group by date (e.g., "03-09-2024")
                    time = timestamp.strftime("%I:%M %p")  # Time format (e.g., "9:15 AM")

                    # Prepare message format based on whether it's an admin message
                    message = {
                        "time": time,
                        "bot_response": row.Bot_response
                    }
                    
                    if not row.IsAdminMessage:
                        message["user_input"] = row.User_input

                    # Append the message to the correct date group
                    if date not in chats_by_date:
                        chats_by_date[date] = []

                    chats_by_date[date].append(message)

                # Formatting the output to have "actual_date" directly associated with chats
                simplified_response = []
                for date, messages in chats_by_date.items():
                    simplified_response.append({
                        "actual_date": date,
                        "chats": messages
                    })

            return jsonify({"dates": simplified_response}), 200
        else:
            return jsonify({"error": "Phone number is required"}), 400
    except pyodbc.Error as e:
        logging.error(f"Failed to fetch chats: {e}")
        return jsonify({"error": "Failed to retrieve data"}), 500


            
@app.route("/api/save_response", methods=["POST"])
def save_response():
    try:
        content = request.get_json()
        phone_number = content.get("phone_number")
        bot_response = content.get("bot_response")

        if phone_number and bot_response:
            with pyodbc.connect(db_string) as conn:
                cursor = conn.cursor()

                # Get ClientID based on phone_number if needed
                client_query = "SELECT ClientID FROM tbWhatsAppClients WHERE PhoneNumber = ?"
                cursor.execute(client_query, phone_number)
                client = cursor.fetchone()

                if client:
                    client_id = client.ClientID
                else:
                    return jsonify({"error": "Phone number not found"}), 404

                # Insert the message with IsAdminMessage flag set to 1
                insert_query = """
                    INSERT INTO tbWhatsAppChat (ClientID, User_input, Bot_response, [Date], IsAdminMessage)
                    VALUES (?, 'ADMIN', ?, GETDATE(), 1)
                """
                cursor.execute(insert_query, client_id, bot_response)
                conn.commit()

            return jsonify({"status": "success", "message": "Response saved successfully"}), 200
        else:
            return jsonify({"error": "Phone number and bot response are required"}), 400
    except pyodbc.Error as e:
        logging.error(f"Failed to save response: {e}")
        return jsonify({"error": "Failed to save data"}), 500


@app.route("/api/update_name", methods=["POST"])
def update_name():
    try:
        content = request.get_json()
        phone_number = content.get("phone_number")
        name = content.get("name")

        if not phone_number or not name:
            return jsonify({"error": "Phone number and name are required"}), 400

        with pyodbc.connect(db_string) as conn:
            cursor = conn.cursor()
            query = "UPDATE tbWhatsAppClients SET Name = ? WHERE PhoneNumber = ?"
            cursor.execute(query, name, phone_number)
            if cursor.rowcount == 0:
                return jsonify({"error": "Phone number not found"}), 404
            conn.commit()

        return jsonify({"message": "Name updated successfully"}), 200
    except pyodbc.Error as e:
        logging.error(f"Failed to update name: {e}")
        return jsonify({"error": "Failed to update name"}), 500

@app.route("/api/latest_chat", methods=["GET"])
def get_latest_chat():
    try:
        with pyodbc.connect(db_string) as conn:
            cursor = conn.cursor()
            
            # Get the phone number with the most recent interaction (latest last_conversation_date)
            query = """
                SELECT TOP 1 c.PhoneNumber AS phone_number
                FROM tbWhatsAppClients c
                LEFT JOIN tbWhatsAppChat ch ON c.ClientID = ch.ClientID
                GROUP BY c.PhoneNumber
                ORDER BY MAX(ch.[Date]) DESC
            """
            cursor.execute(query)
            latest_user = cursor.fetchone()

            if latest_user is None:
                return jsonify({"error": "No chats found"}), 404
            
            latest_phone_number = latest_user.phone_number

            # Fetch the entire chat history for this phone number
            chat_query = """
                SELECT User_input, Bot_response, [Date]
                FROM tbWhatsAppChat
                WHERE ClientID = (SELECT ClientID FROM tbWhatsAppClients WHERE PhoneNumber = ?)
                ORDER BY [Date] ASC
            """
            cursor.execute(chat_query, latest_phone_number)
            chat_history = cursor.fetchall()

            if not chat_history:
                return jsonify({"error": "No chat history found for this user"}), 404

            # Format the chat history by date and time
            chats_by_date = {}
            for chat in chat_history:
                timestamp = chat.Date
                date = timestamp.strftime("%d-%m-%Y")  # Group by date (e.g., "09-09-2024")
                time = timestamp.strftime("%I:%M %p")  # Time format (e.g., "9:15 AM")

                message = {
                    "time": time,
                    "bot_response": chat.Bot_response
                }

                if chat.User_input:
                    message["user_input"] = chat.User_input

                if date not in chats_by_date:
                    chats_by_date[date] = []

                chats_by_date[date].append(message)

            return jsonify({
                "phone_number": latest_phone_number,
                "chat_history": chats_by_date
            }), 200
    except pyodbc.Error as e:
        logging.error(f"Failed to retrieve chat history: {e}")
        return jsonify({"error": "Failed to retrieve data"}), 500

@app.route("/api/search_contact", methods=["GET"])
def search_contact():
    try:
        search_term = request.args.get('query', '').strip()

        if not search_term:
            return jsonify({"error": "Search term is required"}), 400

        with pyodbc.connect(db_string) as conn:
            cursor = conn.cursor()

            # Query to search for users by name or phone number
            search_query = """
                SELECT c.PhoneNumber AS phone_number,
                       ISNULL(c.Name, c.PhoneNumber) AS display_name,
                       MAX(ch.[Date]) AS last_conversation_date
                FROM tbWhatsAppClients c
                LEFT JOIN tbWhatsAppChat ch ON c.ClientID = ch.ClientID
                WHERE c.PhoneNumber LIKE ? OR c.Name LIKE ?
                GROUP BY c.PhoneNumber, c.Name
                ORDER BY MAX(ch.[Date]) DESC
            """
            # Using the search term for both name and phone number search
            search_term_with_wildcards = f"%{search_term}%"
            cursor.execute(search_query, (search_term_with_wildcards, search_term_with_wildcards))
            search_results = cursor.fetchall()

            if not search_results:
                return jsonify({"message": "No contacts found"}), 404

            contacts_json = []
            for result in search_results:
                contact_info = {
                    "phone_number": result.phone_number,
                    "last_conversation_date": result.last_conversation_date.strftime("%Y-%m-%d") if result.last_conversation_date else None
                }

                if result.display_name != result.phone_number:
                    contact_info["name"] = result.display_name

                contacts_json.append(contact_info)

            return jsonify({
                "searchResults": contacts_json,
                "totalResults": len(contacts_json)
            }), 200

    except pyodbc.Error as e:
        logging.error(f"Failed to search contacts: {e}")
        return jsonify({"error": "Failed to search data"}), 500





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

def insert_chat_history(user_input, bot_response, phone_number):
    try:
        connection = pyodbc.connect(db_string)
        cursor = connection.cursor()

        # Check if the phone number exists in tbWhatsAppClients
        check_client_query = "SELECT ClientID FROM tbWhatsAppClients WHERE PhoneNumber = ?"
        cursor.execute(check_client_query, phone_number)
        client = cursor.fetchone()

        # If client doesn't exist, insert the phone number into tbWhatsAppClients
        if client is None:
            insert_client_query = "INSERT INTO tbWhatsAppClients (PhoneNumber) OUTPUT INSERTED.ClientID VALUES (?)"
            cursor.execute(insert_client_query, phone_number)
            client_id = cursor.fetchone()[0]  # Get the ClientID of the newly inserted client
        else:
            client_id = client[0]  # Get the ClientID if the client exists

        # Insert the chat history into tbWhatsAppChat with current date and time
        insert_chat_query = """
            INSERT INTO tbWhatsAppChat (ClientID, User_input, Bot_response, [Date])
            VALUES (?, ?, ?, GETDATE())
        """
        cursor.execute(insert_chat_query, (client_id, user_input, bot_response))        
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
    insert_chat_history(message_body, response, sender_number)

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

@app.route("/Lumi", methods=["GET"])
def webhook_get():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == "123456":
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
        
@app.route("/Lumi", methods=["POST"])
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
        subprocess.run(["ngrok", "http", "--authtoken=2fNXXkafTvkOoZCn44XfG89Zr7E_4Va2jB9AqQbnWGFkKHTrr", "--domain=intent-sharply-kodiak.ngrok-free.app", "5000"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        # Handle the error, if needed
        pass

if __name__ == "__main__":
    # Start ngrok in a separate thread
    ngrok_thread = threading.Thread(target=run_ngrok)
    ngrok_thread.start()

    # Start Flask app
    app.run(port=5000, debug=False)
