import os
import sys
import requests
import base64
import xml.etree.ElementTree as ET
import psycopg2
import psycopg2.extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import (
    get_db_connection,
    log_api_call,
    add_order_status_history,
    get_shipment_details_from_db,
    get_shipments_details_by_order_id,
    get_shipment_details_by_tracking_pin,
    update_shipment_status_in_db
)
from common.utils import get_canada_post_credentials

# --- Configuration ---
CP_API_URL_BASE = 'https://soa-gw.canadapost.ca/rs'
REFUND_EMAIL = "test@example.com" # Placeholder for customer service/admin email

def void_shipment(conn, cp_creds, shipment_id, shipment_details):
    """
    Voids a Canada Post shipment that has not been transmitted.
    """
    print(f"INFO: Attempting to void shipment {shipment_id}...")
    label_url = shipment_details.get('cp_api_label_url')
    if not label_url:
        print(f"ERROR: cp_api_label_url not found for shipment {shipment_id}. Cannot void.")
        return "error"
    if "/label" in label_url:
        shipment_url = label_url.split("/label")[0]
    else:
        print(f"WARNING: Could not determine shipment URL from label URL '{label_url}'. Using it as is.")
        shipment_url = label_url

    auth_string = f"{cp_creds[0]}:{cp_creds[1]}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    headers = {
        'Accept': 'application/vnd.cpc.shipment-v8+xml',
        'Authorization': f'Basic {auth_b64}',
        'Accept-language': 'en-CA'
    }
    order_id = shipment_details.get('order_id')
    try:
        print(f"INFO: Sending DELETE request to {shipment_url}")
        response = requests.delete(shipment_url, headers=headers, timeout=30)
        log_api_call(
            conn, 'CanadaPost', 'VoidShipment', order_id,
            request_payload={'url': shipment_url},
            response_body=response.text,
            status_code=response.status_code,
            is_success=(response.status_code == 204)
        )
        if response.status_code == 204:
            print(f"SUCCESS: Shipment {shipment_id} successfully voided.")
            update_shipment_status_in_db(conn, shipment_id, 'cancelled', 'Shipment successfully voided.')
            add_order_status_history(conn, order_id, 'shipment_cancelled', notes='Shipment voided with Canada Post.')
            return "voided"
        else:
            print(f"ERROR: Received HTTP {response.status_code} when trying to void shipment {shipment_id}.")
            try:
                root = ET.fromstring(response.text)
                ns = {'cp': 'http://www.canadapost.ca/ws/messages'}
                message_code_element = root.find("cp:message/cp:code", ns)
                if message_code_element is None:
                    message_code_element = root.find("message/code")
                if message_code_element is not None:
                    message_code = message_code_element.text
                    if message_code == '8064':
                        print("INFO: Shipment has already been transmitted. A refund must be requested.")
                        return "transmitted"
                    else:
                        message_desc_element = root.find("cp:message/cp:description", ns)
                        if message_desc_element is None:
                            message_desc_element = root.find("message/description")
                        message_details = message_desc_element.text if message_desc_element is not None else "No description provided."
                        print(f"ERROR: Canada Post API Error Code: {message_code} - {message_details}")
                        notes = f"Failed to void shipment. CP Error: {message_code} - {message_details}"
                        update_shipment_status_in_db(conn, shipment_id, 'cancellation_failed', notes)
                        return "error"
                else:
                    raise AttributeError("Could not find message code in response.")
            except (ET.ParseError, AttributeError) as e:
                print(f"ERROR: Could not parse error response from Canada Post. Response: {response.text}. Error: {e}")
                update_shipment_status_in_db(conn, shipment_id, 'cancellation_failed', f"Failed to void shipment. Unparsable API response: {response.text}")
                return "error"
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error while trying to void shipment {shipment_id}: {e}")
        log_api_call(
            conn, 'CanadaPost', 'VoidShipment', order_id,
            request_payload={'url': shipment_url},
            response_body=str(e),
            status_code=500,
            is_success=False
        )
        update_shipment_status_in_db(conn, shipment_id, 'cancellation_failed', f"Network error during void: {e}")
        return "error"

def request_shipment_refund(conn, cp_creds, shipment_id, shipment_details):
    """
    Requests a refund for a Canada Post shipment that has already been transmitted.
    """
    print(f"INFO: Attempting to request refund for shipment {shipment_id}...")
    label_url = shipment_details.get('cp_api_label_url')
    if not label_url:
        print(f"ERROR: cp_api_label_url not found for shipment {shipment_id}. Cannot request refund.")
        return "error"

    if "/label" in label_url:
        shipment_url = label_url.split("/label")[0]
    else:
        shipment_url = label_url

    refund_url = f"{shipment_url}/refund"

    auth_string = f"{cp_creds[0]}:{cp_creds[1]}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    headers = {
        'Accept': 'application/vnd.cpc.shipment-v8+xml',
        'Content-Type': 'application/vnd.cpc.shipment-v8+xml',
        'Authorization': f'Basic {auth_b64}',
        'Accept-language': 'en-CA'
    }

    xml_payload = f"""
    <shipment-refund-request xmlns="http://www.canadapost.ca/ws/shipment-v8">
      <email>{REFUND_EMAIL}</email>
    </shipment-refund-request>
    """

    order_id = shipment_details.get('order_id')
    try:
        print(f"INFO: Sending POST request to {refund_url}")
        response = requests.post(refund_url, headers=headers, data=xml_payload.strip(), timeout=30)
        is_success = response.status_code == 200
        log_api_call(
            conn, 'CanadaPost', 'RequestShipmentRefund', order_id,
            request_payload={'xml_payload': xml_payload},
            response_body=response.text,
            status_code=response.status_code,
            is_success=is_success
        )
        if is_success:
            try:
                root = ET.fromstring(response.text)
                ns = {'cp': 'http://www.canadapost.ca/ws/shipment-v8'}
                ticket_id = root.find("cp:service-ticket-id", ns).text
                print(f"SUCCESS: Refund requested for shipment {shipment_id}. Service Ticket ID: {ticket_id}")
                notes = f"Refund requested. Service Ticket ID: {ticket_id}"
                update_shipment_status_in_db(conn, shipment_id, 'refund_requested', notes)
                add_order_status_history(conn, order_id, 'refund_requested', notes=notes)
                return "refund_requested"
            except (ET.ParseError, AttributeError) as e:
                print(f"ERROR: Could not parse success response from Canada Post. Response: {response.text}. Error: {e}")
                update_shipment_status_in_db(conn, shipment_id, 'cancellation_failed', f"Failed to parse refund response: {response.text}")
                return "error"
        else:
            print(f"ERROR: Received HTTP {response.status_code} when trying to request refund for shipment {shipment_id}.")
            return "error"
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error while trying to request refund for shipment {shipment_id}: {e}")
        log_api_call(
            conn, 'CanadaPost', 'RequestShipmentRefund', order_id,
            request_payload={'xml_payload': xml_payload},
            response_body=str(e),
            status_code=500,
            is_success=False
        )
        update_shipment_status_in_db(conn, shipment_id, 'cancellation_failed', f"Network error during refund request: {e}")
        return "error"

def process_single_shipment_cancellation(conn, cp_creds, shipment_details):
    """
    Processes the cancellation for a single shipment by attempting to void it,
    and if that fails because it's transmitted, requests a refund.
    """
    shipment_id = shipment_details['shipment_id']
    print(f"\n--- Processing Cancellation for Shipment ID: {shipment_id} ---")

    if shipment_details.get('status') in ['cancelled', 'refund_requested']:
        print(f"INFO: Shipment {shipment_id} is already in a '{shipment_details.get('status')}' state. Skipping.")
        return

    void_result = void_shipment(conn, cp_creds, shipment_id, shipment_details)

    if void_result == "transmitted":
        print("INFO: Shipment was transmitted, attempting to request a refund instead.")
        refund_result = request_shipment_refund(conn, cp_creds, shipment_id, shipment_details)
        if refund_result == "refund_requested":
            print(f"INFO: Shipment {shipment_id} cancellation process completed (refund requested).")
        else:
            print(f"ERROR: Failed to request refund for shipment {shipment_id}.")
    elif void_result == "voided":
        print(f"INFO: Shipment {shipment_id} was successfully cancelled (voided).")
    else:
        print(f"ERROR: Failed to cancel shipment {shipment_id}.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Cancel a Canada Post Shipment. Provide one of the following identifiers."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shipment-id", type=int, help="The database shipment_id to cancel.")
    group.add_argument("--order-id", type=str, help="The order_id to cancel all associated shipments for.")
    group.add_argument("--tracking-pin", type=str, help="The tracking_pin of the shipment to cancel.")

    args = parser.parse_args()

    conn = get_db_connection()
    cp_creds = get_canada_post_credentials()

    if not conn or not cp_creds:
        print("CRITICAL: Cannot proceed without DB connection and API credentials.")
        sys.exit(1)

    shipments_to_cancel = []
    if args.shipment_id:
        details = get_shipment_details_from_db(conn, args.shipment_id)
        if details:
            shipments_to_cancel.append(details)
        else:
            print(f"ERROR: No shipment found with ID {args.shipment_id}.")

    elif args.order_id:
        details_list = get_shipments_details_by_order_id(conn, args.order_id)
        if details_list:
            shipments_to_cancel.extend(details_list)
        else:
            print(f"ERROR: No shipments found for order ID {args.order_id}.")

    elif args.tracking_pin:
        details = get_shipment_details_by_tracking_pin(conn, args.tracking_pin)
        if details:
            shipments_to_cancel.append(details)
        else:
            print(f"ERROR: No shipment found with tracking PIN {args.tracking_pin}.")

    if not shipments_to_cancel:
        print("INFO: No shipments to cancel.")
    else:
        for shipment_details in shipments_to_cancel:
            process_single_shipment_cancellation(conn, cp_creds, shipment_details)

    conn.close()
    print("\n--- Cancellation Script Finished ---")