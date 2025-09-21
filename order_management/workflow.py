# -*- coding: utf-8 -*-
"""
================================================================================
Order Management Workflow (V2 - Database Driven)
================================================================================
Purpose:
----------------
This script is the second phase of the order management process. Its primary
responsibility is to accept new orders that have been fetched from the Best Buy
Marketplace API and are waiting in our database with a 'pending_acceptance' status.

The workflow is designed to be robust and idempotent, meaning it can be run
repeatedly without causing duplicate data or unintended side effects. It handles
API communication, status validation, and detailed logging for auditing purposes.

Key Steps:
1.  **Fetch Shippable Orders**: It queries the database to find all orders that
    have the most recent status of 'pending_acceptance'.
2.  **Accept via API**: For each of these orders, it sends a request to the
    Best Buy API to formally accept all the order lines.
3.  **Validate Status**: After attempting to accept, it enters a validation loop.
    It repeatedly checks the order's status via the API until it confirms that
    the order has moved to a post-acceptance state (like 'SHIPPING' or
    'WAITING_DEBIT_PAYMENT') or has been cancelled.
4.  **Update Database**: Throughout the process, it logs every API call and
    updates the order's status in the `order_status_history` table, providing a
    clear audit trail of what happened and when.

This script is intended to be run as a scheduled task (e.g., via a cron job)
to process new orders automatically.
----------------
"""

# =====================================================================================
# --- Imports ---
# =====================================================================================
import os
import sys
import json
import time
import requests
import psycopg2
from datetime import datetime
from psycopg2 import extras

# --- Project Path Setup ---
# This ensures that we can import modules from other parts of the project,
# like 'database' and 'common', by adding the project's root directory to the
# Python path.
#
#       [ project_root ]
#              |
#      -----------------
#      |       |       |
#  database/ common/ order_management/
#
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# --- Module Imports ---
# Imports utility functions from other modules within the project.
from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key


# =====================================================================================
# --- Configuration ---
# =====================================================================================
# Base URL for the Best Buy Marketplace Orders API.
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'

# The maximum number of times the script will check the Best Buy API for a
# status update after accepting an order.
MAX_VALIDATION_ATTEMPTS = 3

# The number of seconds to wait between each validation attempt. This gives the
# Best Buy system time to process the acceptance.
VALIDATION_PAUSE_SECONDS = 60


# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_orders_to_accept_from_db(conn):
    """
    Fetches orders from the database whose most recent status is 'pending_acceptance'.

    This function uses a sophisticated SQL query with a Common Table Expression (CTE)
    and a window function (`ROW_NUMBER()`) to ensure it only retrieves orders that
    are genuinely waiting for acceptance. This is the source of truth for the workflow.

    How the Query Works:
    1.  **`LatestStatus` CTE**: It first looks at the `order_status_history` table.
        For each `order_id`, it assigns a rank (`rn`) to its status entries based on
        the timestamp, with the newest entry getting `rn = 1`.
    2.  **Final `SELECT`**: It then joins the `orders` table with this CTE. It
        selects only those orders where the latest status entry (`rn = 1`) has a
        `status` of 'pending_acceptance'.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        list[dict]: A list of order dictionaries, where each dictionary represents
                    an order to be processed. Returns an empty list if no such
                    orders are found or if an error occurs.
    """
    orders = []
    try:
        # Using DictCursor to get results as dictionaries for easier access.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                -- This CTE finds the most recent status for each order.
                WITH LatestStatus AS (
                    SELECT
                        order_id,
                        status,
                        -- The ROW_NUMBER() window function assigns a unique, sequential
                        -- integer to rows within a partition of a result set.
                        -- Here, we partition by order_id and order by timestamp descending
                        -- to find the latest status entry for each order.
                        ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY timestamp DESC) as rn
                    FROM order_status_history
                )
                -- Final query to select the orders that need processing.
                SELECT o.*
                FROM orders o
                -- Join with our CTE to get the latest status.
                JOIN LatestStatus ls ON o.order_id = ls.order_id
                -- Filter for orders where the latest status (rn=1) is 'pending_acceptance'.
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

    This function constructs the JSON payload required by the Best Buy API, which
    is a list of all order line IDs, each marked as 'accepted'.

    Args:
        api_key (str): The Best Buy API key for authorization.
        order (dict): The order dictionary, which must contain the `order_id` and
                      the `raw_order_data` (the original JSON from Best Buy).

    Returns:
        tuple: A tuple containing:
            - bool: True if the API call was successful, False otherwise.
            - dict: A dictionary with the API response status code and body.
            - dict: The payload that was sent to the API.
    """
    order_id = order['order_id']
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/accept"
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }

    # Extract the original order data to build the payload.
    order_data = order['raw_order_data']
    # The API requires a payload listing each order line to be accepted.
    order_lines_payload = [
        {"accepted": True, "id": line['order_line_id']}
        for line in order_data.get('order_lines', [])
    ]
    payload = {"order_lines": order_lines_payload}

    print(f"INFO: Attempting to accept order {order_id}...")
    try:
        # Make the API call.
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        # Raise an exception for bad status codes (4xx or 5xx).
        response.raise_for_status()
        # If successful, return the success status and the response.
        return True, {"status_code": response.status_code, "body": response.json() if response.content else {}}, payload
    except requests.exceptions.RequestException as e:
        # Handle network errors or bad responses.
        error_body = {}
        if e.response is not None:
            try:
                # Try to parse the error response as JSON.
                error_body = e.response.json()
            except json.JSONDecodeError:
                # If it's not JSON, just store the raw text.
                error_body = {"error_text": e.response.text}
        return False, {"status_code": e.response.status_code if e.response is not None else 500, "body": error_body}, payload


def validate_order_status_via_api(api_key, order_id):
    """
    Fetches the current details of an order from the Best Buy API to check its status.

    After an order is accepted, we need to poll this endpoint to confirm that
    Best Buy's system has processed the acceptance and updated the order state.

    Args:
        api_key (str): The Best Buy API key.
        order_id (str): The ID of the order to validate.

    Returns:
        tuple: A tuple containing:
            - str or None: The current `order_state` from the API (e.g., 'SHIPPING'),
                           or None if the API call fails.
            - str: The raw text of the API response.
            - int: The HTTP status code of the API response.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}"
    headers = {'Authorization': api_key}
    print(f"INFO: Validating status for order {order_id}...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        order_data = response.json()
        # Return the 'order_state' field from the response.
        return order_data.get('order_state'), response.text, response.status_code
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Could not validate status for order {order_id}. Reason: {e}")
        return None, response_text, status_code


def process_single_order(conn, api_key, order):
    """
    Orchestrates the entire acceptance and validation workflow for a single order.

    This function ties everything together: it attempts to accept the order, logs
    the attempt, and then enters a loop to validate the result.

    Args:
        conn: An active psycopg2 database connection object.
        api_key (str): The Best Buy API key.
        order (dict): The order dictionary to process.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Order: {order_id} ---")

    # ---------------------------------------------------------------------
    # Step 1: Attempt to accept the order via the API.
    # ---------------------------------------------------------------------
    is_success, api_response, payload = accept_order_via_api(api_key, order)

    # Log every API call for auditing, whether it succeeds or fails.
    log_api_call(conn, 'BestBuy', 'AcceptOrder', order_id, payload, api_response, api_response.get('status_code'), is_success)

    if not is_success:
        # If the initial API call fails, log it as a critical process failure
        # and update the order status to 'acceptance_failed' for manual review.
        details = f"Initial API call to accept order failed with status {api_response.get('status_code')}."
        log_process_failure(conn, order_id, 'OrderAcceptance', details, payload)
        add_order_status_history(conn, order_id, 'acceptance_failed', notes=details)
        return

    # ---------------------------------------------------------------------
    # Step 2: Enter the validation loop to confirm the order status.
    # ---------------------------------------------------------------------
    for attempt in range(1, MAX_VALIDATION_ATTEMPTS + 1):
        print(f"--- Validation Attempt {attempt}/{MAX_VALIDATION_ATTEMPTS} for order {order_id} ---")
        time.sleep(VALIDATION_PAUSE_SECONDS)

        # Check the order's current status via the API.
        current_status, resp_text, status_code = validate_order_status_via_api(api_key, order_id)
        log_api_call(conn, 'BestBuy', 'GetOrderStatus', order_id, None, resp_text, status_code, current_status is not None)

        # If the status is one of the expected post-acceptance states, the process
        # is successful. Update the status and exit.
        if current_status in ('WAITING_DEBIT_PAYMENT', 'SHIPPING'):
            add_order_status_history(conn, order_id, 'accepted', notes=f"Validated as '{current_status}'.")
            return

        # If the order was cancelled by Best Buy, update our status and stop.
        elif current_status == 'CANCELLED':
            add_order_status_history(conn, order_id, 'cancelled', notes="Validated as 'CANCELLED'.")
            return

        # If the status is still something else, it means the acceptance hasn't
        # fully processed yet. We will retry after a pause.
        else:
            print(f"WARNING: Order {order_id} status is still '{current_status}' after validation attempt {attempt}.")
            # If we've exhausted all attempts, log a failure.
            if attempt == MAX_VALIDATION_ATTEMPTS:
                details = f"Validation failed after {MAX_VALIDATION_ATTEMPTS} attempts. Final status was '{current_status}'."
                log_process_failure(conn, order_id, 'OrderAcceptance', details, payload)
                add_order_status_history(conn, order_id, 'acceptance_failed', notes=details)
                return


def main():
    """
    Main function to run the entire order acceptance workflow.

    This function initializes the database connection and API key, fetches the list
    of orders that need to be processed, and then iterates through them, calling
    the processing logic for each one.
    """
    print("\n--- Starting Order Acceptance Workflow v2 ---")
    conn = get_db_connection()
    api_key = get_best_buy_api_key()

    # A database connection and API key are essential. If they are missing,
    # the script cannot proceed.
    if not conn or not api_key:
        print("CRITICAL: Cannot proceed without a database connection and API key.")
        return

    # Get the list of orders to work on.
    orders_to_process = get_orders_to_accept_from_db(conn)

    if not orders_to_process:
        print("INFO: No orders are currently pending acceptance.")
    else:
        print(f"INFO: Found {len(orders_to_process)} orders to process.")
        for order in orders_to_process:
            process_single_order(conn, api_key, order)

    # Always close the database connection when done.
    conn.close()
    print("\n--- Order Acceptance Workflow Finished ---")

# =====================================================================================
# --- Script Execution ---
# =====================================================================================
# This block ensures that the 'main' function is called only when the script is
# executed directly (not when it's imported as a module).
if __name__ == '__main__':
    main()
