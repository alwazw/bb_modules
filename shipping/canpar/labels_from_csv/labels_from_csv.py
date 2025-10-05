import os
import sys
import pandas as pd
import base64
from dicttoxml import dicttoxml
from xml.dom.minidom import parseString

# Add project root to Python path to allow importing the Canpar API client
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from shipping.canpar.canpar_scripts import canpar_api_client

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_CSV_PATH = os.path.join(BASE_DIR, "orders.csv")
PDF_LABELS_DIR = os.path.join(BASE_DIR, "pdf_labels")
XML_LOGS_DIR = os.path.join(BASE_DIR, "log", "xml_files")

def process_orders_from_csv():
    """
    Reads orders from a CSV, creates Canpar labels for those awaiting shipment,
    saves the labels (PDF) and API responses (XML), and updates the CSV.
    """
    try:
        # Use sep='\t' for tab-separated values and specify dtype for the tracking column
        # to avoid warnings when updating it from float (NaN) to string.
        df = pd.read_csv(ORDERS_CSV_PATH, sep='\t', dtype={'Tracking number': str})
    except FileNotFoundError:
        print(f"ERROR: The file {ORDERS_CSV_PATH} was not found.")
        return

    # Filter for orders that need processing
    orders_to_process = df[df['Status'] == 'Awaiting shipment'].copy()

    if orders_to_process.empty:
        print("INFO: No orders are currently awaiting shipment in the CSV file.")
        return

    print(f"INFO: Found {len(orders_to_process)} orders to process.")
    success_count = 0

    for index, order in orders_to_process.iterrows():
        order_number = order['Order number']
        print(f"\n--- Processing Order: {order_number} ---")

        try:
            # Map the CSV data to the format expected by the API client
            api_order_details = {
                'order_id': order_number,
                'delivery_name': f"{order['Shipping address first name']} {order['Shipping address last name']}",
                'delivery_attention': order['Details'],
                'delivery_address_1': order['Shipping address street 1'],
                'delivery_city': order['Shipping address city'],
                'delivery_province': order['Shipping address state'],
                'delivery_postal_code': order['Shipping address zip'],
                'delivery_phone': order['Shipping address phone'],
                'delivery_email': order['Shipping address email'],
                'weight': 2,  # Using a placeholder weight as before
                'declared_value': order['Total order amount incl. VAT (including shipping charges)']
            }

            # Call the Canpar API
            api_result = canpar_api_client.create_shipment(api_order_details)

            if api_result.get('success'):
                tracking_pin = api_result['shipping_id']
                pdf_label_b64 = api_result['pdf_label']

                # --- Save PDF Label ---
                if isinstance(pdf_label_b64, str):
                    pdf_label_b64 = pdf_label_b64.strip()
                pdf_label_data = base64.b64decode(pdf_label_b64)
                pdf_filename = f"{order_number}.pdf"
                pdf_filepath = os.path.join(PDF_LABELS_DIR, pdf_filename)
                with open(pdf_filepath, 'wb') as f:
                    f.write(pdf_label_data)
                print(f"SUCCESS: Saved PDF label to {pdf_filepath}")

                # --- Save XML Log ---
                xml_data = dicttoxml(api_result, custom_root='CanparAPIResponse', attr_type=False)
                dom = parseString(xml_data)
                pretty_xml = dom.toprettyxml()
                xml_filename = f"{order_number}.xml"
                xml_filepath = os.path.join(XML_LOGS_DIR, xml_filename)
                with open(xml_filepath, 'w') as f:
                    f.write(pretty_xml)
                print(f"SUCCESS: Saved XML log to {xml_filepath}")

                # --- Update DataFrame ---
                df.loc[index, 'Status'] = 'Shipped'
                df.loc[index, 'Tracking number'] = tracking_pin
                success_count += 1
            else:
                error_message = api_result.get('error', 'Unknown API error')
                print(f"ERROR: API call failed for order {order_number}. Reason: {error_message}")
                df.loc[index, 'Status'] = 'Failed'

        except Exception as e:
            print(f"ERROR: An unexpected error occurred while processing order {order_number}. Reason: {e}")
            df.loc[index, 'Status'] = 'Failed'


    # Save the updated DataFrame back to the CSV if any orders were processed successfully
    if success_count > 0:
        try:
            df.to_csv(ORDERS_CSV_PATH, index=False, sep='\t')
            print(f"\nINFO: Successfully updated {success_count} orders in {ORDERS_CSV_PATH}.")
        except Exception as e:
            print(f"ERROR: Could not save the updated CSV file. Reason: {e}")
    else:
        print("\nINFO: No orders were successfully processed. CSV file not updated.")


if __name__ == "__main__":
    process_orders_from_csv()