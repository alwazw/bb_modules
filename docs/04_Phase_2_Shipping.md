# Phase 2: Shipping Label Creation

This phase handles the creation of Canada Post shipping labels for orders that are ready for shipment.

## Orchestrator

-   `main_shipping.py`: This script orchestrates the shipping workflow. It now includes a failsafe to prevent the creation of duplicate labels.

## Scripts

1.  **`Orders/awaiting_shipment/orders_awaiting_shipment/retrieve_pending_shipping.py`**
    -   **Purpose:** Retrieves all orders with the status `SHIPPING` from the Best Buy API.
    -   **Output:** Saves the retrieved orders to `logs/best_buy/orders_pending_shipping.json`.

2.  **`shipping/canada_post/cp_create_labels/cp_transform_shipping_data.py`**
    -   **Purpose:** Reads the `orders_pending_shipping.json` file and transforms the order data into the required XML format for the Canada Post API.
    -   **Output:** Creates one `.xml` file for each order in `logs/canada_post/create_label_xml_files/`.

3.  **`shipping/canada_post/cp_shipping/cp_pdf_labels.py`**
    -   **Purpose:** Processes the generated XML files. For each file, it calls the Canada Post "Create Shipment" API to generate a real, billable shipping label. It then downloads the 4x6 PDF label.
    -   **Output:**
        -   Saves the PDF label to `logs/canada_post/cp_pdf_shipping_labels/` with a unique `{order_id}_{timestamp}.pdf` filename.
        -   Logs the raw API responses to `logs/canada_post/cp_shipping_labels_data.json`.

4.  **`shipping/canada_post/cp_shipping/validate_cp_shipment.py`**
    -   **Purpose:** Contains functions to validate the newly created shipment.
    -   `get_shipment_details`: Fetches the full shipment details from Canada Post and logs them to history files.
    -   `get_tracking_summary`: Makes a call to the public tracking API to confirm the tracking PIN is active. This provides a strong guarantee that the shipment is real.
