import os
import sys
import json
import requests
import psycopg2
from psycopg2 import extras

# --- Project Path Setup ---
# Ensures the script can import modules from the parent directory (e.g., 'database').
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call
from common.utils import get_best_buy_api_key

# --- Configuration ---
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shipments_to_update_on_bb(conn):
    """
    Fetches shipments that have a tracking number but have not yet been
    updated on the Best Buy platform.

    This function identifies the exact set of orders that are ready for the final
    step of the fulfillment process.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        A list of shipment dictionaries.
    """
    shipments = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Selects shipments that have had a label created but have not yet been
            # marked as 'shipped' in our system. This prevents processing orders
            # that have already been completed.
            cur.execute("""
                SELECT s.shipment_id, s.order_id, s.tracking_pin
                FROM shipments s
                JOIN orders o ON s.order_id = o.order_id
                WHERE s.status = 'label_created' AND o.status != 'shipped';
            """)
            shipments = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shipments for tracking update. Reason: {e}")
    return shipments

def update_all_statuses_to_shipped(conn, shipment_id, order_id):
    """
    Atomically updates the status of both the shipment and the original order
    to reflect that the fulfillment process is complete.

    By performing these updates in a single transaction, we ensure that the
    database remains in a consistent state.

    Args:
        conn: An active psycopg2 database connection object.
        shipment_id (int): The ID of the shipment to update to 'tracking_updated'.
        order_id (str): The ID of the order to update to 'shipped'.
    """
    try:
        with conn.cursor() as cur:
            # Update the shipment record to show it has been processed.
            cur.execute("UPDATE shipments SET status = 'tracking_updated' WHERE shipment_id = %s;", (shipment_id,))
            # Update the main order record to the final 'shipped' state.
            cur.execute("UPDATE orders SET status = 'shipped' WHERE order_id = %s;", (order_id,))
        conn.commit()
        print(f"INFO: Successfully updated status to 'shipped' for order {order_id}.")
    except Exception as e:
        print(f"ERROR: Could not update statuses to shipped for order {order_id}. Reason: {e}")
        conn.rollback()

# =====================================================================================
# --- API Interaction Functions ---
# =====================================================================================

def update_bb_tracking_number(api_key, order_id, tracking_pin):
    """
    Calls the Best Buy API to update the tracking number for a given order.

    Args:
        api_key (str): The Best Buy API key.
        order_id (str): The order to update.
        tracking_pin (str): The Canada Post tracking number.

    Returns:
        A tuple of (is_success, response_text, status_code).
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/tracking"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    # The carrier code 'CPCL' is specific to Canada Post.
    payload = {"carrier_code": "CPCL", "tracking_number": tracking_pin}

    print(f"INFO: Updating tracking for order {order_id} with PIN {tracking_pin}...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True, response.text, response.status_code
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to update tracking for order {order_id}: {response_text}")
        return False, response_text, status_code

def mark_bb_order_as_shipped(api_key, order_id):
    """
    Calls the Best Buy API to mark an order as shipped. This is the final,
    customer-facing step in the process.

    Args:
        api_key (str): The Best Buy API key.
        order_id (str): The order to mark as shipped.

    Returns:
        A tuple of (is_success, response_text, status_code).
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/ship"
    headers = {'Authorization': api_key}

    print(f"INFO: Marking order {order_id} as shipped...")
    try:
        response = requests.put(url, headers=headers, timeout=30)
        response.raise_for_status()
        return True, response.text, response.status_code
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to mark order {order_id} as shipped: {response_text}")
        return False, response_text, status_code

# =====================================================================================
# --- Main Workflow ---
# =====================================================================================

def main():
    """
    Main function to run the tracking update workflow. It fetches shipments that
    need updating, calls the Best Buy APIs, and updates the database.
    """
    print("\n--- Starting Tracking Update Workflow ---")
    conn = get_db_connection()
    api_key = get_best_buy_api_key()

    if not conn or not api_key:
        print("CRITICAL: Cannot proceed without DB connection and Best Buy API key.")
        return

    shipments_to_update = get_shipments_to_update_on_bb(conn)

    if not shipments_to_update:
        print("INFO: No shipments found that require a tracking update.")
    else:
        print(f"INFO: Found {len(shipments_to_update)} shipments to update on Best Buy.")
        for shipment in shipments_to_update:
            order_id = shipment['order_id']
            tracking_pin = shipment['tracking_pin']
            shipment_id = shipment['shipment_id']
            print(f"\n--- Processing Order: {order_id} ---")

            # Step 1: Update the tracking number on Best Buy's platform.
            is_success, resp_text, status_code = update_bb_tracking_number(api_key, order_id, tracking_pin)
            # Log the result of this API call.
            log_api_call(conn, 'BestBuy', 'UpdateTracking', order_id, {"tracking_pin": tracking_pin}, resp_text, status_code, is_success)

            if not is_success:
                print(f"WARNING: Skipping rest of process for order {order_id} due to tracking update failure.")
                continue # Move to the next shipment

            # Step 2: Mark the order as shipped on Best Buy's platform.
            is_success, resp_text, status_code = mark_bb_order_as_shipped(api_key, order_id)
            # Log the result of this second API call.
            log_api_call(conn, 'BestBuy', 'MarkAsShipped', order_id, None, resp_text, status_code, is_success)

            if not is_success:
                print(f"WARNING: Failed to mark order {order_id} as shipped, but tracking number was successfully updated.")
                continue # Move to the next shipment

            # Step 3: If both API calls were successful, update our local database statuses.
            update_all_statuses_to_shipped(conn, shipment_id, order_id)
            print(f"SUCCESS: Order {order_id} has been fully processed and marked as shipped.")

    conn.close()
    print("\n--- Tracking Update Workflow Finished ---")


if __name__ == '__main__':
    main()
