import os
import sys
import logging
from datetime import datetime

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, get_orders_by_date_range
from common.utils import get_canada_post_credentials
from shipping.canada_post.cp_tracking import get_tracking_details
from shipping.canada_post.cp_cancel_shipment import process_single_shipment_cancellation

# --- Configuration ---
LOG_DIR = os.path.join(PROJECT_ROOT, 'shipping', 'cancellation_logs')
DAYS_TO_CHECK = 30
# Canada Post event code for "Shipping label created"
LABEL_CREATED_CODE = "135"

def setup_logging():
    """Sets up a rotating log file for the cancellation workflow."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = datetime.now().strftime("cancellation_workflow_%Y-%m-%d.log")
    log_path = os.path.join(LOG_DIR, log_filename)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger()

def is_shipment_cancellable(tracking_events):
    """
    Analyzes tracking events to determine if a shipment should be cancelled.

    Criteria for cancellation:
    1. There is only one tracking event, and its code indicates that only the label has been created.
    2. Any of the tracking event descriptions contain the word "delay".
    """
    if not tracking_events:
        logging.warning("No tracking events found, cannot determine if cancellable.")
        return False, "No tracking events"

    # Check for "delay" in any event description
    for event in tracking_events:
        if 'delay' in event.get('description', '').lower():
            logging.info(f"Cancellation condition met: 'delay' found in description: '{event['description']}'")
            return True, f"Delayed in transit: {event['description']}"

    # Check if only a shipping label has been created
    if len(tracking_events) == 1:
        first_event = tracking_events[0]
        # Using a more generic check for label creation status
        if "label" in first_event.get('description', '').lower() and "created" in first_event.get('description', '').lower():
            logging.info(f"Cancellation condition met: Only a shipping label was created.")
            return True, "Label created, not yet shipped"

    logging.info("Shipment does not meet cancellation criteria.")
    return False, "In transit or delivered"

def main():
    """
    Main function to run the automated cancellation workflow.
    """
    logger = setup_logging()
    logger.info("--- Starting Automated Cancellation Workflow ---")

    conn = get_db_connection()
    cp_creds = get_canada_post_credentials()

    if not conn or not cp_creds:
        logger.critical("CRITICAL: Cannot proceed without DB connection and API credentials.")
        sys.exit(1)

    # 1. Fetch recent orders
    orders = get_orders_by_date_range(conn, days=DAYS_TO_CHECK)
    if not orders:
        logger.info(f"No orders with shipments found in the last {DAYS_TO_CHECK} days. Exiting.")
        conn.close()
        return

    logger.info(f"Found {len(orders)} orders with shipments in the last {DAYS_TO_CHECK} days.")

    cancellable_shipments = 0
    for order in orders:
        order_id = order['order_id']
        tracking_pin = order['tracking_pin']
        shipment_id = order['shipment_id']
        shipment_status = order['shipment_status']

        logger.info(f"--- Checking Order: {order_id}, Shipment ID: {shipment_id}, Tracking PIN: {tracking_pin} ---")

        if shipment_status in ['cancelled', 'refund_requested']:
            logger.info(f"Shipment {shipment_id} is already '{shipment_status}'. Skipping.")
            continue

        if not tracking_pin:
            logger.warning(f"Order {order_id} has no tracking PIN. Skipping.")
            continue

        # 2. Get tracking status
        tracking_events = get_tracking_details(conn, cp_creds, tracking_pin)

        # 3. Analyze tracking status and decide on cancellation
        should_cancel, reason = is_shipment_cancellable(tracking_events)

        if should_cancel:
            cancellable_shipments += 1
            logger.info(f"Shipment {shipment_id} for order {order_id} is cancellable. Reason: {reason}. Proceeding with cancellation.")

            # 4. Cancel the shipment
            # The process_single_shipment_cancellation function requires the full shipment details dictionary
            shipment_details = dict(order) # Convert the order DictRow to a dict
            process_single_shipment_cancellation(conn, cp_creds, shipment_details)
        else:
            logger.info(f"Shipment {shipment_id} for order {order_id} is not cancellable. Reason: {reason}.")

    # 5. Final validation and summary
    logger.info("--- Workflow Summary ---")
    logger.info(f"Total orders checked: {len(orders)}")
    logger.info(f"Total shipments identified for cancellation: {cancellable_shipments}")

    # Simple validation: re-fetch and check statuses (a more robust validation could be added)
    logger.info("--- Final Validation Step ---")
    final_orders = get_orders_by_date_range(conn, days=DAYS_TO_CHECK)
    cancelled_count = 0
    refund_requested_count = 0
    for order in final_orders:
        if order['shipment_status'] == 'cancelled':
            cancelled_count += 1
        elif order['shipment_status'] == 'refund_requested':
            refund_requested_count += 1

    logger.info(f"Validation complete. Final counts in DB: Cancelled={cancelled_count}, Refund Requested={refund_requested_count}")

    conn.close()
    logger.info("--- Automated Cancellation Workflow Finished ---")

if __name__ == '__main__':
    main()