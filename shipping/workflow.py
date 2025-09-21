# -*- coding: utf-8 -*-
"""
================================================================================
Shipping Workflow (V2 - Database Driven)
================================================================================
Purpose:
----------------
This script manages the third phase of the order lifecycle: creating shipping
labels for orders that have been accepted. It interacts with both our internal
database and the Canada Post API to generate shipments and retrieve labels.

The workflow is designed to be robust, with retries for API calls and validation
checks to ensure the generated labels are correct before they are used.

Key Steps:
1.  **Fetch Shippable Orders**: It queries the database to find all orders whose
    most recent status is 'accepted' and that do not already have a shipment
    record. This prevents the creation of duplicate labels.
2.  **Create Shipment Record**: For each shippable order, it first creates a
    placeholder record in the `shipments` table in our database.
3.  **Generate Canada Post Payload**: It constructs a detailed XML payload with
    sender, destination, and parcel information, formatted for the Canada Post API.
4.  **Create Shipment via API**: It sends the XML payload to the Canada Post API
    to create a shipment. This process is retried if it fails.
5.  **Validate and Download Label**: If the API call is successful, it validates
    the response XML and the downloaded PDF label to ensure the content is correct
    (e.g., matching address, tracking number present).
6.  **Update Database**: Once a label is successfully created and validated, it
    updates the corresponding `shipments` record with the tracking PIN and file
    paths and updates the order's status to 'label_created'.

This script is intended to be run as a scheduled task after the order acceptance
workflow has run.
----------------
"""

# =====================================================================================
# --- Imports ---
# =====================================================================================
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
# Ensures that modules from other project directories can be imported.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# --- Module Imports ---
from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_canada_post_credentials, get_best_buy_api_key


# =====================================================================================
# --- Configuration ---
# =====================================================================================
# API endpoint for Canada Post's RESTful services.
CP_API_URL_BASE = 'https://soa-gw.canadapost.ca/rs'
# API endpoint for Best Buy's order management.
BEST_BUY_API_URL_BASE = 'https://marketplace.bestbuy.ca/api/orders'
# Local directory where generated PDF shipping labels will be saved.
PDF_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'shipping', 'shipping_labels')
# The number of times to retry creating a shipping label if the API call fails.
MAX_LABEL_CREATION_ATTEMPTS = 3
# The number of seconds to wait between retry attempts.
RETRY_PAUSE_SECONDS = 60


# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shippable_orders_from_db(conn):
    """
    Fetches orders from the database that are ready for shipping.

    An order is considered "shippable" if its most recent status is 'accepted'
    AND it does not already have a corresponding record in the 'shipments' table.
    This prevents creating duplicate shipping labels for the same order.

    Args:
        conn: An active psycopg2 database connection object.

    Returns:
        list[dict]: A list of order dictionaries ready for shipping.
    """
    orders = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # The LEFT JOIN and "s.shipment_id IS NULL" check are crucial for idempotency.
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
                -- Use a LEFT JOIN to find orders that DON'T have a shipment record.
                LEFT JOIN shipments s ON o.order_id = s.order_id
                WHERE ls.rn = 1 AND ls.status = 'accepted' AND s.shipment_id IS NULL;
            """)
            orders = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"ERROR: Could not fetch shippable orders from database. Reason: {e}")
    return orders

def create_shipment_record(conn, order_id):
    """
    Creates an initial placeholder record in the 'shipments' table for a new shipment.
    This record will be updated later with the tracking number and label info.

    Args:
        conn: An active psycopg2 database connection object.
        order_id (str): The ID of the order for which to create a shipment record.

    Returns:
        int or None: The `shipment_id` of the newly created record, or None if
                     the operation fails. The `order_id` column has a UNIQUE
                     constraint, so this will fail if a record already exists.
    """
    shipment_id = None
    try:
        with conn.cursor() as cur:
            # The RETURNING clause gives us back the primary key of the new row.
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

def update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path):
    """
    Updates a shipment record with the tracking PIN, Canada Post API label URL,
    and the local path to the downloaded PDF.

    Args:
        conn: An active psycopg2 database connection object.
        shipment_id (int): The ID of the shipment record to update.
        tracking_pin (str): The tracking number from Canada Post.
        label_url (str): The URL to the label on the Canada Post API.
        pdf_path (str): The local file path where the PDF label was saved.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE shipments
                SET tracking_pin = %s, cp_api_label_url = %s, label_pdf_path = %s
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
# --- Content Validation & Failsafe Functions ---
# =====================================================================================

def validate_xml_content(order_data, cp_xml_response):
    """
    Compares the shipping address from the original order with the address in the
    Canada Post 'Create Shipment' response XML to ensure they match. This is a
    critical failsafe to prevent sending a package to the wrong address due to an
    API or data error.

    Args:
        order_data (dict): The `raw_order_data` from our database.
        cp_xml_response (str): The raw XML string from the Canada Post API response.

    Returns:
        bool: True if the name and postal code match, False otherwise.
    """
    try:
        # Extract details from our original order data.
        shipping_address = order_data['customer']['shipping_address']
        original_postal_code = shipping_address['zip_code'].replace(" ", "").upper()
        original_name = f"{shipping_address['firstname']} {shipping_address['lastname']}".upper()

        # Parse the XML response from Canada Post.
        root = ET.fromstring(cp_xml_response)
        ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'}
        dest = root.find(".//cp:destination", ns)
        xml_name = dest.find("cp:name", ns).text.upper()
        xml_postal_code = dest.find(".//cp:postal-zip-code", ns).text.replace(" ", "").upper()

        # Compare the key fields.
        if original_postal_code == xml_postal_code and original_name in xml_name:
            print("INFO: XML content validation successful.")
            return True
        else:
            print(f"CRITICAL VALIDATION FAILURE: XML content does not match order data.")
            print(f"  Order Name: {original_name}, XML Name: {xml_name}")
            print(f"  Order Postal: {original_postal_code}, XML Postal: {xml_postal_code}")
            return False
    except Exception as e:
        print(f"ERROR: Could not perform XML content validation. Reason: {e}")
        return False

def validate_pdf_content(pdf_path, tracking_pin):
    """
    Performs a basic sanity check on the downloaded PDF label by extracting its
    text and searching for the tracking pin. This confirms that the downloaded
    file is a valid PDF and contains the correct label information.

    Args:
        pdf_path (str): The local path to the downloaded PDF file.
        tracking_pin (str): The tracking pin to search for within the PDF text.

    Returns:
        bool: True if the tracking pin is found in the PDF, False otherwise.
    """
    try:
        # PyPDF2 is a heavy dependency, so we import it only when needed.
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        pdf_text = ""
        for page in reader.pages:
            pdf_text += page.extract_text()

        if tracking_pin in pdf_text:
            print("INFO: PDF content validation successful (tracking pin found).")
            return True
        else:
            print("CRITICAL VALIDATION FAILURE: Tracking pin not found in downloaded PDF.")
            return False
    except Exception as e:
        print(f"ERROR: Could not perform PDF content validation. Reason: {e}")
        return False

# =====================================================================================
# --- API Interaction Functions ---
# =====================================================================================

def download_label_pdf(label_url, api_user, api_password, output_path):
    """
    Downloads the shipping label PDF from the provided Canada Post URL using
    Basic Authentication.

    Args:
        label_url (str): The URL provided by the Canada Post 'Create Shipment' response.
        api_user (str): The Canada Post API username.
        api_password (str): The Canada Post API password.
        output_path (str): The local file path to save the PDF to.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    if not label_url:
        return False

    # Canada Post's label download endpoint requires Basic Authentication.
    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    headers = {
        'Accept': 'application/pdf',
        'Authorization': f'Basic {auth_b64}'
    }

    print(f"INFO: Downloading label from {label_url}...")
    try:
        response = requests.get(label_url, headers=headers, timeout=30)
        response.raise_for_status()
        # Write the binary content of the response to a file.
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"SUCCESS: Saved label to {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download label: {e}")
        return False

# --- Hardcoded Sender Information ---
# In a real application, this would likely come from a configuration file or database.
SENDER_NAME = "VISIONVATION INC."
SENDER_COMPANY = "VISIONVATION INC."
SENDER_CONTACT_PHONE = "647-444-0848"
SENDER_ADDRESS = "133 Rock Fern Way"
SENDER_CITY = "North York"
SENDER_PROVINCE = "ON"
SENDER_POSTAL_CODE = "M2J 4N3"

def create_xml_payload(order, contract_id, paid_by_customer):
    """
    Constructs the XML payload for the Canada Post 'Create Shipment' API call.

    This function builds a detailed XML structure containing all the necessary
    information for a shipment, including sender and destination addresses,
    parcel dimensions, and settlement information.

    Args:
        order (dict): The order dictionary from the database.
        contract_id (str): The Canada Post contract ID.
        paid_by_customer (str): The Canada Post customer number paying for the shipment.

    Returns:
        str: A formatted XML string to be sent to the Canada Post API.
    """
    order_data = order['raw_order_data']
    order_id = order_data['order_id']
    customer = order_data['customer']
    shipping = customer['shipping_address']
    # NOTE: This currently assumes only one item per order for simplicity.
    offer_sku = order_data['order_lines'][0]['offer_sku']
    quantity = order_data['order_lines'][0]['quantity']

    # --- Build the XML structure using xml.etree.ElementTree ---
    shipment = ET.Element('shipment', xmlns="http://www.canadapost.ca/ws/shipment-v8")
    ET.SubElement(shipment, 'transmit-shipment').text = 'true'
    ET.SubElement(shipment, 'requested-shipping-point').text = SENDER_POSTAL_CODE.replace(" ", "")

    delivery_spec = ET.SubElement(shipment, 'delivery-spec')
    ET.SubElement(delivery_spec, 'service-code').text = 'DOM.EP' # Expedited Parcel

    # --> Sender Details
    sender = ET.SubElement(delivery_spec, 'sender')
    ET.SubElement(sender, 'name').text = SENDER_NAME
    ET.SubElement(sender, 'company').text = SENDER_COMPANY
    ET.SubElement(sender, 'contact-phone').text = SENDER_CONTACT_PHONE
    sender_address = ET.SubElement(sender, 'address-details')
    ET.SubElement(sender_address, 'address-line-1').text = SENDER_ADDRESS
    ET.SubElement(sender_address, 'city').text = SENDER_CITY
    ET.SubElement(sender_address, 'prov-state').text = SENDER_PROVINCE
    ET.SubElement(sender_address, 'postal-zip-code').text = SENDER_POSTAL_CODE

    # --> Destination Details
    destination = ET.SubElement(delivery_spec, 'destination')
    ET.SubElement(destination, 'name').text = f"{shipping['firstname']} {shipping['lastname']}"
    ET.SubElement(destination, 'company').text = f"{quantity}x {offer_sku}"
    dest_address = ET.SubElement(destination, 'address-details')
    ET.SubElement(dest_address, 'address-line-1').text = shipping['street_1']
    ET.SubElement(dest_address, 'city').text = shipping['city']
    ET.SubElement(dest_address, 'prov-state').text = shipping['state']
    ET.SubElement(dest_address, 'postal-zip-code').text = shipping['zip_code']

    # --> Parcel & Options
    options = ET.SubElement(delivery_spec, 'options')
    option = ET.SubElement(options, 'option')
    ET.SubElement(option, 'option-code').text = 'DC' # Delivery Confirmation
    parcel = ET.SubElement(delivery_spec, 'parcel-characteristics')
    ET.SubElement(parcel, 'weight').text = '1.8' # kg
    dimensions = ET.SubElement(parcel, 'dimensions')
    ET.SubElement(dimensions, 'length').text = '35' # cm
    ET.SubElement(dimensions, 'width').text = '25' # cm
    ET.SubElement(dimensions, 'height').text = '5' # cm
    preferences = ET.SubElement(delivery_spec, 'preferences')
    ET.SubElement(preferences, 'show-packing-instructions').text = 'true'
    ET.SubElement(preferences, 'show-postage-rate').text = 'false'

    # --> References & Billing
    references = ET.SubElement(delivery_spec, 'references')
    ET.SubElement(references, 'customer-ref-1').text = order_id # Use our order ID as a reference
    settlement = ET.SubElement(delivery_spec, 'settlement-info')
    ET.SubElement(settlement, 'paid-by-customer').text = paid_by_customer
    ET.SubElement(settlement, 'contract-id').text = contract_id

    # Convert the XML tree to a formatted string.
    xml_str = ET.tostring(shipment, 'utf-8')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def update_bb_tracking_number(api_key, order_id, tracking_pin):
    """
    Calls the Best Buy API to update the tracking number for a given order.
    This is a distinct step from marking the order as shipped.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/tracking"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
    payload = {"carrier_code": "CPCL", "tracking_number": tracking_pin}
    print(f"INFO: Updating tracking for order {order_id} with PIN {tracking_pin}...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True, response.text, response.status_code, payload
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to update tracking for order {order_id}: {response_text}")
        return False, response_text, status_code, payload

def mark_bb_order_as_shipped(api_key, order_id):
    """
    Calls the Best Buy API to mark an order as shipped. This is the final step
    in the Best Buy workflow for an order.
    """
    url = f"{BEST_BUY_API_URL_BASE}/{order_id}/ship"
    headers = {'Authorization': api_key}
    print(f"INFO: Marking order {order_id} as shipped...")
    try:
        response = requests.put(url, headers=headers, timeout=30)
        response.raise_for_status()
        return True, response.text, response.status_code
    except requests.exceptions.RequestException as e:
        response_text = e.response.text if e.response is not None else str(e)
        status_code = e.response.status_code if e.response is not None else 500
        print(f"ERROR: Failed to mark order {order_id} as shipped: {response_text}")
        return False, response_text, status_code

# =====================================================================================
# --- Main Workflow ---
# =====================================================================================

def process_single_order_shipping(conn, cp_creds, order):
    """
    Orchestrates the entire shipping label creation and validation process for a single order.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Shipping for Order: {order_id} ---")

    # Create a placeholder in the database. This helps prevent duplicate processing.
    shipment_id = create_shipment_record(conn, order_id)
    if not shipment_id:
        details = "Failed to create initial shipment record in the database. The order might already have a shipment."
        log_process_failure(conn, order_id, 'ShippingLabelCreation', details, order)
        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
        return

    # Build the XML payload for Canada Post.
    xml_payload = create_xml_payload(order, cp_creds['contract_id'], cp_creds['paid_by_customer'])

    # --- API Call with Retry Logic ---
    for attempt in range(1, MAX_LABEL_CREATION_ATTEMPTS + 1):
        print(f"--- Label Creation Attempt {attempt}/{MAX_LABEL_CREATION_ATTEMPTS} for order {order_id} ---")
        auth_string = f"{cp_creds['api_user']}:{cp_creds['api_password']}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        cp_api_url = f'{CP_API_URL_BASE}/{cp_creds["customer_number"]}/{cp_creds["customer_number"]}/shipment'
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/vnd.cpc.shipment-v8+xml',
            'Accept': 'application/vnd.cpc.shipment-v8+xml'
        }

        try:
            response = requests.post(cp_api_url, headers=headers, data=xml_payload, timeout=30)
            response.raise_for_status()
            response_text = response.text
            status_code = response.status_code
            is_success = True
        except requests.exceptions.RequestException as e:
            response_text = e.response.text if e.response is not None else str(e)
            status_code = e.response.status_code if e.response is not None else 500
            is_success = False

        log_api_call(conn, 'CanadaPost', 'CreateShipment', order_id, xml_payload, response_text, status_code, is_success)

        if is_success:
            try:
                # --- Validation and Finalization ---
                root = ET.fromstring(response_text)
                ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'}
                label_url = root.find(".//cp:link[@rel='label']", ns).get('href')
                tracking_pin = root.find(".//cp:tracking-pin", ns).text

                os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order_id}_{timestamp}.pdf")

                if download_label_pdf(label_url, cp_creds['api_user'], cp_creds['api_password'], pdf_path) and os.path.exists(pdf_path):
                    # Perform content validation as a final check.
                    is_xml_valid = validate_xml_content(order['raw_order_data'], response_text)
                    is_pdf_valid = validate_pdf_content(pdf_path, tracking_pin)

                    if is_xml_valid and is_pdf_valid:
                        # If everything is valid, update the database and we're done with this order.
                        update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path)
                        add_order_status_history(conn, order_id, 'label_created', notes=f"Tracking PIN: {tracking_pin}")
                        print(f"SUCCESS: Label created and validated for order {order_id}.")
                        return
                    else:
                        details = "Shipping label created but content validation failed. Manual review required."
                        log_process_failure(conn, order_id, 'ShippingLabelValidation', details, order)
                        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
                        return
            except (ET.ParseError, AttributeError) as e:
                print(f"ERROR: Failed to parse successful API response. Error: {e}")

        # If we reach here, the API call failed.
        print(f"WARNING: Label creation attempt {attempt} failed for order {order_id}.")
        if attempt < MAX_LABEL_CREATION_ATTEMPTS:
            time.sleep(RETRY_PAUSE_SECONDS)
        else:
            # If all retries fail, log a critical failure.
            details = f"Failed to create and validate shipping label after {MAX_LABEL_CREATION_ATTEMPTS} attempts."
            log_process_failure(conn, order_id, 'ShippingLabelCreation', details, order)
            add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
            return

def main():
    """
    Main function to run the shipping and tracking workflows.
    """
    print("\n--- Starting Shipping & Tracking Workflow ---")
    conn = get_db_connection()
    cp_creds = get_canada_post_credentials()
    bb_api_key = get_best_buy_api_key()

    if not conn or not cp_creds or not bb_api_key:
        print("CRITICAL: Cannot proceed without DB connection and API keys.")
        return

    # --- Phase 1: Create Shipping Labels ---
    orders_to_ship = get_shippable_orders_from_db(conn)
    if not orders_to_ship:
        print("INFO: No orders are currently pending shipment.")
    else:
        print(f"INFO: Found {len(orders_to_ship)} orders to process for label creation.")
        for order in orders_to_ship:
            process_single_order_shipping(conn, cp_creds, order)

    conn.close()
    print("\n--- Shipping & Tracking Workflow Finished ---")

# This ensures the main function is called only when the script is executed directly.
if __name__ == '__main__':
    main()
