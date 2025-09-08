import os
import sys
import json
import time
import requests
import psycopg2
from datetime import datetime
from psycopg2 import extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key

# --- Configuration ---
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'
MAX_VALIDATION_ATTEMPTS = 3 # Renamed from MAX_ACCEPTANCE_ATTEMPTS for clarity
VALIDATION_PAUSE_SECONDS = 60

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_orders_to_accept_from_db(conn):
    """
    Fetches orders whose most recent status is 'pending_acceptance'.

    This function uses a sophisticated query with a Common Table Expression (CTE)
    and window functions to find the latest status for each order and then filters
    for those that need to be accepted.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        A list of order dictionaries.
    """
    orders = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # This query is the heart of the new status system.
            # 1. 'LatestStatus' CTE: For each order_id, it finds the most recent
            #    status entry by ranking them by timestamp in descending order (rn=1).
            # 2. Final SELECT: It joins this back to the orders table and filters
            #    for orders where the latest status is 'pending_acceptance'.
            cur.execute("""
                WITH LatestStatus AS (
                    SELECT
                        order_id,
                        status,
                        ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY timestamp DESC) as rn
                    FROM order_status_history
                )
                SELECT o.*
                FROM orders o
                JOIN LatestStatus ls ON o.order_id = ls.order_id
                WHERE ls.rn = 1 AND ls.status = 'pending_acceptance';
            """)
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch orders to accept from database. Reason: {e}")
    return orders

# =====================================================================================
# --- Core Workflow & API Interaction ---
# =====================================================================================

def accept_order_via_api(api_key, order):
    """
    Calls the Best Buy Marketplace API to accept the order lines for a single order.
    (This function remains largely unchanged but is included for completeness)
    """
    order_id = order['order_id']
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/accept"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}

    order_data = order['raw_order_data']
    order_lines_payload = [
        {"accepted": True, "id": line['order_line_id']}
        for line in order_data.get('order_lines', [])
    ]
    payload = {"order_lines": order_lines_payload}

    print(f"INFO: Attempting to accept order {order_id}...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True, {"status_code": response.status_code, "body": response.json() if response.content else {}}, payload
    except requests.exceptions.RequestException as e:
        error_body = {}
        if e.response is not None:
            try:
                error_body = e.response.json()
            except json.JSONDecodeError:
                error_body = {"error_text": e.response.text}
        return False, {"status_code": e.response.status_code if e.response is not None else 500, "body": error_body}, payload


def validate_order_status_via_api(api_key, order_id):
    """
    Fetches the current details of an order from the Best Buy API to check its status.
    (This function remains unchanged)
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}"
    headers = {'Authorization': api_key}
    print(f"INFO: Validating status for order {order_id}...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        order_data = response.json()
        return order_data.get('order_state'), response.text, response.status_code
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Could not validate status for order {order_id}. Reason: {e}")
        return None, response_text, status_code


def process_single_order(conn, api_key, order):
    """
    Orchestrates the entire acceptance and validation workflow for a single order
    using the new status history system.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Order: {order_id} ---")

    # Step 1: Attempt to accept the order via the API.
    is_success, api_response, payload = accept_order_via_api(api_key, order)

    # Log the acceptance API call itself.
    log_api_call(conn, 'BestBuy', 'AcceptOrder', order_id, payload, api_response, api_response.get('status_code'), is_success)

    if not is_success:
        details = f"Initial API call to accept order failed with status {api_response.get('status_code')}."
        log_process_failure(conn, order_id, 'OrderAcceptance', details, payload)
        add_order_status_history(conn, order_id, 'acceptance_failed', notes=details)
        return

    # Step 2: Enter the validation loop.
    for attempt in range(1, MAX_VALIDATION_ATTEMPTS + 1):
        print(f"--- Validation Attempt {attempt}/{MAX_VALIDATION_ATTEMPTS} for order {order_id} ---")
        time.sleep(VALIDATION_PAUSE_SECONDS)

        # Check the order's current status via the API.
        current_status, resp_text, status_code = validate_order_status_via_api(api_key, order_id)
        log_api_call(conn, 'BestBuy', 'GetOrderStatus', order_id, None, resp_text, status_code, current_status is not None)

        if current_status in ('WAITING_DEBIT_PAYMENT', 'SHIPPING'):
            add_order_status_history(conn, order_id, 'accepted', notes=f"Validated as '{current_status}'.")
            return

        elif current_status == 'CANCELLED':
            add_order_status_history(conn, order_id, 'cancelled', notes="Validated as 'CANCELLED'.")
            return

        else:
            print(f"WARNING: Order {order_id} status is still '{current_status}' after validation attempt {attempt}.")
            if attempt == MAX_VALIDATION_ATTEMPTS:
                details = f"Validation failed after {MAX_VALIDATION_ATTEMPTS} attempts. Final status was '{current_status}'."
                log_process_failure(conn, order_id, 'OrderAcceptance', details, payload)
                add_order_status_history(conn, order_id, 'acceptance_failed', notes=details)
                return


def main():
    """
    Main function to run the entire order acceptance workflow.
    """
    print("\n--- Starting Order Acceptance Workflow v2 ---")
    conn = get_db_connection()
    api_key = get_best_buy_api_key()

    if not conn or not api_key:
        print("CRITICAL: Cannot proceed without a database connection and API key.")
        return

    orders_to_process = get_orders_to_accept_from_db(conn)

    if not orders_to_process:
        print("INFO: No orders are currently pending acceptance.")
    else:
        print(f"INFO: Found {len(orders_to_process)} orders to process.")
        for order in orders_to_process:
            process_single_order(conn, api_key, order)

    conn.close()
    print("\n--- Order Acceptance Workflow Finished ---")

if __name__ == '__main__':
    main()
