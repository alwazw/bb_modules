import os
import sys
import json
import time
import base64
import requests
import psycopg2
from datetime import datetime
from psycopg2 import extras

# --- Project Path Setup ---
# Adjust the path to go up four levels to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_best_buy_api_key
from shipping.canpar import api as canpar_api

# --- Configuration ---
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'
# Updated PDF output directory to match the new structure
PDF_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'shipping', 'canpar', 'output', 'labels')
MAX_LABEL_CREATION_ATTEMPTS = 3
RETRY_PAUSE_SECONDS = 60

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shippable_orders_from_db(conn):
    """
    Fetches orders whose most recent status is 'accepted' and have no associated shipments.
    """
    orders = []
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
                SELECT o.*
                FROM orders o
                JOIN LatestStatus ls ON o.order_id = ls.order_id
                WHERE ls.rn = 1 AND ls.status = 'accepted'
                AND NOT EXISTS (SELECT 1 FROM shipments s WHERE s.order_id = o.order_id);
            """)
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shippable orders from database. Reason: {e}")
    return orders

def create_shipment_record(conn, order_id):
    """
    Creates an initial record in the 'shipments' table for a new shipment.
    """
    shipment_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shipments (order_id) VALUES (%s) RETURNING shipment_id;",
                (order_id,)
            )
            shipment_id = cur.fetchone()[0]
        conn.commit()
        print(f"INFO: Created shipment record for order {order_id} with shipment_id {shipment_id}.")
    except Exception as e:
        print(f"ERROR: Could not create shipment record for order {order_id}. Reason: {e}")
        conn.rollback()
    return shipment_id

def update_shipment_with_label_info(conn, shipment_id, tracking_pin, pdf_path):
    """
    Updates a shipment record with the tracking PIN and label PDF path.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE shipments
                SET tracking_pin = %s, label_pdf_path = %s
                WHERE shipment_id = %s;
                """,
                (tracking_pin, pdf_path, shipment_id)
            )
        conn.commit()
        print(f"INFO: Updated shipment {shipment_id} with tracking PIN and label info.")
    except Exception as e:
        print(f"ERROR: Could not update shipment {shipment_id}. Reason: {e}")
        conn.rollback()


# =====================================================================================
# --- API Interaction Functions ---
# =====================================================================================

def update_bb_tracking_number(api_key, order_id, tracking_pin):
    """
    Calls the Best Buy API to update the tracking number for a given order.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/tracking"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    payload = {"carrier_code": "CANPAR-EXPRESS", "tracking_number": tracking_pin}
    print(f"INFO: Updating tracking for order {order_id} with PIN {tracking_pin}...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        log_api_call(None, 'BestBuy', 'UpdateTracking', order_id, payload, response.text, response.status_code, True)
        return True
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to update tracking for order {order_id}: {response_text}")
        log_api_call(None, 'BestBuy', 'UpdateTracking', order_id, payload, response_text, status_code, False)
        return False

def mark_bb_order_as_shipped(api_key, order_id):
    """
    Calls the Best Buy API to mark an order as shipped.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/ship"
    headers = {'Authorization': api_key}
    print(f"INFO: Marking order {order_id} as shipped...")
    try:
        response = requests.put(url, headers=headers, timeout=30)
        response.raise_for_status()
        log_api_call(None, 'BestBuy', 'MarkAsShipped', order_id, None, response.text, response.status_code, True)
        return True
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to mark order {order_id} as shipped: {response_text}")
        log_api_call(None, 'BestBuy', 'MarkAsShipped', order_id, None, response_text, status_code, False)
        return False

# =====================================================================================
# --- Main Workflow ---
# =====================================================================================

def process_order(conn, canpar_client, bb_api_key, order, num_packages=1):
    """
    Orchestrates the shipping label creation process for a single order using Canpar.
    Can create multiple labels for a single order if it's shipped in multiple packages.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Canpar Shipping for Order: {order_id} ({num_packages} package(s)) ---")

    canpar_result = None
    for attempt in range(1, MAX_LABEL_CREATION_ATTEMPTS + 1):
        print(f"--- Canpar Shipment Creation Attempt {attempt}/{MAX_LABEL_CREATION_ATTEMPTS} for order {order_id} ---")
        canpar_result = canpar_api.create_shipment(canpar_client, order, num_packages=num_packages)
        log_api_call(conn, 'Canpar', 'ProcessShipment', order_id, canpar_result.get('raw_request', {}), canpar_result.get('raw_response', {}), 200 if canpar_result.get('success') else 500, canpar_result.get('success'))

        if canpar_result and canpar_result.get('success'):
            break

        print(f"WARNING: Canpar shipment creation attempt {attempt} failed. Reason: {canpar_result.get('error', 'Unknown')}")
        if attempt < MAX_LABEL_CREATION_ATTEMPTS:
            time.sleep(RETRY_PAUSE_SECONDS)

    if not canpar_result or not canpar_result.get('success'):
        details = f"Failed to create Canpar shipment after {MAX_LABEL_CREATION_ATTEMPTS} attempts."
        log_process_failure(conn, order_id, 'ShippingLabelCreation', details, canpar_result)
        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
        return

    canpar_shipment_id = canpar_result['shipment_id']
    packages = canpar_result.get('packages', [])
    print(f"SUCCESS: Created Canpar shipment for order {order_id}. Canpar ID: {canpar_shipment_id} with {len(packages)} packages.")

    label_result = canpar_api.get_shipping_label(canpar_client, canpar_shipment_id)
    if not label_result.get('success') or not label_result.get('labels'):
        details = f"Failed to retrieve Canpar labels. Reason: {label_result.get('error', 'Unknown')}"
        log_process_failure(conn, order_id, 'ShippingLabelCreation', details, label_result)
        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
        return

    labels_b64 = label_result['labels']
    if len(labels_b64) != len(packages):
        details = f"Mismatch between number of packages ({len(packages)}) and labels ({len(labels_b64)})."
        log_process_failure(conn, order_id, 'ShippingLabelCreation', details, label_result)
        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
        return

    all_tracking_numbers = []
    for package_info, label_data_b64 in zip(packages, labels_b64):
        tracking_number = package_info['tracking_number']
        all_tracking_numbers.append(tracking_number)

        db_shipment_id = create_shipment_record(conn, order_id)
        if not db_shipment_id:
            print(f"ERROR: Failed to create DB shipment record for tracking number {tracking_number}.")
            continue

        try:
            label_pdf_data = base64.b64decode(label_data_b64)
            os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order_id}_{tracking_number}_{timestamp}.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(label_pdf_data)

            if not os.path.exists(pdf_path):
                raise IOError("Failed to save label PDF to disk.")

            print(f"SUCCESS: Saved Canpar label to {pdf_path} for tracking {tracking_number}")
            update_shipment_with_label_info(conn, db_shipment_id, tracking_number, pdf_path)
            add_order_status_history(conn, order_id, 'label_created', notes=f"Package tracking: {tracking_number}")

        except (IOError, TypeError) as e:
            details = f"Failed to save label for tracking {tracking_number}. Reason: {e}"
            print(f"ERROR: {details}")
            log_process_failure(conn, order_id, 'ShippingLabelCreation', {"error": details}, {})
            add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
            continue

    if not all_tracking_numbers:
        print(f"ERROR: No tracking numbers were generated for order {order_id}. Aborting Best Buy update.")
        return

    first_tracking_number = all_tracking_numbers[0]
    print(f"INFO: Updating Best Buy for order {order_id} with primary tracking number {first_tracking_number}.")

    if update_bb_tracking_number(bb_api_key, order_id, first_tracking_number):
        add_order_status_history(conn, order_id, 'tracking_updated', notes=f"Best Buy tracking updated with {first_tracking_number}. Total packages: {len(all_tracking_numbers)}.")
        if mark_bb_order_as_shipped(bb_api_key, order_id):
            add_order_status_history(conn, order_id, 'shipped', notes="Marked as shipped in Best Buy.")
            print(f"SUCCESS: Order {order_id} fully processed and marked as shipped.")
        else:
            notes = "Failed to mark order as shipped in Best Buy. Manual intervention required."
            add_order_status_history(conn, order_id, 'shipping_failed', notes=notes)
            log_process_failure(conn, order_id, 'MarkAsShipped', {"error": notes}, order)
    else:
        notes = "Failed to update tracking number in Best Buy. Manual intervention required."
        add_order_status_history(conn, order_id, 'shipping_failed', notes=notes)
        log_process_failure(conn, order_id, 'UpdateTracking', {"error": notes}, order)


def main():
    """
    Main function to run the shipping and tracking workflows.
    """
    print("\n--- Starting Canpar Pending Order Processing ---")
    conn = get_db_connection()
    bb_api_key = get_best_buy_api_key()
    canpar_client = canpar_api.get_canpar_client()

    if not all([conn, bb_api_key, canpar_client]):
        print("CRITICAL: Cannot proceed without DB connection, Best Buy API key, and Canpar client.")
        if conn:
            conn.close()
        return

    orders_to_ship = get_shippable_orders_from_db(conn)
    if not orders_to_ship:
        print("INFO: No orders are currently pending shipment.")
    else:
        print(f"INFO: Found {len(orders_to_ship)} orders to process for label creation.")
        for order in orders_to_ship:
            # This can be parameterized if needed, e.g., from a command-line argument
            # or a configuration file. For now, it defaults to one package.
            process_order(conn, canpar_client, bb_api_key, order, num_packages=1)

    conn.close()
    print("\n--- Canpar Pending Order Processing Finished ---")

if __name__ == '__main__':
    main()