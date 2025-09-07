import os
import sys
import json
import requests
from datetime import datetime

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_best_buy_api_key

# --- Configuration ---
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'best_buy')
PENDING_ACCEPTANCE_FILE = os.path.join(LOGS_DIR, 'pending_acceptance.json')
ACCEPTED_LOG_FILE = os.path.join(LOGS_DIR, 'accepted_orders_log.json')
JOURNAL_FILE = os.path.join(LOGS_DIR, 'order_acceptance_journal.json')
BEST_BUY_ACCEPT_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'


def get_orders_to_accept():
    """ Identifies which orders need to be accepted. """
    print("INFO: Identifying orders that need to be accepted...")

    if not os.path.exists(PENDING_ACCEPTANCE_FILE):
        print("INFO: pending_acceptance.json not found. Assuming no orders to process.")
        return []
    with open(PENDING_ACCEPTANCE_FILE, 'r') as f:
        try:
            pending_orders = json.load(f)
        except json.JSONDecodeError:
            print("ERROR: pending_acceptance.json is corrupted.")
            return []

    if not pending_orders:
        print("INFO: pending_acceptance.json is empty. No orders to process.")
        return []

    if os.path.exists(ACCEPTED_LOG_FILE):
        with open(ACCEPTED_LOG_FILE, 'r') as f:
            try:
                accepted_orders_log = json.load(f)
            except json.JSONDecodeError:
                print("WARNING: accepted_orders_log.json is corrupted. Starting fresh.")
                accepted_orders_log = []
    else:
        accepted_orders_log = []
        print("INFO: accepted_orders_log.json not found. A new file will be created.")

    accepted_order_ids = {entry['order_id'] for entry in accepted_orders_log}
    orders_to_accept = [order for order in pending_orders if order['order_id'] not in accepted_order_ids]

    if not orders_to_accept:
        print("INFO: No new orders to accept.")
    else:
        print(f"INFO: Found {len(orders_to_accept)} orders to be accepted.")

    return orders_to_accept

def accept_order(api_key, order):
    """ Calls the Best Buy API to accept a single order. """
    if not api_key:
        print("ERROR: API key is missing. Cannot accept order.")
        return None

    order_id = order['order_id']
    url = f"{BEST_BUY_ACCEPT_API_URL_BASE}/{order_id}/accept"

    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }

    order_lines_payload = []
    for line in order.get('order_lines', []):
        order_lines_payload.append({
            "accepted": True,
            "id": line['order_line_id']
        })

    payload = {
        "order_lines": order_lines_payload
    }

    print(f"INFO: Sending API request to accept order {order_id} at {url}...")
    print(f"INFO: Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"SUCCESS: API call for order {order_id} was successful with status code {response.status_code}.")
        if response.content:
            return response.json()
        return {"status": "success", "message": "Order accepted successfully."}
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request to accept order {order_id} failed: {e}")
        if e.response is not None:
            return e.response.json()
        return {"error": str(e)}

def log_acceptance(order_id, api_response):
    """ Logs the acceptance in the log and journal files. """
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.now().isoformat()

    print(f"INFO: Logging acceptance for order {order_id} in {ACCEPTED_LOG_FILE}...")
    if os.path.exists(ACCEPTED_LOG_FILE):
        with open(ACCEPTED_LOG_FILE, 'r') as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = []
    else:
        log_data = []

    log_data.append({"order_id": order_id, "timestamp": timestamp})

    with open(ACCEPTED_LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=4)

    print(f"INFO: Logging API response for order {order_id} in {JOURNAL_FILE}...")
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            try:
                journal_data = json.load(f)
            except json.JSONDecodeError:
                journal_data = []
    else:
        journal_data = []

    journal_data.append({
        "order_id": order_id,
        "timestamp": timestamp,
        "api_response": api_response
    })

    with open(JOURNAL_FILE, 'w') as f:
        json.dump(journal_data, f, indent=4)

def main():
    """ Main function to execute the script's logic. """
    print("\n--- Starting Accept Orders Script ---")
    api_key = get_best_buy_api_key()
    if api_key:
        orders_to_process = get_orders_to_accept()
        for order in orders_to_process:
            api_response = accept_order(api_key, order)
            if api_response:
                log_acceptance(order['order_id'], api_response)
    print("--- Accept Orders Script Finished ---\n")

if __name__ == '__main__':
    main()
