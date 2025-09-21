# Phase 2 (v2): Re-Architected Shipping & Tracking Workflow

This document provides a detailed breakdown of the re-architected and unified Shipping and Tracking workflow. This version introduces significant enhancements in resilience, validation, and idempotency, creating a much more robust fulfillment process.

## 1. Strategic Goal

The primary goal was to merge the previously separate shipping label creation and tracking update workflows into a single, cohesive process. This simplifies the logic, improves maintainability, and provides a clearer picture of the end-to-end fulfillment process. The new workflow also incorporates advanced resilience and validation features to prevent common errors like duplicate or incorrect shipping labels.

## 2. The New Unified Workflow

The logic for both creating shipping labels and updating tracking information on the Best Buy marketplace has been merged into a single, powerful workflow, orchestrated by `shipping/workflow.py` and `tracking/workflow.py`.

### 2.1. End-to-End Process Flow

The process is now a clear, sequential chain of events:

**Shipping Label Creation (`main_shipping.py`)**
1.  **Fetch Shippable Orders**: The workflow queries the database for orders whose most recent status in `order_status_history` is `'accepted'`. Crucially, it **excludes** any order that already has a record in the `shipments` table, making it impossible to process the same order twice.

2.  **Create Shipment Record**: As a key failsafe against duplicate labels, the first action for a valid order is to create a record in the `shipments` table. Because the `order_id` in this table is a unique key, this step would fail if another process were simultaneously trying to create a label for the same order, preventing a race condition.

3.  **Label Creation Retry Loop**: The entire process of creating a label is now wrapped in a retry loop (defaulting to 3 attempts) to handle transient network or API errors.
    -   It calls the Canada Post "Create Shipment" API with a detailed XML payload.
    -   If the call succeeds, it proceeds to download and validate the label.
    -   If any step in this process fails (the API call, the PDF download, or the content validation), the entire loop repeats from the beginning after a configured pause.
    -   If all attempts fail, a critical entry is logged to the `process_failures` table, and the order's status is updated to `'shipping_failed'` for manual review.

4.  **Advanced Content Validation (New Failsafe)**:
    -   **XML Validation**: After a successful API call, the system parses the XML response from Canada Post and compares the recipient's name and postal code against the original order data from our database. This prevents a rare but critical bug where the wrong label could be generated.
    -   **PDF Validation**: After successfully downloading the PDF label, the system uses the `PyPDF2` library to extract the text from the PDF and performs a sanity check to ensure the tracking number is present in the label's text.
    -   If either of these content validation checks fails, it is treated as a critical error. The process stops immediately for that order, a failure is logged, and the status is set to `'shipping_failed'`.

5.  **Status Update**: If all steps are successful, the order's status is updated to `label_created`.

**Tracking Update (`main_tracking.py`)**
1.  **Fetch Orders for Tracking Update**: This separate workflow queries for orders whose latest status is `'label_created'`.
2.  **Update Tracking on Best Buy**: The workflow takes the tracking number from the `shipments` table and calls the Best Buy `/tracking` endpoint to add it to the order.
3.  **Mark as Shipped**: A second API call is made to the `/ship` endpoint to mark the order as shipped, which updates the status for the end customer.
4.  **Final Status Update**: If both API calls succeed, the workflow updates the order's status in our local database to the final `'shipped'` state.

## 3. Database Schema Changes

-   **`shipments` table**: The `status` column was **removed**. The state of a shipment is now derived from the associated order's status in the `order_status_history` table. The `order_id` column also has a `UNIQUE` constraint to provide a database-level guarantee against duplicate shipments.
-   **`process_failures` table**: This new table captures critical errors from the shipping and tracking workflows, providing a centralized place for manual review.
-   **`order_status_history` table**: This table now tracks the detailed progression of an order through the shipping phase (e.g., `'accepted'` -> `'label_created'` -> `'shipped'` or `'shipping_failed'`). This provides a clear and granular audit trail.
