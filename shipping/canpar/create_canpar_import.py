import os
import sys
import pandas as pd
import json
import logging
from datetime import datetime, timedelta

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# --- Configuration ---
CANPAR_DIR = os.path.join(PROJECT_ROOT, "shipping", "canpar")
INPUT_DIR = os.path.join(CANPAR_DIR, "input")
INPUT_FILE = os.path.join(INPUT_DIR, "orders.csv")
OUTPUT_FILE = os.path.join(CANPAR_DIR, "Canpar_Import_Orders.csv")
JSON_FILE = os.path.join(CANPAR_DIR, "Canpar_Imports.json")
VLOOKUP_FILE = os.path.join(CANPAR_DIR, "vlookup.csv")
LOG_FILE = os.path.join(CANPAR_DIR, "canpar_import.log")

def setup_logging():
    """Sets up logging to file and console."""
    os.makedirs(CANPAR_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger()

def delete_previous_imports(logger):
    """Delete existing Canpar_Import_Orders.csv file."""
    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
            logger.info(f"Deleted previous import file: {OUTPUT_FILE}")
        except Exception as e:
            logger.warning(f"Could not delete {OUTPUT_FILE}: {e}")

def load_existing_records(logger):
    """Load existing records from JSON file."""
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []
    except Exception as e:
        logger.warning(f"Could not load JSON file: {e}")
        return []

def check_duplicate_orders(new_orders, existing_records, logger):
    """Check for and log orders that have already been processed."""
    existing_order_numbers = {record.get('Reference', '') for record in existing_records}
    duplicate_orders = sorted(list(set(new_orders) & existing_order_numbers))

    if duplicate_orders:
        logger.warning("=" * 80)
        logger.warning("WARNING: Shipping label may have already been created for the following orders:")
        for order in duplicate_orders:
            logger.warning(f"- {order}")
        logger.warning(f"Total duplicate orders found: {len(duplicate_orders)}")
        logger.warning("=" * 80)

def save_to_json(records, logger):
    """Save records to JSON file."""
    try:
        existing_records = load_existing_records(logger)
        existing_records.extend(records)
        with open(JSON_FILE, 'w') as f:
            json.dump(existing_records, f, indent=2)
        logger.info(f"Successfully saved {len(records)} records to {JSON_FILE}")
        logger.info(f"Total records in JSON: {len(existing_records)}")
    except Exception as e:
        logger.error(f"Could not save to JSON file: {e}")

def validate_addresses(order, logger):
    """Log any address mismatches."""
    mismatches = []
    if order.get("Shipping address first name") != order.get("Billing address first name"):
        mismatches.append("First Name")
    if order.get("Shipping address last name") != order.get("Billing address last name"):
        mismatches.append("Last Name")
    if order.get("Billing address street 1") != order.get("Shipping address street 1"):
        mismatches.append("Street 1")

    if mismatches:
        logger.warning(f"Address mismatch detected for Order number: {order['Order number']}. Fields: {', '.join(mismatches)}. Proceeding with SHIPPING address.")
    return order

def load_vlookup_mapping(logger):
    """Load the VLOOKUP mapping from vlookup.csv."""
    if not os.path.exists(VLOOKUP_FILE):
        logger.warning(f"VLOOKUP file not found at {VLOOKUP_FILE}. Proceeding without it.")
        return {}
    try:
        vlookup_df = pd.read_csv(VLOOKUP_FILE)
        return dict(zip(vlookup_df["Offer SKU"], vlookup_df["universal-offer-SKU"]))
    except Exception as e:
        logger.error(f"Error loading VLOOKUP file: {e}")
        return {}

def process_orders(logger):
    """Process orders.csv and create Canpar import file."""
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file not found: {INPUT_FILE}")
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    logger.info(f"Processing input file: {INPUT_FILE}")
    vlookup_mapping = load_vlookup_mapping(logger)
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

    existing_records = load_existing_records(logger)
    check_duplicate_orders(df["Order number"].tolist(), existing_records, logger)
    import_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    validated_orders = [validate_addresses(row.to_dict(), logger) for _, row in df.iterrows()]
    validated_df = pd.DataFrame(validated_orders)

    if vlookup_mapping:
        validated_df["Offer SKU"] = validated_df["Offer SKU"].map(vlookup_mapping).fillna(validated_df["Offer SKU"])

    shipping_template = pd.DataFrame({
        "Delivery Address ID": validated_df["Order number"],
        "Delivery Address Attention": validated_df["Quantity"].astype(str).str.strip() + "x " + validated_df["Offer SKU"].fillna("").str.strip(),
        "Delivery Address Name": validated_df["Shipping address first name"].str.strip() + " " + validated_df["Shipping address last name"].str.strip(),
        "Delivery Address Line 1": validated_df["Shipping address street 1"].str.strip(),
        "Delivery Address Line 2": validated_df["Shipping address street 2"].fillna("").str.strip(),
        "Delivery Address Line 3": validated_df["Shipping address additional information"].fillna("").str.strip(),
        "Delivery Address City": validated_df["Shipping address city"].str.strip(),
        "Delivery Address Province": validated_df["Shipping address state"].str.strip(),
        "Delivery Address Postal Code": validated_df["Shipping address zip"].str.strip(),
        "Delivery Address Country": "CA",
        "Delivery Address Phone": validated_df["Shipping address phone"].fillna("").astype(str).str.strip(),
        "Delivery Address Phone Extension": "",
        "Delivery Address Residential": "",
        "Delivery Address Email": validated_df["Shipping address email"].fillna("").str.strip(),
        "Send Email To Delivery Address": "1",
        "No Signature Required": "0",
        "Signature": "SR",
        "Service Type": "1",
        "Total Number Of Pieces": validated_df["Quantity"].astype(str).str.strip(),
        "Total Weight": "2",
        "Shipper Num": "46000041",
        "Collect Shipper Num": "",
        "Shipping Date": (datetime.now() + timedelta(days=1)).strftime("%Y%m%d"),
        "Pickup Address ID": "",
        "Pickup Address Name": "VISIONVATION INC.",
        "Pickup Address Line 1": "133 ROCK FERN WAY",
        "Pickup Address Line 2": "",
        "Pickup Address Line 3": "",
        "Pickup Address City": "NORTH YORK",
        "Pickup Address Province": "ON",
        "Pickup Address Postal Code": "M2J4N3",
        "Pickup Address Country": "CA",
        "Pickup Address Attention": "",
        "Pickup Address Phone": "6474440848",
        "Pickup Address Phone Extension": "",
        "Pickup Address Residential": "0",
        "Pickup Address Email": "WAFIC.ALWAZZAN@VISIONVATION.COM",
        "Send Email To Pickup Address": "0",
        "Premium": "N",
        "Chain Of Signature": "0",
        "Dangerous Goods": "0",
        "Instruction": "",
        "Description": "",
        "Handling": "0",
        "Handling Type": "",
        "Weight Unit": "L",
        "Dimension Unit": "l",
        "Package Length": "14",
        "Package Width": "10",
        "Package Height": "2",
        "Extra Care": "0",
        "Total Declared Value": validated_df["Total order amount incl. VAT (including shipping charges)"],
        "Reference": validated_df["Order number"],
        "Alternative Reference": "",
        "Cost Centre": "",
        "Store Num": "",
        "COD Type": "N",
        "COD Amount 1": "0",
        "Post Dated Cheque 1": "",
        "COD Amount 2": "0",
        "Post Dated Cheque 2": "",
        "COD Amount 3": "0",
        "Post Dated Cheque 3": "",
        "Box Id": ""
    })

    json_records = shipping_template.to_dict('records')
    for record in json_records:
        record['Import_Timestamp'] = import_timestamp

    delete_previous_imports(logger)
    shipping_template.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    save_to_json(json_records, logger)

    try:
        os.remove(INPUT_FILE)
        logger.info(f"Deleted input file: {INPUT_FILE}")
    except Exception as e:
        logger.warning(f"Could not delete input file: {e}")

    logger.info(f"Successfully created: {OUTPUT_FILE}")

def main():
    logger = setup_logging()
    try:
        process_orders(logger)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())