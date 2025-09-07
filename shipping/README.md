# Shipping Module

This module is responsible for handling all shipping-related tasks, including creating shipping labels, tracking shipments, and validating addresses.

## Canada Post Integration

The `shipping/canada_post` directory contains the integration with the Canada Post API.

### `cp_pdf_labels.py`

This script is used to create shipping labels and download them as PDF files.

**How it works:**

1.  The script reads XML files from the `logs/canada_post/create_label_xml_files` directory.
2.  For each XML file, it sends a request to the Canada Post "Create Shipment" API.
3.  If the request is successful, it parses the XML response to get the label URL, details URL, and tracking pin.
4.  It logs the shipping data to `logs/canada_post/cp_shipping_labels_data.json` and the full shipment details to `logs/canada_post/cp_shipping_history_log.json` and `logs/customer_service/cp_shipping_history_log.json`.
5.  It downloads the PDF label from the label URL and saves it to the `logs/canada_post/cp_pdf_shipping_labels` directory.

**How to run:**

To run the script, execute the following command from the project root:

```bash
python3 shipping/canada_post/cp_shipping/cp_pdf_labels.py
```

**Troubleshooting:**

*   **PDFs not being saved:** Check the logs in the `logs/canada_post` directory for any errors. Make sure that the `label_url` is being returned from the Canada Post API and that the `download_label` function is not failing.
*   **XML log not complete:** Check the `cp_shipping_labels_data.json` file to see the API responses from Canada Post. If there are errors, the `details_url` might not be returned, and the shipment details will not be logged.

### `validate_cp_shipment.py`

This script is used to validate tracking numbers with the Canada Post API.

**How it works:**

The `get_tracking_summary` function sends a request to the Canada Post "Get Tracking Summary" API and returns the tracking information.

## Fulfillment Service Integration

The `fulfillment_service` uses the `shipping` module to generate shipping labels when a fulfillment is finalized. See the `fulfillment_service/README.md` for more details.
