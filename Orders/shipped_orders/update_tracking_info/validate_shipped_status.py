import os
import sys
import json
import requests

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_best_buy_api_key

# --- Configuration ---
LOGS_DIR_CP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'canada_post')
CP_SHIPPING_DATA_FILE = os.path.join(LOGS_DIR_CP, 'cp_shipping_labels_data.json')
BEST_BUY_API_URL = 'https://marketplace.bestbuy.ca/api/orders'


def check_order_status(api_key, order_id):
    """ Checks the status of a single order on Best Buy. """
    params = {'order_ids': order_id}
    headers = {'Authorization': api_key}

    try:
        response = requests.get(BEST_BUY_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('orders'):
            return data['orders'][0].get('order_state')
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not get status for order {order_id}: {e}")
    return None

def main():
    """ Main function to validate that orders have been marked as shipped. """
    print("\n--- Starting Validate Shipped Status Script ---")

    api_key = get_best_buy_api_key()
    if not api_key:
        return
    
    if not os.path.exists(CP_SHIPPING_DATA_FILE):
        print(f"INFO: {CP_SHIPPING_DATA_FILE} not found. No orders to validate.")
        return
    
    with open(CP_SHIPPING_DATA_FILE, 'r') as f:
        try:
            shipped_data = json.load(f)
        except json.JSONDecodeError:
            print(f"ERROR: {CP_SHIPPING_DATA_FILE} is corrupted.")
            return

    if not shipped_data:
        print("INFO: No shipped data found to validate.")
        return
        
    for shipment in shipped_data:
        order_id = shipment.get('order_id')
        if order_id:
            print(f"INFO: Validating status for order {order_id}...")
            status = check_order_status(api_key, order_id)
            if status == 'SHIPPING' or status == 'SHIPPED':
                print(f"SUCCESS: Order {order_id} is marked as {status}.")
            else:
                print(f"WARNING: Order {order_id} has status '{status}', not 'SHIPPING' or 'SHIPPED'.")
            
    print("--- Validate Shipped Status Script Finished ---\n")

if __name__ == '__main__':
    main()
