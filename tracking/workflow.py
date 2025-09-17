import os
import sys
import psycopg2
from psycopg2 import extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key
from shipping.workflow import update_bb_tracking_number, mark_bb_order_as_shipped

def get_shipments_to_update_on_bb(conn):
    """
    Fetches shipments for orders whose most recent status is 'label_created'.
    """
    shipments = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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

def main():
    """
    Main function to run the tracking update workflow.
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
            is_success, resp_text, status_code, payload = update_bb_tracking_number(bb_api_key, order_id, tracking_pin)
            log_api_call(conn, 'BestBuy', 'UpdateTracking', order_id, payload, resp_text, status_code, is_success)
            if not is_success:
                details = f"Failed to update tracking number on Best Buy. API returned status {status_code}."
                log_process_failure(conn, order_id, 'TrackingUpdate', details, payload)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                continue
            is_success, resp_text, status_code = mark_bb_order_as_shipped(bb_api_key, order_id)
            log_api_call(conn, 'BestBuy', 'MarkAsShipped', order_id, None, resp_text, status_code, is_success)
            if not is_success:
                details = f"Succeeded in updating tracking PIN, but failed to mark order as shipped. API returned status {status_code}."
                log_process_failure(conn, order_id, 'TrackingUpdate', details)
                add_order_status_history(conn, order_id, 'tracking_failed', notes=details)
                continue
            add_order_status_history(conn, order_id, 'shipped', notes="Successfully marked as shipped on Best Buy.")
            print(f"SUCCESS: Order {order_id} has been fully processed and marked as shipped.")

    conn.close()
    print("\n--- Tracking Update Workflow Finished ---")
