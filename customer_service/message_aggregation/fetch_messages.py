import json
import os
import requests
import sys
from datetime import datetime, timedelta, timezone
from psycopg2 import extras

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db_utils import get_db_connection

API_BASE_URL = "https://marketplace.bestbuy.ca/api"
TIMESTAMP_FILE = "customer_service/message_aggregation/last_sync_timestamp.txt"

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

def load_last_sync_timestamp():
    """Loads the last sync timestamp from a file."""
    try:
        with open(TIMESTAMP_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

def save_last_sync_timestamp(timestamp):
    """Saves the last sync timestamp to a file."""
    os.makedirs(os.path.dirname(TIMESTAMP_FILE), exist_ok=True)
    with open(TIMESTAMP_FILE, "w") as f:
        f.write(timestamp)

def get_new_messages(api_key, updated_since):
    """Fetches new message threads from the Mirakl API since the last sync."""
    print(f"Connecting to Mirakl API to check for new messages since {updated_since}...")
    headers = {"Authorization": api_key}
    params = {"with_messages": "true", "updated_since": updated_since}
    all_threads = []
    next_page_token = None
    while True:
        if next_page_token:
            params["page_token"] = next_page_token
        response = requests.get(f"{API_BASE_URL}/inbox/threads", headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching messages: {response.status_code} - {response.text}")
            response.raise_for_status()
        data = response.json()
        all_threads.extend(data.get("data", []))
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
    print(f"Found {len(all_threads)} updated threads.")
    return all_threads

def get_or_create_customer(cur, mirakl_customer_id, firstname, lastname, email):
    """Gets or creates a customer and returns the customer ID."""
    cur.execute("SELECT id FROM customers WHERE mirakl_customer_id = %s", (mirakl_customer_id,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO customers (mirakl_customer_id, firstname, lastname, email) VALUES (%s, %s, %s, %s) RETURNING id",
            (mirakl_customer_id, firstname, lastname, email),
        )
        return cur.fetchone()[0]

def get_or_create_conversation(cur, mirakl_thread_id, customer_id, order_id, subject):
    """Gets or creates a conversation and returns the conversation ID."""
    cur.execute("SELECT id FROM conversations WHERE mirakl_thread_id = %s", (mirakl_thread_id,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO conversations (mirakl_thread_id, customer_id, order_id, subject, last_message_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (mirakl_thread_id, customer_id, order_id, subject, datetime.now(timezone.utc)),
        )
        return cur.fetchone()[0]

def insert_message(cur, conversation_id, sender_type, sender_id, body, sent_at):
    """Inserts a message into the database."""
    cur.execute(
        "INSERT INTO messages (conversation_id, sender_type, sender_id, body, sent_at) VALUES (%s, %s, %s, %s, %s)",
        (conversation_id, sender_type, sender_id, body, sent_at),
    )

def update_conversation_on_new_message(cur, conversation_id, sent_at, sender_type):
    """
    Updates the conversation's timestamp and sets its status based on the sender.
    A message from a 'customer' makes it 'unread', from a 'technician' makes it 'read'.
    """
    new_status = 'unread' if sender_type == 'customer' else 'read'
    cur.execute(
        "UPDATE conversations SET last_message_at = %s, status = %s WHERE id = %s",
        (sent_at, new_status, conversation_id)
    )

def process_and_store_threads(conn, threads):
    """Processes threads from the Mirakl API and stores them in the database."""
    with conn.cursor() as cur:
        for thread in threads:
            for message in thread.get("messages", []):
                # Check if message already exists
                cur.execute("SELECT id FROM messages WHERE id = %s", (message["id"],))
                if cur.fetchone():
                    continue

                from_details = message.get("from", {})
                customer_id = from_details.get("id")
                if not customer_id:
                    continue

                customer_pk = get_or_create_customer(
                    cur, customer_id, from_details.get("firstname"), from_details.get("lastname"), from_details.get("email")
                )

                order_id = thread["entities"][0]["id"] if thread.get("entities") else None
                conversation_pk = get_or_create_conversation(
                    cur, thread["id"], customer_pk, order_id, thread["topic"]["value"]
                )

                sender_type = message.get("from", {}).get("type", "customer").lower()
                insert_message(
                    cur,
                    conversation_pk,
                    sender_type,
                    customer_id,
                    message["body"],
                    message["date_created"],
                )
                update_conversation_on_new_message(cur, conversation_pk, message["date_created"], sender_type)
        conn.commit()
    print(f"Successfully processed and stored {len(threads)} threads.")

def fetch_and_save_messages():
    """Main orchestration function for the message aggregation phase."""
    api_key = load_api_key()
    if not api_key:
        print("Could not load API key. Aborting.")
        return

    conn = get_db_connection()
    if conn is None:
        print("Could not connect to the database. Aborting.")
        return

    try:
        last_sync_timestamp = load_last_sync_timestamp()
        current_sync_timestamp = datetime.now(timezone.utc).isoformat()
        threads = get_new_messages(api_key, last_sync_timestamp)
        if threads:
            process_and_store_threads(conn, threads)
        save_last_sync_timestamp(current_sync_timestamp)
        print("Message sync completed successfully.")
    except Exception as e:
        print(f"An error occurred during message sync: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fetch_and_save_messages()
