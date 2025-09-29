import os
import sys
import json
import requests

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_best_buy_api_key

# --- Configuration ---
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'best_buy')
PENDING_SHIPPING_FILE = os.path.join(LOGS_DIR, 'orders_pending_shipping.json')
BEST_BUY_API_URL = 'https://marketplace.bestbuy.ca/api/orders'


def retrieve_awaiting_shipment_orders(api_key):
    """ Retrieves orders with 'SHIPPING' status from the Best Buy API. """
    if not api_key:
        print("ERROR: API key is missing. Cannot retrieve orders.")
        return []

    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    params = {
        'order_state_codes': 'SHIPPING'
    }

    print("INFO: Calling Best Buy API to retrieve orders awaiting shipment...")
    try:
        response = requests.get(BEST_BUY_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"SUCCESS: Found {data.get('total_count', 0)} orders awaiting shipment from API.")
        return data.get('orders', [])
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}")
        return []

from database.db_utils import get_db_connection, add_order_status_history

def save_new_orders_to_db(new_orders):
    """
    Saves new orders to the database, avoiding duplicates.
    These orders are fetched from Best Buy with 'SHIPPING' status, so we mark them as 'accepted'
    in our system, making them ready for label creation.
    """
    conn = get_db_connection()
    if not conn:
        print("CRITICAL: Could not connect to the database. Cannot save new orders.")
        return

    added_count = 0
    try:
        with conn.cursor() as cur:
            for order in new_orders:
                order_id = order['order_id']
                # Use ON CONFLICT to gracefully handle orders that already exist.
                cur.execute(
                    "INSERT INTO orders (order_id, raw_order_data) VALUES (%s, %s) ON CONFLICT (order_id) DO NOTHING;",
                    (order_id, json.dumps(order))
                )
                # cur.rowcount will be 1 if a new row was inserted, 0 otherwise.
                if cur.rowcount > 0:
                    # If the order was newly inserted, set its initial status to 'accepted'.
                    add_order_status_history(conn, order_id, 'accepted', 'Order imported from Best Buy awaiting shipment.')
                    added_count += 1
                    print(f"INFO: Imported new order {order_id} and marked as 'accepted'.")
        conn.commit()
    except Exception as e:
        print(f"ERROR: Database operation failed. Reason: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

    if added_count > 0:
        print(f"SUCCESS: Imported {added_count} new orders into the database.")
    else:
        print("INFO: No new orders to import.")


def main():
    """ Main function to execute the script's logic. """
    print("\n--- Starting Retrieve Orders Pending Shipment Script ---")
    api_key = get_best_buy_api_key()
    if api_key:
        awaiting_shipment_orders = retrieve_awaiting_shipment_orders(api_key)
        if awaiting_shipment_orders:
            save_new_orders_to_db(awaiting_shipment_orders)
    print("--- Retrieve Orders Pending Shipment Script Finished ---\n")

if __name__ == '__main__':
    main()
