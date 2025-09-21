# -*- coding: utf-8 -*-
"""
================================================================================
Tracking Update Workflow (V2 - Database Driven)
================================================================================
Purpose:
----------------
This script represents the final phase of the automated order processing lifecycle.
Its job is to update the Best Buy Marketplace with the shipping information for
orders that have had a shipping label created.

This completes the "fulfillment loop" by informing the customer and Best Buy that
the order is on its way.

Key Steps:
1.  **Fetch Shipments to Update**: It queries the database to find all orders
    whose most recent status is 'label_created'. This means a shipping label
    and tracking number have been successfully generated.
2.  **Update Tracking Number**: For each of these shipments, it calls the Best Buy
    API to submit the carrier code (Canada Post) and the tracking number.
3.  **Mark as Shipped**: Immediately after successfully updating the tracking,
    it makes a second API call to Best Buy to mark the entire order as shipped.
4.  **Update Database**: It logs both API calls and, upon success, updates the
    order's status to 'shipped' in our database, marking the end of the
    automated process for this order.

This script should be scheduled to run after the shipping workflow is complete.
----------------
"""

# =====================================================================================
# --- Imports ---
# =====================================================================================
import os
import sys
import psycopg2
from psycopg2 import extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# --- Module Imports ---
from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key
# We import functions from the shipping workflow because they are also used here to interact
# with the Best Buy API. This promotes code re-use.
from shipping.workflow import update_bb_tracking_number, mark_bb_order_as_shipped


# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shipments_to_update_on_bb(conn):
    """
    Fetches shipments from the database for orders whose most recent status is 'label_created'.

    This function identifies orders that have a tracking number ready but have not yet
    been marked as 'shipped' on the Best Buy marketplace.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        list[dict]: A list of shipment dictionaries, each containing the `shipment_id`,
                    `order_id`, and `tracking_pin`.
    """
    shipments = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # This query is very similar to the ones in other workflows. It uses a CTE
            # to find the latest status for each order and then joins with the shipments
            # table to get the necessary tracking information.
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
# --- Main Workflow ---
# =====================================================================================

def main():
    """
    Main function to run the tracking update workflow.

    It fetches shipments that need updating and then iterates through them,
    calling the Best Buy API to update tracking and mark them as shipped.
    """
    print("\n--- Starting Tracking Update Workflow ---")
    conn = get_db_connection()
    bb_api_key = get_best_buy_api_key()

    if not conn or not bb_api_key:
        print("CRITICAL: Cannot proceed without DB connection and API key.")
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

            # -------------------------------------------------------------
            # Step 1: Update the tracking number on Best Buy.
            # -------------------------------------------------------------
            is_success, resp_text, status_code, payload = update_bb_tracking_number(bb_api_key, order_id, tracking_pin)
            log_api_call(conn, 'BestBuy', 'UpdateTracking', order_id, payload, resp_text, status_code, is_success)

            if not is_success:
                details = f"Failed to update tracking number on Best Buy. API returned status {status_code}."
                log_process_failure(conn, order_id, 'TrackingUpdate', details, payload)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                # Continue to the next shipment if this one fails.
                continue

            # -------------------------------------------------------------
            # Step 2: Mark the order as shipped on Best Buy.
            # -------------------------------------------------------------
            is_success, resp_text, status_code = mark_bb_order_as_shipped(bb_api_key, order_id)
            log_api_call(conn, 'BestBuy', 'MarkAsShipped', order_id, None, resp_text, status_code, is_success)

            if not is_success:
                details = f"Succeeded in updating tracking PIN, but failed to mark order as shipped. API returned status {status_code}."
                log_process_failure(conn, order_id, 'TrackingUpdate', details)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                continue

            # -------------------------------------------------------------
            # Step 3: Update our internal status to 'shipped'.
            # -------------------------------------------------------------
            add_order_status_history(conn, order_id, 'shipped', notes="Successfully marked as shipped on Best Buy.")
            print(f"SUCCESS: Order {order_id} has been fully processed and marked as shipped.")

    conn.close()
    print("\n--- Tracking Update Workflow Finished ---")
