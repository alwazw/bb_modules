import os
import json
from datetime import datetime

# --- Path Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ORDERS_FILE = os.path.join(PROJECT_ROOT, 'Orders', 'pending_acceptance', 'orders_pending_acceptance', 'pending_acceptance.json')
PRODUCTS_FILE = os.path.join(PROJECT_ROOT, 'catalogue', 'products.json')
PDF_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'logs', 'canada_post', 'cp_pdf_shipping_labels')


# --- Import from other project modules ---
# This is a bit tricky with Python's pathing. We need to add the project root to the sys.path
# to ensure these imports work correctly when the app is run.
import sys
sys.path.insert(0, PROJECT_ROOT)
from common.utils import get_canada_post_credentials
from shipping.canada_post.cp_create_labels.cp_transform_shipping_data import create_xml_payload
from shipping.canada_post.cp_shipping.cp_pdf_labels import create_shipment_and_get_label, download_label


# --- Data Loading ---
def load_json_file(file_path):
    """Loads a JSON file and returns its content."""
    if not os.path.exists(file_path):
        print(f"WARNING: Data file not found: {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode JSON from {file_path}")
        return None

# --- Core Business Logic ---

def get_work_order_details(order_id):
    """
    Retrieves the full order and the component map for a work order.
    """
    orders = load_json_file(ORDERS_FILE)
    products = load_json_file(PRODUCTS_FILE)

    if not orders or not products:
        return None, "Could not load necessary data files."

    order = find_order_by_id(orders, order_id)
    if not order:
        return None, f"Order ID '{order_id}' not found in pending shipments."

    offer_sku = order.get('order_lines', [{}])[0].get('offer_sku')
    product_variant = find_product_by_sku(products, offer_sku)

    if not product_variant:
        return None, f"Product with SKU '{offer_sku}' not found in catalogue."

    component_map = product_variant.get('barcodes', {})

    work_order_data = {
        "order": order,
        "required_components": {v: k for k, v in component_map.items()} # barcode -> component_name
    }
    return work_order_data, None


def generate_shipping_label(order):
    """
    Generates a shipping label for the given order and returns the tracking number.
    """
    print(f"INFO: Generating shipping label for order {order['order_id']}...")
    api_user, api_password, customer_number, paid_by_customer, contract_id = get_canada_post_credentials()

    if not all([api_user, api_password, customer_number, paid_by_customer, contract_id]):
        return None, "Missing Canada Post credentials. Cannot generate label."

    xml_content = create_xml_payload(order, contract_id, paid_by_customer)
    label_url, _, tracking_pin = create_shipment_and_get_label(api_user, api_password, customer_number, xml_content, order)

    if not label_url or not tracking_pin:
        return None, "Failed to create shipment via Canada Post API."

    print(f"SUCCESS: Shipping label created with Tracking PIN: {tracking_pin}")

    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order['order_id']}_{timestamp}.pdf")
    download_label(label_url, api_user, api_password, pdf_path)

    if not os.path.exists(pdf_path):
        return None, "Failed to download shipping label PDF."

    return {"tracking_pin": tracking_pin, "pdf_path": pdf_path}, None


def find_order_by_id(orders, order_id):
    """Finds an order in a list of orders by its ID."""
    for order in orders:
        if order.get('order_id') == order_id:
            return order
    return None

def find_product_by_sku(products, sku):
    """Finds a product variant by its SKU."""
    for product in products:
        for variant in product.get('variants', []):
            if variant.get('sku') == sku:
                return variant
    return None
