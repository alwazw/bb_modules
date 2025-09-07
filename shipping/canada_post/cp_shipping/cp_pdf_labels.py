import os
import sys
import requests
import base64
import json
from datetime import datetime
import xml.etree.ElementTree as ET

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_canada_post_credentials
from .validate_cp_shipment import get_shipment_details, get_tracking_summary

# --- Configuration ---
LOGS_DIR_BB = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'best_buy')
LOGS_DIR_CP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'canada_post')
XML_INPUT_DIR = os.path.join(LOGS_DIR_CP, 'create_label_xml_files')
PDF_OUTPUT_DIR = os.path.join(LOGS_DIR_CP, 'cp_pdf_shipping_labels')
CP_SHIPPING_DATA_FILE = os.path.join(LOGS_DIR_CP, 'cp_shipping_labels_data.json')
CP_HISTORY_LOG_FILE = os.path.join(LOGS_DIR_CP, 'cp_shipping_history_log.json')
CUSTOMER_SERVICE_CP_HISTORY_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'customer_service', 'cp_shipping_history_log.json')


def log_shipping_data(order_id, tracking_pin=None, label_url=None, api_response_text=None, error=None):
    """ Logs the shipping data to cp_shipping_labels_data.json. """
    os.makedirs(os.path.dirname(CP_SHIPPING_DATA_FILE), exist_ok=True)
    print(f"INFO: Logging shipping data for order {order_id}...")

    log_entry = {
        "order_id": order_id,
        "tracking_pin": tracking_pin,
        "label_url": label_url,
        "timestamp": datetime.now().isoformat(),
        "api_response": api_response_text,
        "error": str(error) if error else None
    }

    log_entries = []
    if os.path.exists(CP_SHIPPING_DATA_FILE):
        with open(CP_SHIPPING_DATA_FILE, 'r') as f:
            try:
                log_entries = json.load(f)
            except json.JSONDecodeError:
                print("WARNING: cp_shipping_labels_data.json is corrupted. Starting fresh.")

    log_entries.append(log_entry)

    with open(CP_SHIPPING_DATA_FILE, 'w') as f:
        json.dump(log_entries, f, indent=4)

def log_cp_history(shipment_details_xml):
    """ Appends the full shipment details XML to the history logs. """
    if not shipment_details_xml:
        return

    for log_path in [CP_HISTORY_LOG_FILE, CUSTOMER_SERVICE_CP_HISTORY_LOG_FILE]:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_entries = []
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_entries = json.load(f)
                except json.JSONDecodeError:
                    log_entries = []

        log_entries.append({
            "timestamp": datetime.now().isoformat(),
            "shipment_details": shipment_details_xml
        })

        with open(log_path, 'w') as f:
            json.dump(log_entries, f, indent=4)
        print(f"SUCCESS: Appended shipment details to {log_path}")


def create_shipment_and_get_label(api_user, api_password, customer_number, xml_content, order):
    """ Sends the request to Canada Post, logs the data, and returns the label URL. """
    order_id = order['order_id']
    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    cp_api_url = f'https://soa-gw.canadapost.ca/rs/{customer_number}/{customer_number}/shipment'

    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/vnd.cpc.shipment-v8+xml',
        'Accept': 'application/vnd.cpc.shipment-v8+xml'
    }

    print("INFO: Sending request to Canada Post 'Create Shipment' API...")
    try:
        response = requests.post(cp_api_url, headers=headers, data=xml_content)
        response.raise_for_status()
        response_text = response.text
        print("SUCCESS: 'Create Shipment' API call was successful.")
        
        label_url, details_url, tracking_pin = None, None, None
        try:
            root = ET.fromstring(response_text)
            label_link = root.find(".//{http://www.canadapost.ca/ws/shipment-v8}link[@rel='label']")
            if label_link is not None:
                label_url = label_link.get('href')

            tracking_pin_element = root.find(".//{http://www.canadapost.ca/ws/shipment-v8}tracking-pin")
            if tracking_pin_element is not None:
                tracking_pin = tracking_pin_element.text

            details_link = root.find(".//{http://www.canadapost.ca/ws/shipment-v8}link[@rel='details']")
            if details_link is not None:
                details_url = details_link.get('href')

        except ET.ParseError as e:
            print(f"ERROR: Failed to parse 'Create Shipment' response XML: {e}")
            log_shipping_data(order_id, api_response_text=response_text, error=e)
            return None, None, None

        log_shipping_data(order_id, tracking_pin, label_url, response_text)
        return label_url, details_url, tracking_pin

    except requests.exceptions.RequestException as e:
        print(f"ERROR: 'Create Shipment' API request failed: {e}")
        response_text = e.response.text if e.response else "No response from server."
        print("Response Body:", response_text)
        log_shipping_data(order_id, api_response_text=response_text, error=e)
        return None, None, None

def download_label(label_url, api_user, api_password, output_path):
    """ Downloads the shipping label PDF from the provided URL. """
    if not label_url:
        return

    auth_string = f"{api_user}:{api_password}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    headers = {
        'Accept': 'application/pdf',
        'Authorization': f'Basic {auth_b64}'
    }

    print(f"INFO: Downloading label from {label_url}...")
    try:
        response = requests.get(label_url, headers=headers)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"SUCCESS: Saved label to {output_path}")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download label: {e}")
        return False
    return True

def main():
    """ Main function to process XML files and get PDF labels. """
    print("\n--- Starting Create PDF Labels Script ---")

    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

    api_user, api_password, customer_number, _, _ = get_canada_post_credentials()
    if not all([api_user, api_password, customer_number]):
        return

    if not os.path.exists(XML_INPUT_DIR) or not os.listdir(XML_INPUT_DIR):
        print("INFO: No XML files found to process.")
        return

    xml_files = [f for f in os.listdir(XML_INPUT_DIR) if f.endswith('.xml')]
    
    print(f"INFO: Found {len(xml_files)} XML files to process.")

    orders_file_path = os.path.join(LOGS_DIR_BB, 'orders_pending_shipping.json')
    if not os.path.exists(orders_file_path):
        print(f"ERROR: {orders_file_path} not found.")
        return

    with open(orders_file_path, 'r') as f:
        all_orders = json.load(f)
    orders_map = {order['order_id']: order for order in all_orders}

    for xml_file in xml_files:
        try:
            order_id = os.path.splitext(xml_file)[0]
            xml_path = os.path.join(XML_INPUT_DIR, xml_file)
            details_url = None

            print(f"\nINFO: Processing {xml_file} for order {order_id}...")

            with open(xml_path, 'r') as f:
                xml_content = f.read()

            order_details = orders_map.get(order_id)
            if not order_details:
                print(f"WARNING: Could not find order details for {order_id}. Skipping.")
                continue

            label_url, details_url, tracking_pin = create_shipment_and_get_label(api_user, api_password, customer_number, xml_content, order_details)

            if details_url:
                shipment_details_xml = get_shipment_details(api_user, api_password, details_url)
                if shipment_details_xml:
                    log_cp_history(shipment_details_xml)

            if tracking_pin:
                import time
                print("INFO: Waiting for 30 seconds for tracking pin to become active...")
                time.sleep(30)
                is_valid_tracking = get_tracking_summary(api_user, api_password, tracking_pin)
                if not is_valid_tracking:
                    print(f"CRITICAL WARNING: Tracking PIN for order {order_id} could not be validated in real-time. Proceeding with Best Buy update.")

            if label_url:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                pdf_path = os.path.join(PDF_OUTPUT_DIR, f"{order_id}_{timestamp}.pdf")
                if not download_label(label_url, api_user, api_password, pdf_path):
                    print(f"ERROR: Failed to download label for order {order_id}. See logs for details.")
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while processing {xml_file}: {e}")
            log_shipping_data(order_id, error=e)

    print("--- Create PDF Labels Script Finished ---\n")

if __name__ == '__main__':
    main()
