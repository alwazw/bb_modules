import sys
import os
import requests
from psycopg2 import extras
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db_utils import get_db_connection

API_BASE_URL = "https://marketplace.bestbuy.ca/api"

def load_api_key(secret_file="secrets.txt"):
    """Loads the Best Buy API key from the secrets file."""
    try:
        with open(secret_file, "r") as f:
            for line in f:
                if line.startswith("BEST_BUY_API_KEY="):
                    return line.strip().split("=")[1]
    except FileNotFoundError:
        print(f"Error: {secret_file} not found.")
        return None
    return None

def send_message_to_mirakl(thread_id, message_body):
    """
    Sends a reply message to a specific conversation thread via the Mirakl API.
    """
    api_key = load_api_key()
    if not api_key:
        return False, "Could not load API key."

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    payload = { "body": message_body }

    url = f"{API_BASE_URL}/inbox/threads/{thread_id}/messages"

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Successfully sent message to thread {thread_id} via Mirakl API.")
        return True, response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to Mirakl API for thread {thread_id}: {e}")
        return False, str(e)

def _format_conversation_list(records):
    """Formats a list of conversation records for the API response."""
    conversations = []
    for record in records:
        conversations.append({
            "id": record["id"],
            "customer_name": f"{record['firstname']} {record['lastname']}",
            "order_id": record["order_id"],
            "subject": record["subject"],
            "last_message_at": record["last_message_at"].isoformat(),
            "last_message_snippet": record["body"][:100] if record["body"] else ""
        })
    return conversations

def _format_message_list(records):
    """Formats a list of message records for the API response."""
    messages = []
    for record in records:
        messages.append({
            "id": record["id"],
            "sender_type": record["sender_type"],
            "sender_id": record["sender_id"],
            "body": record["body"],
            "sent_at": record["sent_at"].isoformat()
        })
    return messages

def get_all_conversations():
    """
    Retrieves a list of all conversations from the database, including the customer's name
    and a snippet of the last message.
    """
    conn = get_db_connection()
    if not conn:
        return None, "Could not connect to the database."

    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("""
                WITH latest_message AS (
                    SELECT
                        m.conversation_id,
                        m.body,
                        ROW_NUMBER() OVER(PARTITION BY m.conversation_id ORDER BY m.sent_at DESC) as rn
                    FROM messages m
                )
                SELECT
                    c.id,
                    c.order_id,
                    c.subject,
                    c.last_message_at,
                    cust.firstname,
                    cust.lastname,
                    lm.body
                FROM conversations c
                JOIN customers cust ON c.customer_id = cust.id
                LEFT JOIN latest_message lm ON c.id = lm.conversation_id AND lm.rn = 1
                ORDER BY c.last_message_at DESC;
            """)
            records = cur.fetchall()
            return _format_conversation_list(records), None
    except Exception as e:
        return None, f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()

def get_conversation_by_id(conversation_id):
    """
    Retrieves all messages for a single conversation, sorted by sent_at.
    """
    conn = get_db_connection()
    if not conn:
        return None, "Could not connect to the database."

    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("SELECT * FROM messages WHERE conversation_id = %s ORDER BY sent_at ASC", (conversation_id,))
            records = cur.fetchall()
            return _format_message_list(records), None
    except Exception as e:
        return None, f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()

def add_message_to_conversation(conversation_id, message_data):
    """
    Adds a new message to a conversation from a technician, sends it to the Mirakl API,
    and marks the conversation as 'read'.
    """
    conn = get_db_connection()
    if not conn:
        return None, "Could not connect to the database."

    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            sent_at = datetime.utcnow()
            sender_id = message_data.get("sender_id", "tech_01") # Placeholder for technician ID

            # Insert the new manual message
            cur.execute(
                """
                INSERT INTO messages (conversation_id, sender_type, sender_id, body, sent_at, message_type)
                VALUES (%s, 'technician', %s, %s, %s, 'manual')
                RETURNING *;
                """,
                (conversation_id, sender_id, message_data["body"], sent_at)
            )
            new_message = cur.fetchone()

            # Update conversation timestamps and status
            cur.execute(
                "UPDATE conversations SET last_message_at = %s, status = 'read' WHERE id = %s RETURNING mirakl_thread_id",
                (sent_at, conversation_id)
            )
            mirakl_thread_id = cur.fetchone()['mirakl_thread_id']

            conn.commit()

            # After saving to DB, send to Mirakl API
            success, result = send_message_to_mirakl(mirakl_thread_id, message_data["body"])
            if not success:
                # If the API call fails, we might want to log this more formally.
                # For now, we just print the error.
                print(f"WARNING: Message {new_message['id']} saved to DB, but failed to send to Mirakl: {result}")

            return _format_message_list([new_message])[0], None
    except Exception as e:
        if conn:
            conn.rollback()
        return None, f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()


def get_conversations_by_order_id(order_id):
    """
    Retrieves all conversations for a given order ID.
    """
    conn = get_db_connection()
    if not conn:
        return None, "Could not connect to the database."

    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.order_id,
                    c.subject,
                    c.last_message_at,
                    cust.firstname,
                    cust.lastname,
                    NULL as body
                FROM conversations c
                JOIN customers cust ON c.customer_id = cust.id
                WHERE c.order_id = %s
                ORDER BY c.last_message_at DESC;
            """, (order_id,))
            records = cur.fetchall()
            return _format_conversation_list(records), None
    except Exception as e:
        return None, f"An error occurred: {e}"
    finally:
        if conn:
            conn.close()
