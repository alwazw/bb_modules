import os
import sys
import json
import time
import base64
import requests
import psycopg2
import xml.etree.ElementTree as ET
from datetime import datetime
from psycopg2 import extras
from xml.dom import minidom

# --- Project Path Setup ---
# Ensures the script can import modules from the parent directory (e.g., 'database').
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call
from common.utils import get_canada_post_credentials

# --- Configuration ---
CP_API_URL_BASE = 'https://soa-gw.canadapost.ca/rs'
# Defines a dedicated directory for storing the downloaded PDF shipping labels.
PDF_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'shipping', 'shipping_labels')

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shippable_orders_from_db(conn):
    """
    Fetches orders that are ready for shipment from the database.

    An order is considered "shippable" if its status is 'accepted' and it does not
    already have an associated entry in the 'shipments' table. This check is crucial
    to prevent creating duplicate shipments for the same order.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        A list of order dictionaries, ready for processing.
    """
    orders = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # A LEFT JOIN is used to find orders that do not have a matching shipment.
            # If an order has a shipment, s.shipment_id will be NOT NULL, and the
            # order will be excluded by the WHERE clause.
            cur.execute("""
                SELECT o.*
                FROM orders o
                LEFT JOIN shipments s ON o.order_id = s.order_id
                WHERE o.status = 'accepted' AND s.shipment_id IS NULL;
            """)
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shippable orders from database. Reason: {e}")
    return orders

def create_shipment_record(conn, order_id, status):
    """
    Creates an initial record in the 'shipments' table for a new shipment.
    This serves as a placeholder and is updated as the workflow progresses.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the order to create a shipment for.
        status (str): The initial status, e.g., 'label_creation_initiated'.

    Returns:
        The integer ID of the new shipment record, or None on failure.
    """
    shipment_id = None
    try:
        with conn.cursor() as cur:
            # 'RETURNING shipment_id' is an efficient way to get the primary key of
            # the newly inserted row without needing a separate SELECT query.
            cur.execute(
                "INSERT INTO shipments (order_id, status) VALUES (%s, %s) RETURNING shipment_id;",
                (order_id, status)
            )
            shipment_id = cur.fetchone()[0]
        conn.commit()
        print(f"INFO: Created shipment record for order {order_id} with shipment_id {shipment_id}.")
    except Exception as e:
        print(f"ERROR: Could not create shipment record for order {order_id}. Reason: {e}")
        conn.rollback()
    return shipment_id


def update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path):
    """
    Updates a shipment record with the tracking PIN and label info after a successful API call.
    It also updates the shipment's status to 'label_created', marking it as ready for the next phase.

    Args:
        conn: An active psycopg2 database connection object.
        shipment_id (int): The ID of the shipment to update.
        tracking_pin (str): The tracking number from Canada Post.
        label_url (str): The API URL to download the label PDF.
        pdf_path (str): The local path where the PDF was saved.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE shipments
                SET tracking_pin = %s, cp_api_label_url = %s, label_pdf_path = %s, status = 'label_created'
                WHERE shipment_id = %s;
                """,
                (tracking_pin, label_url, pdf_path, shipment_id)
            )
        conn.commit()
        print(f"INFO: Updated shipment {shipment_id} with tracking PIN and label info.")
    except Exception as e:
        print(f"ERROR: Could not update shipment {shipment_id}. Reason: {e}")
        conn.rollback()


# =====================================================================================
# --- Core Workflow & API Interaction ---
# =====================================================================================

def download_label_pdf(label_url, api_user, api_password, output_path):
    """
    Downloads the shipping label PDF from the provided Canada Post URL.
    This requires a separate, authenticated GET request.

    Args:
        label_url (str): The URL from the 'Create Shipment' API response.
        api_user/api_password (str): Credentials for authentication.
        output_path (str): The local file path to save the PDF to.

    Returns:
        True if download was successful, False otherwise.
    """
    if not label_url:
        return False

    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    # The 'Accept' header is crucial to tell the CP API we want the PDF format.
    headers = {'Accept': 'application/pdf', 'Authorization': f'Basic {auth_b64}'}

    print(f"INFO: Downloading label from {label_url}...")
    try:
        response = requests.get(label_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Open the output file in write-binary ('wb') mode to save the PDF content.
        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"SUCCESS: Saved label to {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download label: {e}")
        return False

# --- Hardcoded Sender Information ---
# In a production system, this should be moved to a configuration file or database table.
SENDER_NAME = "VISIONVATION INC."
SENDER_COMPANY = "VISIONVATION INC."
SENDER_CONTACT_PHONE = "647-444-0848"
SENDER_ADDRESS = "133 Rock Fern Way"
SENDER_CITY = "North York"
SENDER_PROVINCE = "ON"
SENDER_POSTAL_CODE = "M2J 4N3"

def create_xml_payload(order, contract_id, paid_by_customer):
    """
    Creates the Canada Post 'Create Shipment' XML payload for a single order.

    This function dynamically builds the XML structure required by the API,
    populating it with sender data (hardcoded) and customer/destination data
    extracted from the order's raw JSON data.

    Args:
        order (dict): The order record from the database.
        contract_id (str): The Canada Post contract ID.
        paid_by_customer (str): The customer number paying for the shipment.

    Returns:
        A formatted XML string ready to be sent to the API.
    """
    order_data = order['raw_order_data']
    order_id = order_data['order_id']
    customer = order_data['customer']
    shipping = customer['shipping_address']
    # The original logic only considered the first order line. This could be
    # enhanced in the future to handle multiple packages for multi-line orders.
    offer_sku = order_data['order_lines'][0]['offer_sku']
    quantity = order_data['order_lines'][0]['quantity']

    # Define the root element with the correct namespace.
    shipment = ET.Element('shipment', xmlns="http://www.canadapost.ca/ws/shipment-v8")
    # This flag tells CP to create a real, billable shipment.
    ET.SubElement(shipment, 'transmit-shipment').text = 'true'
    ET.SubElement(shipment, 'requested-shipping-point').text = SENDER_POSTAL_CODE.replace(" ", "")

    delivery_spec = ET.SubElement(shipment, 'delivery-spec')
    ET.SubElement(delivery_spec, 'service-code').text = 'DOM.EP' # Expedited Parcel

    # --- Sender Details ---
    sender = ET.SubElement(delivery_spec, 'sender')
    ET.SubElement(sender, 'name').text = SENDER_NAME
    ET.SubElement(sender, 'company').text = SENDER_COMPANY
    ET.SubElement(sender, 'contact-phone').text = SENDER_CONTACT_PHONE
    sender_address = ET.SubElement(sender, 'address-details')
    ET.SubElement(sender_address, 'address-line-1').text = SENDER_ADDRESS
    ET.SubElement(sender_address, 'city').text = SENDER_CITY
    ET.SubElement(sender_address, 'prov-state').text = SENDER_PROVINCE
    ET.SubElement(sender_address, 'postal-zip-code').text = SENDER_POSTAL_CODE

    # --- Destination Details ---
    destination = ET.SubElement(delivery_spec, 'destination')
    ET.SubElement(destination, 'name').text = f"{shipping['firstname']} {shipping['lastname']}"
    # The 'company' field is used here to store item info, which will appear on the label.
    ET.SubElement(destination, 'company').text = f"{quantity}x {offer_sku}"
    dest_address = ET.SubElement(destination, 'address-details')
    ET.SubElement(dest_address, 'address-line-1').text = shipping['street_1']
    ET.SubElement(dest_address, 'city').text = shipping['city']
    ET.SubElement(dest_address, 'prov-state').text = shipping['state']
    ET.SubElement(dest_address, 'postal-zip-code').text = shipping['zip_code']

    # --- Parcel & Options ---
    options = ET.SubElement(delivery_spec, 'options')
    option = ET.SubElement(options, 'option')
    ET.SubElement(option, 'option-code').text = 'DC' # Delivery Confirmation

    parcel = ET.SubElement(delivery_spec, 'parcel-characteristics')
    ET.SubElement(parcel, 'weight').text = '1.8' # Default weight, can be parameterized later.
    dimensions = ET.SubElement(parcel, 'dimensions')
    ET.SubElement(dimensions, 'length').text = '35'
    ET.SubElement(dimensions, 'width').text = '25'
    ET.SubElement(dimensions, 'height').text = '5'

    preferences = ET.SubElement(delivery_spec, 'preferences')
    ET.SubElement(preferences, 'show-packing-instructions').text = 'true'
    ET.SubElement(preferences, 'show-postage-rate').text = 'false'

    references = ET.SubElement(delivery_spec, 'references')
    ET.SubElement(references, 'customer-ref-1').text = order_id # Link the shipment to our order_id.

    # --- Billing Details ---
    settlement = ET.SubElement(delivery_spec, 'settlement-info')
    ET.SubElement(settlement, 'paid-by-customer').text = paid_by_customer
    ET.SubElement(settlement, 'contract-id').text = contract_id

    # Use minidom to pretty-print the XML for better readability in logs.
    xml_str = ET.tostring(shipment, 'utf-8')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def create_cp_shipment_and_download_label(conn, api_user, api_password, customer_number, xml_payload, order):
    """
    Orchestrates the process of creating a Canada Post shipment, logging the interaction,
    and downloading the resulting PDF label.

    Args:
        conn: An active psycopg2 database connection object.
        ... (api credentials) ...
        xml_payload (str): The fully formed XML request for the 'Create Shipment' API.
        order (dict): The order object.

    Returns:
        The tracking PIN if successful, otherwise None.
    """
    order_id = order['order_id']

    # 1. Create an initial record in the database to represent this shipment attempt.
    shipment_id = create_shipment_record(conn, order_id, 'label_creation_initiated')
    if not shipment_id:
        return None

    # 2. Authenticate and call the Canada Post 'Create Shipment' API.
    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    cp_api_url = f'{CP_API_URL_BASE}/{customer_number}/{customer_number}/shipment'
    # The headers are specific to the Canada Post API contract for creating shipments.
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/vnd.cpc.shipment-v8+xml',
        'Accept': 'application/vnd.cpc.shipment-v8+xml'
    }

    print(f"INFO: Sending 'Create Shipment' request for order {order_id}...")
    try:
        response = requests.post(cp_api_url, headers=headers, data=xml_payload, timeout=30)
        response.raise_for_status()
        response_text = response.text
        is_success = True
        print("SUCCESS: 'Create Shipment' API call was successful.")
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        is_success = False
        print(f"ERROR: 'Create Shipment' API request failed: {response_text}")

    # 3. Log the API interaction to our generic logging table for auditing.
    # Get status_code from the successful response if it exists, otherwise it's from the exception.
    status_code_to_log = response.status_code if is_success else status_code
    log_api_call(
        conn=conn,
        service='CanadaPost',
        endpoint='CreateShipment',
        related_id=order_id,
        request_payload=xml_payload, # Store the exact XML sent
        response_body=response_text, # Store the exact response
        status_code=status_code_to_log,
        is_success=is_success
    )

    if not is_success:
        return None

    # 4. Parse the successful XML response to find the label URL and tracking PIN.
    try:
        root = ET.fromstring(response_text)
        ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'} # Namespace for XPath
        label_url = root.find(".//cp:link[@rel='label']", ns).get('href')
        tracking_pin = root.find(".//cp:tracking-pin", ns).text
    except (ET.ParseError, AttributeError) as e:
        print(f"ERROR: Failed to parse 'Create Shipment' response XML for order {order_id}. Error: {e}")
        return None

    # 5. Download the PDF Label from the extracted URL.
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order_id}_{timestamp}.pdf")

    is_download_success = download_label_pdf(label_url, api_user, api_password, pdf_path)

    if not is_download_success:
        # If download fails, we still have the tracking PIN and the URL, so we log
        # a warning but don't halt the process. The label can be downloaded later.
        print(f"WARNING: Label PDF download failed for order {order_id}.")

    # 6. Update the shipment record in our database with all the final information.
    update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path)

    return tracking_pin


def main():
    """
    Main function to run the shipping label creation workflow.
    """
    print("\n--- Starting Shipping Label Creation Workflow ---")
    conn = get_db_connection()
    # Unpack all credentials, including the contract_id and paid_by_customer.
    api_user, api_password, customer_number, paid_by_customer, contract_id = get_canada_post_credentials()

    if not all([conn, api_user, api_password, customer_number, paid_by_customer, contract_id]):
        print("CRITICAL: Cannot proceed without DB connection and full Canada Post credentials.")
        return

    orders_to_ship = get_shippable_orders_from_db(conn)

    if not orders_to_ship:
        print("INFO: No orders are currently pending shipment.")
    else:
        print(f"INFO: Found {len(orders_to_ship)} orders to process.")
        for order in orders_to_ship:
            print(f"\n--- Processing Order: {order['order_id']} ---")

            # 1. Generate the XML payload for the current order.
            xml_payload = create_xml_payload(order, contract_id, paid_by_customer)

            # 2. Pass the generated XML to the main shipment creation function.
            tracking_pin = create_cp_shipment_and_download_label(
                conn, api_user, api_password, customer_number, xml_payload, order
            )

            if tracking_pin:
                print(f"SUCCESS: Successfully created label for order {order['order_id']} with tracking PIN {tracking_pin}.")
                # TODO: Trigger the next phase (tracking update)
            else:
                print(f"FAILURE: Failed to create label for order {order['order_id']}.")

    conn.close()
    print("\n--- Shipping Label Creation Workflow Finished ---")

if __name__ == '__main__':
    main()
