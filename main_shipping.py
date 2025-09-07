import os
import sys
import json

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from Orders.awaiting_shipment.orders_awaiting_shipment.retrieve_pending_shipping import main as retrieve_shipping_main
from shipping.canada_post.cp_create_labels.cp_transform_shipping_data import main as transform_data_main
from shipping.canada_post.cp_shipping.cp_pdf_labels import main as create_labels_main

LOGS_DIR_CP = os.path.join(os.path.dirname(__file__), 'logs', 'canada_post')
CP_HISTORY_LOG_FILE = os.path.join(LOGS_DIR_CP, 'cp_shipping_history_log.json')
LOGS_DIR_BB = os.path.join(os.path.dirname(__file__), 'logs', 'best_buy')
PENDING_SHIPPING_FILE = os.path.join(LOGS_DIR_BB, 'orders_pending_shipping.json')


def has_label_been_created(order_id):
    """ Checks if a shipping label has already been created for a given order ID. """
    if not os.path.exists(CP_HISTORY_LOG_FILE):
        return False

    with open(CP_HISTORY_LOG_FILE, 'r') as f:
        try:
            history = json.load(f)
            for entry in history:
                # This assumes the order ID is present in the logged shipment details XML.
                # A more robust check might parse the XML to be certain.
                if order_id in entry.get("shipment_details", ""):
                    return True
        except (json.JSONDecodeError, TypeError):
            return False
    return False

def process_shippable_orders():
    """
    Orchestrates the entire shipping label creation process for orders
    that are ready for shipment and have not been processed before.
    """
    print("=============================================")
    print("===      Running Shipping Workflow        ===")
    print("=============================================")

    # First, get the latest list of shippable orders from Best Buy
    retrieve_shipping_main()

    # Now, process the orders found in the pending shipping file
    if not os.path.exists(PENDING_SHIPPING_FILE):
        print("INFO: No pending shipping file found. Nothing to process.")
        return

    with open(PENDING_SHIPPING_FILE, 'r') as f:
        try:
            orders_to_ship = json.load(f)
        except json.JSONDecodeError:
            print("ERROR: orders_pending_shipping.json is corrupted.")
            return

    if not orders_to_ship:
        print("INFO: No orders awaiting shipment.")
        return

    # Filter out orders that already have a label
    unprocessed_orders = [order for order in orders_to_ship if not has_label_been_created(order['order_id'])]

    if not unprocessed_orders:
        print("INFO: All shippable orders have already been processed.")
        return

    print(f"INFO: Found {len(unprocessed_orders)} new shippable orders to process.")

    # Temporarily overwrite the pending shipping file with only the unprocessed orders
    with open(PENDING_SHIPPING_FILE, 'w') as f:
        json.dump(unprocessed_orders, f, indent=4)

    # Now run the rest of the workflow on the filtered list
    print("\n>>> Transforming data for Canada Post...")
    transform_data_main()

    print("\n>>> Creating shipping labels...")
    create_labels_main()

    print("\n=============================================")
    print("===   Shipping Workflow Has Concluded     ===")
    print("=============================================")

if __name__ == '__main__':
    process_shippable_orders()
