import os
import sys
import json
import requests
import psycopg2
from psycopg2 import extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key

# --- Configuration ---
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shipments_to_update_on_bb(conn):
    """
    Fetches shipments for orders whose most recent status is 'label_created'.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        A list of shipment dictionaries, joined with order data.
    """
    shipments = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # This query identifies orders that are ready for the final tracking update step.
            cur.execute("""
                WITH LatestStatus AS (
                    SELECT
                        order_id,
                        status,
                        ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY timestamp DESC) as rn
                    FROM order_status_history
                )
                SELECT s.shipment_id, s.order_id, s.tracking_pin
                FROM shipments s
                JOIN LatestStatus ls ON s.order_id = ls.order_id
                WHERE ls.rn = 1 AND ls.status = 'label_created';
            """)
            shipments = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shipments for tracking update. Reason: {e}")
    return shipments

# =====================================================================================
# --- API Interaction Functions ---
# =====================================================================================

def update_bb_tracking_number(api_key, order_id, tracking_pin):
    """
    Calls the Best Buy API to update the tracking number for a given order.
    (This function remains unchanged)
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/tracking"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    payload = {"carrier_code": "CPCL", "tracking_number": tracking_pin}

    print(f"INFO: Updating tracking for order {order_id} with PIN {tracking_pin}...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True, response.text, response.status_code, payload
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to update tracking for order {order_id}: {response_text}")
        return False, response_text, status_code, payload

def mark_bb_order_as_shipped(api_key, order_id):
    """
    Calls the Best Buy API to mark an order as shipped.
    (This function remains unchanged)
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
    Main function to run the tracking update workflow using the new schema.
    """
    print("\n--- Starting Tracking Update Workflow v2 ---")
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
            print(f"\n--- Processing Tracking for Order: {order_id} ---")

            # Step 1: Update the tracking number
            is_success, resp_text, status_code, payload = update_bb_tracking_number(api_key, order_id, tracking_pin)
            log_api_call(conn, 'BestBuy', 'UpdateTracking', order_id, payload, resp_text, status_code, is_success)

            if not is_success:
                details = f"Failed to update tracking number on Best Buy. API returned status {status_code}."
                # This is a critical failure because we can't complete the order without this step.
                log_process_failure(conn, order_id, 'TrackingUpdate', details, payload)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                continue

            # Step 2: Mark the order as shipped
            is_success, resp_text, status_code = mark_bb_order_as_shipped(api_key, order_id)
            log_api_call(conn, 'BestBuy', 'MarkAsShipped', order_id, None, resp_text, status_code, is_success)

            if not is_success:
                details = f"Succeeded in updating tracking PIN, but failed to mark order as shipped. API returned status {status_code}."
                # This is also critical and needs manual review.
                log_process_failure(conn, order_id, 'TrackingUpdate', details)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                continue

            # Step 3: If both API calls were successful, update our local status to the final state.
            add_order_status_history(conn, order_id, 'shipped', notes="Successfully marked as shipped on Best Buy.")
            print(f"SUCCESS: Order {order_id} has been fully processed and marked as shipped.")

    conn.close()
    print("\n--- Tracking Update Workflow Finished ---")


if __name__ == '__main__':
    main()
