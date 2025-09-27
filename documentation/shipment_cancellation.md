# Shipment Cancellation Guide

This document provides a comprehensive guide to the shipment cancellation functionality within the Canada Post integration. It covers the core logic of how cancellations are handled and provides detailed instructions for using the available scripts.

## 1. Cancellation Logic: Void vs. Refund

When a shipping label needs to be cancelled, there are two possible actions depending on the shipment's status with Canada Post:

-   **Void Shipment**: This action is used for shipping labels that have been created and printed but **have not yet been transmitted** to Canada Post in a manifest. A successful void operation immediately cancels the label, and it cannot be used.

-   **Request Shipment Refund**: This action is required for labels that **have already been transmitted** to Canada Post. Since the shipment is already in Canada Post's system, a formal refund request must be submitted. This process is not instantaneous and is subject to approval by Canada Post. A service ticket ID is generated to track the refund request.

The cancellation scripts automatically handle this logic. They will first attempt to void the shipment. If the API returns an error indicating the shipment has already been transmitted (Error `8064`), the script will automatically proceed to request a refund.

## 2. Single Shipment Cancellation

The `shipping/canada_post/cp_cancel_shipment.py` script is used to cancel one or more labels associated with a single identifier.

### Usage

The script must be run with one of the following mutually exclusive arguments:

-   `--shipment-id`: Cancels a single shipment by its unique database ID.
-   `--order-id`: Cancels all shipments associated with a given order ID.
-   `--tracking-pin`: Cancels a single shipment by its Canada Post tracking number.

### Examples

**Cancel by Shipment ID:**
```bash
python shipping/canada_post/cp_cancel_shipment.py --shipment-id 101
```

**Cancel all shipments for an Order ID:**
```bash
python shipping/canada_post/cp_cancel_shipment.py --order-id "ORDER-123"
```

**Cancel by Tracking PIN:**
```bash
python shipping/canada_post/cp_cancel_shipment.py --tracking-pin "123456789012"
```

## 3. Bulk Shipment Cancellation

The `shipping/bulk_cancel_shipments.py` script is used to cancel multiple shipments from a CSV or XLSX file.

### Input File Format

The script requires a file (`.csv` or `.xlsx`) containing a column with the identifiers of the shipments to be cancelled.

-   By default, the script looks for a column named `identifier`.
-   You can specify a different column name using the `--column` argument.

**Example CSV (`cancellations.csv`):**
```csv
identifier
ORDER-001
ORDER-002
123456789012
```

### Usage

The script requires three arguments:
1.  `file_path`: The path to the input file.
2.  `identifier_type`: The type of identifiers in the file (`shipment_id`, `order_id`, or `tracking_pin`).
3.  `--column` (optional): The name of the column containing the identifiers. Defaults to `identifier`.

### Examples

**Bulk cancel using `order_id` from a CSV file:**
```bash
python shipping/bulk_cancel_shipments.py cancellations.csv order_id
```

**Bulk cancel using `tracking_pin` from an XLSX file with a custom column name:**
```bash
python shipping/bulk_cancel_shipments.py cancellations.xlsx tracking_pin --column "TrackingNumber"
```

## 4. Dependencies

Ensure the necessary Python packages are installed by running:
```bash
pip install -r shipping/requirements.txt
```
This will install `psycopg2-binary`, `requests`, `pandas`, and `openpyxl`.