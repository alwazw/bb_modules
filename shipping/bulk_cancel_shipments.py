import os
import sys
import pandas as pd
import argparse

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import (
    get_db_connection,
    get_shipment_details_from_db,
    get_shipments_details_by_order_id,
    get_shipment_details_by_tracking_pin
)
from common.utils import get_canada_post_credentials
from shipping.canada_post.cp_cancel_shipment import process_single_shipment_cancellation

def read_identifiers_from_file(file_path, column_name):
    """
    Reads a column of identifiers from a CSV or XLSX file.
    """
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return None

    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            print("ERROR: Unsupported file format. Please use a .csv or .xlsx file.")
            return None

        if column_name not in df.columns:
            print(f"ERROR: Column '{column_name}' not found in the file.")
            return None

        return df[column_name].dropna().unique().tolist()
    except Exception as e:
        print(f"ERROR: Failed to read or process the file. Reason: {e}")
        return None

def main():
    """
    Main function to run the bulk cancellation workflow.
    """
    parser = argparse.ArgumentParser(description="Bulk cancel Canada Post shipments from a file.")
    parser.add_argument("file_path", type=str, help="Path to the CSV or XLSX file containing the identifiers.")
    parser.add_argument(
        "identifier_type",
        choices=['shipment_id', 'order_id', 'tracking_pin'],
        help="The type of identifier in the file."
    )
    parser.add_argument(
        "--column",
        type=str,
        default='identifier',
        help="The name of the column containing the identifiers (default: 'identifier')."
    )
    args = parser.parse_args()

    identifiers = read_identifiers_from_file(args.file_path, args.column)
    if identifiers is None:
        sys.exit(1)

    conn = get_db_connection()
    cp_creds = get_canada_post_credentials()

    if not conn or not cp_creds:
        print("CRITICAL: Cannot proceed without DB connection and API credentials.")
        sys.exit(1)

    print(f"--- Starting Bulk Cancellation for {len(identifiers)} unique identifiers from {args.file_path} ---")

    for identifier in identifiers:
        shipments_to_cancel = []
        if args.identifier_type == 'shipment_id':
            details = get_shipment_details_from_db(conn, identifier)
            if details:
                shipments_to_cancel.append(details)
        elif args.identifier_type == 'order_id':
            shipments_to_cancel.extend(get_shipments_details_by_order_id(conn, identifier))
        elif args.identifier_type == 'tracking_pin':
            details = get_shipment_details_by_tracking_pin(conn, identifier)
            if details:
                shipments_to_cancel.append(details)

        if not shipments_to_cancel:
            print(f"INFO: No shipments found for identifier '{identifier}'.")
            continue

        for shipment_details in shipments_to_cancel:
            process_single_shipment_cancellation(conn, cp_creds, shipment_details)

    conn.close()
    print("\n--- Bulk Cancellation Script Finished ---")

if __name__ == '__main__':
    main()