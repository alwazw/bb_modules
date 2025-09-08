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
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection, log_api_call, add_order_status_history, log_process_failure
from common.utils import get_canada_post_credentials

# --- Configuration ---
CP_API_URL_BASE = 'https://soa-gw.canadapost.ca/rs'
PDF_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'shipping', 'shipping_labels')
MAX_LABEL_CREATION_ATTEMPTS = 3
RETRY_PAUSE_SECONDS = 60

# =====================================================================================
# --- Database Interaction Functions ---
# =====================================================================================

def get_shippable_orders_from_db(conn):
    """
    Fetches orders whose most recent status is 'accepted'.
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
                WHERE ls.rn = 1 AND ls.status = 'accepted';
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

def update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path):
    """
    Updates a shipment record with the tracking PIN and label URLs.
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
    Canada Post 'Create Shipment' response XML to ensure they match.

    Args:
        order_data (dict): The raw order data from our database.
        cp_xml_response (str): The XML response text from Canada Post.

    Returns:
        bool: True if key address fields match, False otherwise.
    """
    try:
        # Normalize original data
        shipping_address = order_data['customer']['shipping_address']
        original_postal_code = shipping_address['zip_code'].replace(" ", "").upper()
        original_name = f"{shipping_address['firstname']} {shipping_address['lastname']}".upper()

        # Parse XML and get destination data
        root = ET.fromstring(cp_xml_response)
        ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'}
        dest = root.find(".//cp:destination", ns)
        xml_name = dest.find("cp:name", ns).text.upper()
        xml_postal_code = dest.find(".//cp:postal-zip-code", ns).text.replace(" ", "").upper()

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
    text and searching for the tracking pin.

    Args:
        pdf_path (str): The local path to the downloaded PDF file.
        tracking_pin (str): The tracking pin to search for.

    Returns:
        bool: True if the tracking pin is found in the PDF text, False otherwise.
    """
    try:
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
# --- Core Workflow & API Interaction ---
# =====================================================================================

def download_label_pdf(label_url, api_user, api_password, output_path):
    """
    Downloads the shipping label PDF from the provided Canada Post URL.
    """
    # ... (This function remains unchanged)
    if not label_url:
        return False
    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    headers = {'Accept': 'application/pdf', 'Authorization': f'Basic {auth_b64}'}
    print(f"INFO: Downloading label from {label_url}...")
    try:
        response = requests.get(label_url, headers=headers, timeout=30)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"SUCCESS: Saved label to {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download label: {e}")
        return False

# ... (create_xml_payload and sender constants remain unchanged)
SENDER_NAME = "VISIONVATION INC."
SENDER_COMPANY = "VISIONVATION INC."
SENDER_CONTACT_PHONE = "647-444-0848"
SENDER_ADDRESS = "133 Rock Fern Way"
SENDER_CITY = "North York"
SENDER_PROVINCE = "ON"
SENDER_POSTAL_CODE = "M2J 4N3"

def create_xml_payload(order, contract_id, paid_by_customer):
    order_data = order['raw_order_data']
    order_id = order_data['order_id']
    customer = order_data['customer']
    shipping = customer['shipping_address']
    offer_sku = order_data['order_lines'][0]['offer_sku']
    quantity = order_data['order_lines'][0]['quantity']
    shipment = ET.Element('shipment', xmlns="http://www.canadapost.ca/ws/shipment-v8")
    ET.SubElement(shipment, 'transmit-shipment').text = 'true'
    ET.SubElement(shipment, 'requested-shipping-point').text = SENDER_POSTAL_CODE.replace(" ", "")
    delivery_spec = ET.SubElement(shipment, 'delivery-spec')
    ET.SubElement(delivery_spec, 'service-code').text = 'DOM.EP'
    sender = ET.SubElement(delivery_spec, 'sender')
    ET.SubElement(sender, 'name').text = SENDER_NAME
    ET.SubElement(sender, 'company').text = SENDER_COMPANY
    ET.SubElement(sender, 'contact-phone').text = SENDER_CONTACT_PHONE
    sender_address = ET.SubElement(sender, 'address-details')
    ET.SubElement(sender_address, 'address-line-1').text = SENDER_ADDRESS
    ET.SubElement(sender_address, 'city').text = SENDER_CITY
    ET.SubElement(sender_address, 'prov-state').text = SENDER_PROVINCE
    ET.SubElement(sender_address, 'postal-zip-code').text = SENDER_POSTAL_CODE
    destination = ET.SubElement(delivery_spec, 'destination')
    ET.SubElement(destination, 'name').text = f"{shipping['firstname']} {shipping['lastname']}"
    ET.SubElement(destination, 'company').text = f"{quantity}x {offer_sku}"
    dest_address = ET.SubElement(destination, 'address-details')
    ET.SubElement(dest_address, 'address-line-1').text = shipping['street_1']
    ET.SubElement(dest_address, 'city').text = shipping['city']
    ET.SubElement(dest_address, 'prov-state').text = shipping['state']
    ET.SubElement(dest_address, 'postal-zip-code').text = shipping['zip_code']
    options = ET.SubElement(delivery_spec, 'options')
    option = ET.SubElement(options, 'option')
    ET.SubElement(option, 'option-code').text = 'DC'
    parcel = ET.SubElement(delivery_spec, 'parcel-characteristics')
    ET.SubElement(parcel, 'weight').text = '1.8'
    dimensions = ET.SubElement(parcel, 'dimensions')
    ET.SubElement(dimensions, 'length').text = '35'
    ET.SubElement(dimensions, 'width').text = '25'
    ET.SubElement(dimensions, 'height').text = '5'
    preferences = ET.SubElement(delivery_spec, 'preferences')
    ET.SubElement(preferences, 'show-packing-instructions').text = 'true'
    ET.SubElement(preferences, 'show-postage-rate').text = 'false'
    references = ET.SubElement(delivery_spec, 'references')
    ET.SubElement(references, 'customer-ref-1').text = order_id
    settlement = ET.SubElement(delivery_spec, 'settlement-info')
    ET.SubElement(settlement, 'paid-by-customer').text = paid_by_customer
    ET.SubElement(settlement, 'contract-id').text = contract_id
    xml_str = ET.tostring(shipment, 'utf-8')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def process_single_order_shipping(conn, api_user, api_password, customer_number, contract_id, paid_by_customer, order):
    """
    Orchestrates the entire shipping label creation process for a single order,
    including API calls, logging, validation, and retries.
    """
    order_id = order['order_id']
    print(f"\n--- Processing Shipping for Order: {order_id} ---")

    # Create the shipment record. This implicitly prevents duplicate processing
    # because the get_shippable_orders_from_db query excludes orders that already
    # have a shipment record.
    shipment_id = create_shipment_record(conn, order_id)
    if not shipment_id:
        details = "Failed to create initial shipment record in the database."
        log_process_failure(conn, order_id, 'ShippingLabelCreation', details, order)
        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
        return

    xml_payload = create_xml_payload(order, contract_id, paid_by_customer)

    for attempt in range(1, MAX_LABEL_CREATION_ATTEMPTS + 1):
        print(f"--- Label Creation Attempt {attempt}/{MAX_LABEL_CREATION_ATTEMPTS} for order {order_id} ---")

        # Call CP API
        auth_string = f"{api_user}:{api_password}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        cp_api_url = f'{CP_API_URL_BASE}/{customer_number}/{customer_number}/shipment'
        headers = {'Authorization': f'Basic {auth_b64}', 'Content-Type': 'application/vnd.cpc.shipment-v8+xml', 'Accept': 'application/vnd.cpc.shipment-v8+xml'}

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
                root = ET.fromstring(response_text)
                ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'}
                label_url = root.find(".//cp:link[@rel='label']", ns).get('href')
                tracking_pin = root.find(".//cp:tracking-pin", ns).text

                os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order_id}_{timestamp}.pdf")

                if download_label_pdf(label_url, api_user, api_password, pdf_path) and os.path.exists(pdf_path):
                    # --- V2 Enhancement: Content Validation Failsafes ---
                    is_xml_valid = validate_xml_content(order['raw_order_data'], response_text)
                    is_pdf_valid = validate_pdf_content(pdf_path, tracking_pin)

                    if is_xml_valid and is_pdf_valid:
                        # Only if all validations pass, we finalize the process.
                        update_shipment_with_label_info(conn, shipment_id, tracking_pin, label_url, pdf_path)
                        add_order_status_history(conn, order_id, 'label_created', notes=f"Tracking PIN: {tracking_pin}")
                        print(f"SUCCESS: Label created and validated for order {order_id}.")
                        return # Success, exit the loop and function
                    else:
                        # If content validation fails, this is a critical error.
                        details = "Shipping label created but content validation failed. Manual review required."
                        log_process_failure(conn, order_id, 'ShippingLabelValidation', details, order)
                        add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
                        return # Stop processing this order

            except (ET.ParseError, AttributeError) as e:
                print(f"ERROR: Failed to parse successful API response. Error: {e}")
                # Fall through to retry logic

        # If we're here, something failed.
        print(f"WARNING: Label creation attempt {attempt} failed for order {order_id}.")
        if attempt < MAX_LABEL_CREATION_ATTEMPTS:
            time.sleep(RETRY_PAUSE_SECONDS)
        else:
            details = f"Failed to create and validate shipping label after {MAX_LABEL_CREATION_ATTEMPTS} attempts."
            log_process_failure(conn, order_id, 'ShippingLabelCreation', details, order)
            add_order_status_history(conn, order_id, 'shipping_failed', notes=details)
            return

def main():
    """
    Main function to run the shipping label creation workflow.
    """
    print("\n--- Starting Shipping Label Creation Workflow v2 ---")
    conn = get_db_connection()
    api_user, api_password, customer_number, paid_by_customer, contract_id = get_canada_post_credentials()

    if not all([conn, api_user, api_password, customer_number, paid_by_customer, contract_id]):
        return

    orders_to_ship = get_shippable_orders_from_db(conn)

    if not orders_to_ship:
        print("INFO: No orders are currently pending shipment.")
    else:
        print(f"INFO: Found {len(orders_to_ship)} orders to process.")
        for order in orders_to_ship:
            process_single_order_shipping(conn, api_user, api_password, customer_number, contract_id, paid_by_customer, order)

    conn.close()
    print("\n--- Shipping Label Creation Workflow Finished ---")

if __name__ == '__main__':
    main()
