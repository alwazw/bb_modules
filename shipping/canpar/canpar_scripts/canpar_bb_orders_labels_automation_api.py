import os
import sys
import json
import base64
from datetime import datetime

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

import requests
from common.utils import get_best_buy_api_key

# Import local and project-level modules
from shipping.canpar.canpar_scripts import canpar_db_utils, canpar_api_client
from database.db_utils import get_db_connection, add_order_status_history, log_process_failure

# --- Configuration ---
LABELS_DIR = os.path.join(PROJECT_ROOT, "shipping", "canpar", "canpar_output_files", "canpar_shipping_labels_pdf")
BEST_BUY_API_URL = 'https://marketplace.bestbuy.ca/api/orders'

def setup_directories():
    """Ensure that the directory for saving PDF labels exists."""
    os.makedirs(LABELS_DIR, exist_ok=True)

def update_best_buy_order_status(order_id, tracking_pin):
    """
    Updates the order status on Best Buy Marketplace to 'shipped' and provides a tracking number.
    """
    api_key = get_best_buy_api_key()
    if not api_key:
        raise Exception("Best Buy API key is missing.")

    # The endpoint to accept an order line is different from shipping.
    # This is a common pattern: first accept, then ship.
    # We will assume for now the orders are already accepted.
    shipping_url = f"{BEST_BUY_API_URL}/{order_id}/ship"

    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}

    # This payload structure is based on typical marketplace API requirements.
    # It assumes we ship all lines of the order at once.
    payload = {
        "shipments": [{
            "carrier_code": "CPAR",
            "tracking_number": tracking_pin
            # In a more complex scenario, we might specify order_lines here.
        }]
    }

    # NOTE: The actual API call is commented out for development.
    # try:
    #     response = requests.put(shipping_url, headers=headers, json=payload)
    #     response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
    #     print(f"SUCCESS: Marked order {order_id} as shipped on Best Buy.")
    #     return True
    # except requests.exceptions.RequestException as e:
    #     error_message = f"Failed to update Best Buy for order {order_id}. Status: {e.response.status_code}, Body: {e.response.text}"
    #     raise Exception(error_message)

    print(f"MOCKING API CALL to ship order {order_id} with tracking {tracking_pin} and carrier CPAR.")
    return True


def process_single_order(order, conn):
    """
    Processes a single order to create a Canpar shipping label and update Best Buy.
    """
    order_id = order['order_id']
    print(f"--- Processing Order: {order_id} ---")

    try:
        # 1. Extract and map order data
        order_data = order['raw_order_data']
        customer_info = order_data.get('customer', {})
        shipping_info = customer_info.get('shipping_address', {})
        order_lines = order_data.get('order_lines', [])

        api_order_details = {
            'order_id': order_id,
            'delivery_name': f"{shipping_info.get('firstname', '')} {shipping_info.get('lastname', '')}",
            'delivery_attention': ", ".join([f"{line.get('quantity')}x {line.get('offer_sku')}" for line in order_lines]),
            'delivery_address_1': shipping_info.get('street_1'),
            'delivery_city': shipping_info.get('city'),
            'delivery_province': shipping_info.get('state'),
            'delivery_postal_code': shipping_info.get('zip_code'),
            'delivery_phone': shipping_info.get('phone'),
            'delivery_email': customer_info.get('email', ''),
            'weight': 2, 'declared_value': order_data.get('total_price', 0)
        }

        # 2. Call Canpar API
        api_result = canpar_api_client.create_shipment(api_order_details)
        if not api_result.get('success'):
            raise Exception(api_result.get('error', 'Unknown API error'))

        # 3. Save PDF label
        tracking_pin = api_result['shipping_id']
        pdf_label_data = base64.b64decode(api_result['pdf_label'])
        label_filename = f"{order_id}_{tracking_pin}.pdf"
        label_filepath = os.path.join(LABELS_DIR, label_filename)
        with open(label_filepath, 'wb') as f:
            f.write(pdf_label_data)
        print(f"SUCCESS: Saved shipping label to {label_filepath}")

        # 4. Update local database (label created)
        shipment_id = canpar_db_utils.create_canpar_shipment(order_id, tracking_pin, label_filepath)
        if not shipment_id:
            raise Exception("Failed to create shipment record in the database.")
        add_order_status_history(conn, order_id, 'label_created', f'Canpar label created. Tracking: {tracking_pin}')

        # 5. Update Best Buy Marketplace
        update_best_buy_order_status(order_id, tracking_pin)

        # 6. Update local database (shipped)
        add_order_status_history(conn, order_id, 'shipped', f'Order marked as shipped on Best Buy. Carrier: CPAR, Tracking: {tracking_pin}')

        print(f"SUCCESS: Order {order_id} processed and shipped successfully.")
        return True

    except Exception as e:
        error_details = f"Failed to process order {order_id}. Reason: {e}"
        print(f"ERROR: {error_details}")
        log_process_failure(get_db_connection(), order_id, 'CanparLabelCreation', error_details, order)
        conn.rollback()
        return False

def main():
    """
    Main function to orchestrate the shipping label creation process.
    """
    print("\n--- Starting Canpar Shipping Label Automation ---")
    setup_directories()

    orders_to_process = canpar_db_utils.get_orders_ready_for_shipping()

    if not orders_to_process:
        print("INFO: No orders are currently ready for shipping.")
        print("--- Automation Finished ---")
        return

    print(f"INFO: Found {len(orders_to_process)} orders to process.")

    success_count = 0
    failure_count = 0
    conn = get_db_connection()

    if not conn:
        print("CRITICAL: Could not connect to the database. Aborting.")
        return

    try:
        for order in orders_to_process:
            if process_single_order(order, conn):
                conn.commit()
                success_count += 1
            else:
                # The rollback is handled within process_single_order
                failure_count += 1
    finally:
        if conn:
            conn.close()

    print("\n--- Automation Summary ---")
    print(f"Successfully processed: {success_count} orders")
    print(f"Failed to process: {failure_count} orders")
    print("--- Automation Finished ---\n")

if __name__ == "__main__":
    main()