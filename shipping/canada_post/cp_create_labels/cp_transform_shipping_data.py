import os
import sys
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Add project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, '..', '..', '..'))
from common.utils import get_canada_post_credentials

# --- Configuration ---
LOGS_DIR_BB = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'best_buy')
LOGS_DIR_CP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logs', 'canada_post')
ORDERS_FILE = os.path.join(LOGS_DIR_BB, 'orders_pending_shipping.json')
XML_OUTPUT_DIR = os.path.join(LOGS_DIR_CP, 'create_label_xml_files')

SENDER_NAME = "VISIONVATION INC."
SENDER_COMPANY = "VISIONVATION INC."
SENDER_CONTACT_PHONE = "647-444-0848"
SENDER_ADDRESS = "133 Rock Fern Way"
SENDER_CITY = "North York"
SENDER_PROVINCE = "ON"
SENDER_POSTAL_CODE = "M2J 4N3"
SENDER_COUNTRY = "CA"


def create_xml_payload(order, contract_id, paid_by_customer):
    """ Creates the XML payload for a single order. """
    order_id = order['order_id']
    customer = order['customer']
    shipping = customer['shipping_address']
    offer_sku = order['order_lines'][0]['offer_sku']
    quantity = order['order_lines'][0]['quantity']

    shipment = ET.Element('shipment', xmlns="http://www.canadapost.ca/ws/shipment-v8")
    ET.SubElement(shipment, 'transmit-shipment').text = 'true'
    ET.SubElement(shipment, 'requested-shipping-point').text = SENDER_POSTAL_CODE.replace(" ", "")

    delivery_spec = ET.SubElement(shipment, 'delivery-spec')
    ET.SubElement(delivery_spec, 'service-code').text = 'DOM.EP'

    sender = ET.SubElement(delivery_spec, 'sender')
    ET.SubElement(sender, 'name').text = SENDER_NAME
    ET.SubElement(sender, 'company').text = SENDER_COMPANY
    ET.SubElement(sender, 'contact-phone').text = SENDER_CONTACT_PHONE
    sender_address_details = ET.SubElement(sender, 'address-details')
    ET.SubElement(sender_address_details, 'address-line-1').text = SENDER_ADDRESS
    ET.SubElement(sender_address_details, 'city').text = SENDER_CITY
    ET.SubElement(sender_address_details, 'prov-state').text = SENDER_PROVINCE
    ET.SubElement(sender_address_details, 'country-code').text = SENDER_COUNTRY
    ET.SubElement(sender_address_details, 'postal-zip-code').text = SENDER_POSTAL_CODE

    destination = ET.SubElement(delivery_spec, 'destination')
    ET.SubElement(destination, 'name').text = f"{shipping['firstname']} {shipping['lastname']}"
    ET.SubElement(destination, 'company').text = f"{quantity}x {offer_sku}"
    dest_address_details = ET.SubElement(destination, 'address-details')
    ET.SubElement(dest_address_details, 'address-line-1').text = shipping['street_1']
    ET.SubElement(dest_address_details, 'city').text = shipping['city']
    ET.SubElement(dest_address_details, 'prov-state').text = shipping['state']
    ET.SubElement(dest_address_details, 'country-code').text = 'CA'
    ET.SubElement(dest_address_details, 'postal-zip-code').text = shipping['zip_code']

    options = ET.SubElement(delivery_spec, 'options')
    option = ET.SubElement(options, 'option')
    ET.SubElement(option, 'option-code').text = 'DC'

    parcel_characteristics = ET.SubElement(delivery_spec, 'parcel-characteristics')
    ET.SubElement(parcel_characteristics, 'weight').text = '1.8'
    dimensions = ET.SubElement(parcel_characteristics, 'dimensions')
    ET.SubElement(dimensions, 'length').text = '35'
    ET.SubElement(dimensions, 'width').text = '25'
    ET.SubElement(dimensions, 'height').text = '5'

    print_preferences = ET.SubElement(delivery_spec, 'print-preferences')
    ET.SubElement(print_preferences, 'output-format').text = '4x6'

    preferences = ET.SubElement(delivery_spec, 'preferences')
    ET.SubElement(preferences, 'show-packing-instructions').text = 'true'
    ET.SubElement(preferences, 'show-postage-rate').text = 'false'
    ET.SubElement(preferences, 'show-insured-value').text = 'true'

    references = ET.SubElement(delivery_spec, 'references')
    ET.SubElement(references, 'customer-ref-1').text = order_id

    settlement_info = ET.SubElement(delivery_spec, 'settlement-info')
    ET.SubElement(settlement_info, 'paid-by-customer').text = paid_by_customer
    ET.SubElement(settlement_info, 'contract-id').text = contract_id
    ET.SubElement(settlement_info, 'intended-method-of-payment').text = 'Account'

    xml_str = ET.tostring(shipment, 'utf-8')
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def main():
    """ Main function to read orders and generate XML files. """
    print("\n--- Starting Transform Shipping Data to XML Script ---")

    _, _, _, paid_by_customer, contract_id = get_canada_post_credentials()
    if not all([paid_by_customer, contract_id]):
        return

    os.makedirs(XML_OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(ORDERS_FILE):
        print(f"ERROR: {ORDERS_FILE} not found.")
        return

    with open(ORDERS_FILE, 'r') as f:
        try:
            orders = json.load(f)
        except json.JSONDecodeError:
            print("ERROR: orders_pending_shipping.json is corrupted.")
            return
        
    if not orders:
        print("INFO: No orders found in orders_pending_shipping.json to process.")
        return

    print(f"INFO: Found {len(orders)} orders to process.")

    for order in orders:
        order_id = order['order_id']
        print(f"INFO: Processing order {order_id}...")
    
        xml_content = create_xml_payload(order, contract_id, paid_by_customer)
    
        xml_filename = os.path.join(XML_OUTPUT_DIR, f"{order_id}.xml")
        with open(xml_filename, 'w') as xml_file:
            xml_file.write(xml_content)
        
        print(f"SUCCESS: Created XML file: {xml_filename}")
    
    print("--- Transform Shipping Data to XML Script Finished ---\n")

if __name__ == '__main__':
    main()
