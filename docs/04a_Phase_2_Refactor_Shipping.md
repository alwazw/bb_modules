# Phase 2 (v2): Re-Architected Shipping & Tracking with Advanced Failsafes

This document details the re-architected Shipping and Tracking workflows. This version introduces significant enhancements in resilience and validation, creating a much more robust fulfillment process.

## 1. Strategic Goal

The goal was to enhance the existing shipping workflow with two key features requested by the user:
1.  **Resilience:** The system should be able to handle transient errors from the Canada Post API without failing completely.
2.  **Validation:** The system must verify that the shipping labels it creates are correct before the process can continue, preventing costly fulfillment errors.

## 2. The New Enhanced Workflow

The workflows in `shipping/workflow.py` and `tracking/workflow.py` have been significantly upgraded.

### 2.1. Shipping Label Creation (`shipping/workflow.py`)

1.  **Fetch Shippable Orders:** The workflow queries the database for orders whose most recent status in `order_status_history` is `'accepted'`.

2.  **Create Shipment Record:** A key failsafe against duplicate labels is creating a record in the `shipments` table *before* calling any APIs. The query in the step above naturally excludes any order that already has a shipment record, making it impossible to process the same order twice.

3.  **Label Creation Retry Loop:** The entire process of creating a label is now wrapped in a retry loop (defaulting to 3 attempts).
    -   It calls the Canada Post "Create Shipment" API.
    -   If the call succeeds, it proceeds to download and validate the label.
    -   If any step in this process fails (the API call, the PDF download, or the content validation), the entire loop repeats from the beginning.
    -   A pause between retries prevents overwhelming the API.
    -   If all attempts fail, a critical entry is logged to the `process_failures` table, and the order's status is updated to `'shipping_failed'`.

4.  **Advanced Content Validation (New Failsafe):**
    -   **XML Validation:** After a successful API call, the system now parses the XML response from Canada Post and compares the recipient's name and postal code against the original order data from our database.
    -   **PDF Validation:** After successfully downloading the PDF label, the system uses the `PyPDF2` library to extract the text from the PDF and performs a sanity check to ensure the tracking number is present in the label's text.
    -   If either of these content validation checks fails, it is treated as a critical error. The process stops immediately for that order, a failure is logged, and the status is set to `'shipping_failed'`.

5.  **Success:** Only if the API call succeeds AND the label is downloaded AND both content validations pass does the workflow update the order's status to `'label_created'`.

### 2.2. Tracking Update (`tracking/workflow.py`)

The tracking update workflow has been updated to use the new `order_status_history` and `process_failures` tables, making its logging and state management consistent with the rest of the application.

1.  **Fetch Shipments to Update:** It queries the database for orders whose latest status is `'label_created'`.
2.  **API Calls:** It calls the Best Buy `/tracking` and `/ship` endpoints sequentially.
3.  **Failure Handling:** If either API call fails, the process for that order stops, a critical failure is logged to `process_failures`, and the order status is updated to `'tracking_failed'`.
4.  **Success:** If both calls succeed, the final status is updated to `'shipped'` in the `order_status_history` table.

## 3. Database Schema Changes

-   **`shipments` table:** The `status` column was **removed**. The state of a shipment is now derived from the associated order's status in the `order_status_history` table.
-   **`process_failures` table:** This new table captures critical errors from the shipping and tracking workflows, providing a centralized place for manual review.
-   **`order_status_history` table:** This table now tracks the detailed progression of an order through the shipping phase (e.g., `'accepted'` -> `'label_created'` -> `'shipped'` or `'shipping_failed'`).
