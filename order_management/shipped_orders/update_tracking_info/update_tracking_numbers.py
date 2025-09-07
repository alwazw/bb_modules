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
LOGS_DIR_BB = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'best_buy')
LOGS_DIR_CP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'canada_post')
LOGS_DIR_CS = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'customer_service')
CP_SHIPPING_DATA_FILE = os.path.join(LOGS_DIR_CP, 'cp_shipping_labels_data.json')
BB_HISTORY_LOG_FILE = os.path.join(LOGS_DIR_BB, 'orders_shipped_and_validated.json')
CUSTOMER_SERVICE_BB_HISTORY_LOG_FILE = os.path.join(LOGS_DIR_CS, 'orders_shipped_and_validated.json')
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'


def update_tracking_number(api_key, order_id, tracking_number):
    """ Updates the tracking number for a single order on Best Buy. """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/tracking"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    payload = {"carrier_code": "CPCL", "tracking_number": tracking_number}

    print(f"INFO: Updating tracking for order {order_id} with tracking number {tracking_number}...")
    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"SUCCESS: Successfully updated tracking for order {order_id}.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to update tracking for order {order_id}: {e}")
        if e.response is not None:
            print("Response:", e.response.text)
        return False

def mark_order_as_shipped(api_key, order_id):
    """ Calls the Best Buy API to mark an order as shipped. """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/ship"
    headers = {'Authorization': api_key}

    print(f"INFO: Marking order {order_id} as shipped...")
    try:
        response = requests.put(url, headers=headers)
        response.raise_for_status()
        print(f"SUCCESS: Successfully marked order {order_id} as shipped.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to mark order {order_id} as shipped: {e}")
        if e.response is not None:
            print("Response:", e.response.text)
        return False

def get_order_details(api_key, order_id):
    """ Gets the full details for a single order ID. """
    print(f"INFO: Getting full details for order {order_id}...")
    params = {'order_ids': order_id}
    headers = {'Authorization': api_key}

    try:
        response = requests.get(BEST_BUY_API_URL_BASE, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('orders'):
            return data['orders'][0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not get order details for {order_id}: {e}")
        return None

def log_bb_history(order_details_json):
    """ Appends the full order details to the history logs. """
    if not order_details_json:
        return

    for log_path in [BB_HISTORY_LOG_FILE, CUSTOMER_SERVICE_BB_HISTORY_LOG_FILE]:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_entries = []
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_entries = json.load(f)
                except json.JSONDecodeError:
                    log_entries = []
        
        log_entries.append(order_details_json)

        with open(log_path, 'w') as f:
            json.dump(log_entries, f, indent=4)
        print(f"SUCCESS: Appended order details to {log_path}")

def main():
    """ Main function to read shipping data and update tracking numbers. """
    print("\n--- Starting Update Tracking Numbers Script ---")

    api_key = get_best_buy_api_key()
    if not api_key:
        return

    if not os.path.exists(CP_SHIPPING_DATA_FILE):
        print(f"INFO: {CP_SHIPPING_DATA_FILE} not found. No tracking numbers to update.")
        return
    
    with open(CP_SHIPPING_DATA_FILE, 'r') as f:
        try:
            shipped_data = json.load(f)
        except json.JSONDecodeError:
            print(f"ERROR: {CP_SHIPPING_DATA_FILE} is corrupted.")
            return

    if not shipped_data:
        print("INFO: No shipped data found to process.")
        return

    for shipment in shipped_data:
        order_id = shipment.get('order_id')
        tracking_pin = shipment.get('tracking_pin')
        
        if order_id and tracking_pin:
            if update_tracking_number(api_key, order_id, tracking_pin):
                if mark_order_as_shipped(api_key, order_id):
                    order_details = get_order_details(api_key, order_id)
                    if order_details:
                        log_bb_history(order_details)
        else:
            print(f"WARNING: Skipping shipment due to missing order_id or tracking_pin: {shipment}")

    print("--- Update Tracking Numbers Script Finished ---\n")

if __name__ == '__main__':
    main()
