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
ACCEPTED_LOG_FILE = os.path.join(LOGS_DIR, 'accepted_orders_log.json')
FAILED_LOG_FILE = os.path.join(LOGS_DIR, 'failed_order_acceptances.json')
BEST_BUY_API_URL = 'https://marketplace.bestbuy.ca/api/orders'


def get_currently_pending_orders(api_key):
    """ Retrieves a fresh list of orders with 'WAITING_ACCEPTANCE' status from the Best Buy API. """
    if not api_key:
        print("ERROR: API key is missing. Cannot retrieve orders.")
        return []

    headers = {'Authorization': api_key}
    params = {'order_state_codes': 'WAITING_ACCEPTANCE'}

    print("INFO: Calling Best Buy API for a fresh list of pending orders for validation...")
    try:
        response = requests.get(BEST_BUY_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"SUCCESS: API reports {data.get('total_count', 0)} orders are currently pending acceptance.")
        return data.get('orders', [])
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed during validation: {e}")
        return []

def validate_acceptance():
    """ Compares recently accepted orders with the current pending list to validate acceptance. """
    print("INFO: Starting order acceptance validation...")
    api_key = get_best_buy_api_key()
    if not api_key:
        return 'ERROR'

    currently_pending_orders_list = get_currently_pending_orders(api_key)
    currently_pending_ids = {order['order_id'] for order in currently_pending_orders_list}

    accepted_log = []
    if not os.path.exists(ACCEPTED_LOG_FILE):
        print("INFO: accepted_orders_log.json not found. Assuming no orders have been accepted yet.")
    else:
        with open(ACCEPTED_LOG_FILE, 'r') as f:
            try:
                accepted_log = json.load(f)
            except json.JSONDecodeError:
                print("ERROR: accepted_orders_log.json is corrupted.")
                return 'ERROR'

    accepted_log_ids = {entry['order_id'] for entry in accepted_log}
    failed_acceptances = currently_pending_ids.intersection(accepted_log_ids)

    if failed_acceptances:
        print(f"ERROR: Found {len(failed_acceptances)} orders that failed to be accepted.")
        print("Failed Order Numbers:", list(failed_acceptances))

        os.makedirs(LOGS_DIR, exist_ok=True)
        failed_log_entries = []
        if os.path.exists(FAILED_LOG_FILE):
            with open(FAILED_LOG_FILE, 'r') as f:
                try:
                    failed_log_entries = json.load(f)
                except json.JSONDecodeError:
                    pass

        for order_id in failed_acceptances:
            failed_log_entries.append({
                "order_id": order_id,
                "failure_timestamp": datetime.now().isoformat()
            })

        with open(FAILED_LOG_FILE, 'w') as f:
            json.dump(failed_log_entries, f, indent=4)

        return 'VALIDATION_FAILED'

    new_unprocessed_orders = currently_pending_ids.difference(accepted_log_ids)

    if new_unprocessed_orders:
        print(f"INFO: Found {len(new_unprocessed_orders)} new pending orders that were not in the last run.")
        print("New Order Numbers:", list(new_unprocessed_orders))
        return 'NEW_ORDERS_FOUND'

    if not currently_pending_ids:
        print("SUCCESS: All orders have been successfully accepted.")
        return 'SUCCESS'

    print("INFO: Validation finished. Some orders may still be pending that were not processed in this run.")
    return 'INCOMPLETE'

def main():
    """ Main function to execute the script's logic. """
    print("\n--- Starting Order Acceptance Validation Script ---")
    validation_status = validate_acceptance()
    print(f"Validation Result: {validation_status}")
    print("--- Order Acceptance Validation Script Finished ---\n")

if __name__ == '__main__':
    main()
