import sys
import os
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2 import extras

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db_utils import get_db_connection
from customer_service.src.logic import send_message_to_mirakl

# --- Constants ---
AUTO_REPLY_DELAY_HOURS = 4
TEMPLATE_1 = "Thank you for your message. We will look into it and get back to you as soon as possible."
TEMPLATE_2 = "I would like to provide you with a prompt and immediate resolution to ensure that I keep your purchasing journey to the highest satisfaction with our shop. Please reach out to me directly by phone at 647-444-0848 or by email at wafic.alwazzan@visionvation.com."
SENDER_ID_BOT = "auto_reply_bot"

def get_unread_conversations(conn):
    """
    Fetches all conversations with 'unread' status from the database.
    """
    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("SELECT id, mirakl_thread_id FROM conversations WHERE status = 'unread'")
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching unread conversations: {e}")
        return []

def send_auto_reply(conn, conversation, template_body):
    """
    Inserts an auto-reply message into the database and prepares it for sending.
    """
    try:
        with conn.cursor() as cur:
            sent_at = datetime.now(timezone.utc)
            # Insert the new auto-reply message
            cur.execute(
                """
                INSERT INTO messages (conversation_id, sender_type, sender_id, body, sent_at, message_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (conversation['id'], 'technician', SENDER_ID_BOT, template_body, sent_at, 'auto_reply')
            )

            # Update the conversation's last_message_at timestamp to reflect the new message
            cur.execute(
                "UPDATE conversations SET last_message_at = %s WHERE id = %s",
                (sent_at, conversation['id'])
            )
            # The conversation 'status' remains 'unread' because this is an automated reply.

            conn.commit()
            print(f"INFO: Auto-reply for conversation {conversation['id']} saved to DB.")

            # After saving to DB, send to Mirakl API
            success, result = send_message_to_mirakl(conversation['mirakl_thread_id'], template_body)
            if not success:
                print(f"WARNING: Auto-reply for conversation {conversation['id']} saved to DB, but failed to send to Mirakl: {result}")

            return True
    except Exception as e:
        print(f"Error sending auto-reply for conversation {conversation['id']}: {e}")
        if conn:
            conn.rollback()
        return False

def process_conversation(conn, conversation):
    """
    Analyzes a single conversation and triggers an auto-reply if the conditions are met.
    """
    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute(
                "SELECT sender_type, sent_at, message_type FROM messages WHERE conversation_id = %s ORDER BY sent_at ASC",
                (conversation['id'],)
            )
            messages = cur.fetchall()

            customer_messages = [m for m in messages if m['sender_type'] == 'customer']
            auto_replies = [m for m in messages if m['message_type'] == 'auto_reply']

            # If there are no messages from the customer, there's nothing to reply to.
            if not customer_messages:
                return

            last_customer_message_at = customer_messages[-1]['sent_at']
            # Check if the last customer message is recent enough to ignore.
            if datetime.now(timezone.utc) - last_customer_message_at < timedelta(hours=AUTO_REPLY_DELAY_HOURS):
                return

            # --- Apply Auto-Reply Rules ---

            # Rule 1: First auto-reply for the first unanswered message.
            if len(customer_messages) >= 1 and len(auto_replies) == 0:
                print(f"Rule 1 triggered: Sending first auto-reply to conversation {conversation['id']}.")
                send_auto_reply(conn, conversation, TEMPLATE_1)

            # Rule 2: Second auto-reply for the second unanswered message.
            elif len(customer_messages) >= 2 and len(auto_replies) == 1:
                print(f"Rule 2 triggered: Sending second auto-reply to conversation {conversation['id']}.")
                send_auto_reply(conn, conversation, TEMPLATE_2)

    except Exception as e:
        print(f"Error processing conversation {conversation['id']}: {e}")

def run_auto_reply_logic():
    """
    Main orchestration function for the auto-reply module.
    """
    print("--- Starting Auto-Reply Module ---")
    conn = get_db_connection()
    if conn is None:
        print("Could not connect to the database. Aborting.")
        return

    try:
        unread_conversations = get_unread_conversations(conn)
        print(f"Found {len(unread_conversations)} unread conversations to process.")
        for conv in unread_conversations:
            process_conversation(conn, conv)
        print("--- Auto-Reply Module Finished ---")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_auto_reply_logic()
