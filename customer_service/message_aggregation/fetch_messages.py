import json
import os
import requests
from datetime import datetime, timedelta

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

def get_new_messages(api_key):
    """
    Fetches new message threads from the Mirakl API.
    """
    print("Connecting to Mirakl API to check for new messages...")

    headers = {"Authorization": api_key}

    # For testing, we'll fetch threads updated in the last 24 hours.
    # A more robust implementation would store the timestamp of the last run.
    updated_since = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"

    params = {
        "with_messages": "true",
        "updated_since": updated_since,
    }

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

def transform_threads_to_messages(threads):
    """
    Transforms the raw thread data from the API into a simplified message format.
    """
    transformed_messages = []
    for thread in threads:
        if thread.get("messages"):
            # We'll just take the last message for simplicity
            last_message = thread["messages"][-1]
            transformed_messages.append({
                "message_id": last_message["id"],
                "thread_id": thread["id"],
                "order_id": thread["entities"][0]["id"] if thread.get("entities") else "N/A",
                "customer_id": last_message["from"].get("id", "N/A"),
                "subject": thread["topic"]["value"],
                "message": last_message["body"],
                "timestamp": last_message["date_created"],
                "status": "UNREAD" # This is a simplification, the API doesn't provide a simple unread status
            })
    return transformed_messages

def save_messages_to_json(messages, file_path="customer_service/messages.json"):
    """
    Saves a list of messages to a JSON file.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        with open(file_path, "r") as f:
            existing_messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_messages = []

    existing_ids = {msg["message_id"] for msg in existing_messages}
    new_messages = [msg for msg in messages if msg["message_id"] not in existing_ids]

    if not new_messages:
        print("No new messages to save.")
        return

    updated_messages = existing_messages + new_messages

    with open(file_path, "w") as f:
        json.dump(updated_messages, f, indent=4)

    print(f"Successfully saved {len(new_messages)} new messages to {file_path}.")

def fetch_and_save_messages():
    """
    Main orchestration function for the message aggregation phase.
    """
    api_key = load_api_key()
    if not api_key:
        print("Could not load API key. Aborting.")
        return

    threads = get_new_messages(api_key)

    if threads:
        messages = transform_threads_to_messages(threads)
        save_messages_to_json(messages)

if __name__ == "__main__":
    fetch_and_save_messages()
