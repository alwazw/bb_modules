import os
import sys
import json
import time
import requests
import psycopg2
from datetime import datetime
from psycopg2 import extras

# --- Project Path Setup ---
# This ensures that the script can import modules from the parent directory (e.g., 'database', 'common').
# It makes the script runnable from any location, not just the project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection
from common.utils import get_best_buy_api_key

# --- Configuration ---
# Centralized constants for the workflow.
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'
# The number of times to retry VALIDATING an order's status after a successful acceptance call.
MAX_ACCEPTANCE_ATTEMPTS = 3
# The time to wait in seconds between the acceptance API call and the first validation check.
VALIDATION_PAUSE_SECONDS = 60 # 1 minute

# =====================================================================================
# --- Database Interaction Functions ---
# These functions abstract the raw SQL queries, making the main workflow logic cleaner
# and easier to read. Each function handles a single, specific database operation.
# =====================================================================================

def get_orders_to_accept_from_db(conn):
    """
    Fetches all orders from the database that have the 'pending_acceptance' status.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        A list of dictionaries, where each dictionary represents an order.
        Returns an empty list if no orders are found or if an error occurs.
    """
    orders = []
    try:
        # DictCursor is used to get results as dictionaries instead of tuples,
        # which makes accessing columns by name possible and the code more readable.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM orders WHERE status = 'pending_acceptance';")
            # Fetch all results from the query.
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch orders from database. Reason: {e}")
    return orders

def log_acceptance_attempt_to_db(conn, order_id, attempt_number, status, api_response):
    """
    Logs the result of an order acceptance API call to the 'order_acceptance_attempts' table.
    This provides a detailed audit trail for every attempt made.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the order being processed.
        attempt_number (int): The attempt number (in this workflow, it's always 1).
        status (str): The result of the attempt, e.g., 'success' or 'failure'.
        api_response (dict): The full response from the API, stored as JSON for later analysis.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO order_acceptance_attempts (order_id, attempt_number, status, api_response)
                VALUES (%s, %s, %s, %s);
                """,
                # The api_response dictionary is serialized into a JSON string for storage in the JSONB column.
                (order_id, attempt_number, status, json.dumps(api_response))
            )
        # The transaction must be committed to save the changes.
        conn.commit()
    except Exception as e:
        print(f"ERROR: Could not log acceptance attempt for order {order_id}. Reason: {e}")
        # If logging fails, roll back the transaction to avoid a partial state.
        conn.rollback()

def log_to_debug_table(conn, order_id, details, payload):
    """
    Logs critical failure information to the 'order_acceptance_debug_logs' table.
    This table is intended to be monitored by humans or a separate alerting system
    for orders that require manual intervention.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the failed order.
        details (str): A human-readable string explaining the failure.
        payload (dict): The request payload sent to the API, stored for debugging.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO order_acceptance_debug_logs (order_id, details, raw_request_payload)
                VALUES (%s, %s, %s);
                """,
                (order_id, details, json.dumps(payload))
            )
        conn.commit()
        print(f"INFO: Logged debug information for order {order_id}.")
    except Exception as e:
        print(f"ERROR: Could not log to debug table for order {order_id}. Reason: {e}")
        conn.rollback()

def update_order_status_in_db(conn, order_id, new_status):
    """
    Updates the 'status' field for a given order in the 'orders' table.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the order to update.
        new_status (str): The new status to set (e.g., 'accepted', 'cancelled', 'acceptance_failed').
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = %s WHERE order_id = %s;",
                (new_status, order_id)
            )
        conn.commit()
        print(f"INFO: Updated status for order {order_id} to '{new_status}'.")
    except Exception as e:
        print(f"ERROR: Could not update status for order {order_id}. Reason: {e}")
        conn.rollback()

# =====================================================================================
# --- Core Workflow & API Interaction ---
# =====================================================================================

def accept_order_via_api(api_key, order):
    """
    Calls the Best Buy Marketplace API to accept the order lines for a single order.

    Args:
        api_key (str): The authentication key for the Best Buy API.
        order (dict): The order object, which contains the order lines.

    Returns:
        A tuple containing:
        - A dictionary with the API response details (status_code, body).
        - The payload that was sent to the API.
    """
    order_id = order['order_id']
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/accept"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}

    # Construct the payload from the 'order_lines' stored in the raw_order_data JSON.
    # The API requires a list of order line IDs to be accepted.
    order_data = order['raw_order_data']
    order_lines_payload = [
        {"accepted": True, "id": line['order_line_id']}
        for line in order_data.get('order_lines', [])
    ]
    payload = {"order_lines": order_lines_payload}

    print(f"INFO: Attempting to accept order {order_id}...")
    try:
        # Make the PUT request to the Best Buy API. A timeout is set for resilience.
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        # Raise an exception for non-2xx status codes (e.g., 4xx, 5xx).
        response.raise_for_status()
        print(f"SUCCESS: API call for order {order_id} was successful.")
        # Return a structured dictionary for the response and the payload for logging purposes.
        return {"status_code": response.status_code, "body": response.json() if response.content else {}}, payload
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request to accept order {order_id} failed: {e}")
        error_body = {}
        if e.response is not None:
            try:
                error_body = e.response.json()
            except json.JSONDecodeError:
                error_body = {"error_text": e.response.text}
        return {"status_code": e.response.status_code if e.response is not None else 500, "body": error_body}, payload


def validate_order_status_via_api(api_key, order_id):
    """
    Fetches the current details of an order from the Best Buy API to check its status.

    Args:
        api_key (str): The authentication key for the Best Buy API.
        order_id (str): The ID of the order to validate.

    Returns:
        str or None: The order status string (e.g., 'WAITING_DEBIT_PAYMENT') if successful, otherwise None.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}"
    headers = {'Authorization': api_key}
    print(f"INFO: Validating status for order {order_id}...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        order_data = response.json()
        status = order_data.get('order_state')
        print(f"INFO: Current status for order {order_id} is '{status}'.")
        return status
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not validate status for order {order_id}. Reason: {e}")
        return None


def process_single_order(conn, api_key, order):
    """
    Orchestrates the entire acceptance and validation workflow for a single order.

    This function implements the core logic:
    1.  Accept the order via the API ONCE.
    2.  If the acceptance fails, log for debug and stop.
    3.  If successful, enter a validation loop that retries up to MAX_ACCEPTANCE_ATTEMPTS.
    4.  In the loop, it pauses, then checks the order status via the API.
    5.  If the status is final ('accepted' or 'cancelled'), it updates the DB and stops.
    6.  If the loop completes without successful validation, it logs for debug and stops.

    Args:
        conn: An active psycopg2 database connection object.
        api_key (str): The Best Buy API key.
        order (dict): The order object to be processed.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Order: {order_id} ---")

    # Step 1: Attempt to accept the order via the API. This is done only ONCE.
    api_response, payload = accept_order_via_api(api_key, order)
    is_success = 200 <= api_response.get('status_code', 500) < 300

    # Log the result of this single, crucial attempt.
    log_acceptance_attempt_to_db(conn, order_id, 1, 'success' if is_success else 'failure', api_response)

    # If the initial API call to accept the order fails, we can't proceed.
    if not is_success:
        print(f"CRITICAL: API call to accept order {order_id} failed. Halting processing for this order.")
        log_to_debug_table(conn, order_id, "Initial API call to accept order failed.", payload)
        update_order_status_in_db(conn, order_id, 'acceptance_failed')
        return # Stop processing this specific order.

    # Step 2: Enter the validation loop. We retry checking the status because it can take time
    # for Best Buy's system to update the order state after acceptance.
    for attempt in range(1, MAX_ACCEPTANCE_ATTEMPTS + 1):
        print(f"--- Validation Attempt {attempt}/{MAX_ACCEPTANCE_ATTEMPTS} for order {order_id} ---")

        # Pause to give the external system time to process the acceptance.
        print(f"INFO: Pausing for {VALIDATION_PAUSE_SECONDS} seconds before validation...")
        time.sleep(VALIDATION_PAUSE_SECONDS)

        # Check the order's current status via the API.
        current_status = validate_order_status_via_api(api_key, order_id)

        # Check for a successful outcome. 'SHIPPING' is also a success state.
        if current_status in ('WAITING_DEBIT_PAYMENT', 'SHIPPING'):
            print(f"SUCCESS: Order {order_id} has been successfully accepted and validated.")
            update_order_status_in_db(conn, order_id, 'accepted')
            return # Successfully exit the process for this order.

        elif current_status == 'CANCELLED':
            print(f"INFO: Order {order_id} was cancelled.")
            update_order_status_in_db(conn, order_id, 'cancelled')
            return # Successfully exit the process for this order.

        else:
            # If the status is still pending or something unexpected, we log and retry (if attempts remain).
            print(f"WARNING: Order {order_id} status is still '{current_status}' after validation attempt {attempt}.")
            if attempt == MAX_ACCEPTANCE_ATTEMPTS:
                # If this was the final validation attempt, the process has failed.
                print(f"CRITICAL: Order {order_id} failed to validate after {MAX_ACCEPTANCE_ATTEMPTS} attempts.")
                print("!!! NOTIFICATION: Manual intervention required !!!")
                log_to_debug_table(conn, order_id, f"Validation failed after {MAX_ACCEPTANCE_ATTEMPTS} attempts. Final status was '{current_status}'.", payload)
                update_order_status_in_db(conn, order_id, 'acceptance_failed')
                return # Exit the process for this order.


def main():
    """
    Main function to run the entire order acceptance workflow.
    It fetches all pending orders and processes them one by one.
    """
    print("\n--- Starting Order Acceptance Workflow ---")
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

    # Close the database connection once all orders have been processed.
    conn.close()
    print("\n--- Order Acceptance Workflow Finished ---")

if __name__ == '__main__':
    main()
