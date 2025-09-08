# Phase 2 (Refactored): Database-Driven Shipping & Tracking

This document provides a detailed breakdown of the refactored Shipping and Tracking workflows. This second phase of the order lifecycle is responsible for the physical fulfillment of an order: creating a shipping label and then communicating that information back to the customer via the Best Buy platform.

## 1. Strategic Goal

The refactoring of this phase continues the work started in Phase 1, moving all logic and state management from scattered scripts and JSON files into the centralized PostgreSQL database.

-   **Transactional Integrity:** Creating a shipment, logging the API calls, and updating the order status are now part of a clear, transactional process. The database ensures that we have a complete record of every step.
-   **Decoupled Workflows:** The process is broken into two distinct, independently runnable workflows:
    1.  **Shipping Label Creation:** Generates labels for all shippable orders.
    2.  **Tracking Update:** Updates Best Buy with tracking information for all orders that have a label.
    This separation makes the system more resilient; a failure in the Best Buy tracking update API will not prevent new shipping labels from being created.
-   **Centralized Auditing:** All API calls to both Canada Post and Best Buy are now logged in a single, generic `api_calls` table, providing a powerful, unified audit trail for all external communications.

## 2. The New Workflows

### 2.1. Shipping Label Creation (`shipping/workflow.py`)

This workflow is responsible for creating shipping labels for orders that are ready to be fulfilled.

1.  **Fetch Shippable Orders:** The workflow queries the database for all orders with a status of `'accepted'` that do not yet have a corresponding record in the `shipments` table. This prevents duplicate labels from ever being created.
2.  **Create Shipment Record:** For each order, it first creates a new row in the `shipments` table with a status of `'label_creation_initiated'`. This immediately marks the order as "in-process" for shipping.
3.  **Generate XML Payload:** It dynamically constructs the detailed XML payload required by the Canada Post "Create Shipment" API, using customer data from the `orders` table.
4.  **Call Canada Post API:** It sends the XML payload to the Canada Post API.
5.  **Log API Call:** The full request and response (success or failure) of the API call are logged to the `api_calls` table.
6.  **Process Response:** If the call was successful, it parses the XML response to extract the **Tracking PIN** and the **PDF Label URL**.
7.  **Download PDF Label:** It makes a second authenticated API call to the provided URL to download the PDF shipping label and saves it to the `shipping/shipping_labels` directory.
8.  **Update Shipment Record:** Finally, it updates the `shipments` record with the tracking PIN, the PDF URL, the local file path, and sets the status to `'label_created'`.

At the end of this workflow, we have a tracking number and a PDF label for the order, and the database has a complete record of the entire process.

### 2.2. Tracking Update (`tracking/workflow.py`)

This workflow completes the cycle by communicating the shipping information back to Best Buy.

1.  **Fetch Shipments to Update:** The workflow queries the database for all shipments with a status of `'label_created'`. This identifies all orders that have a label but have not yet been updated on Best Buy.
2.  **Update Tracking Number:** For each shipment, it makes an API call to the Best Buy `/tracking` endpoint to submit the tracking PIN and carrier code. The result is logged to the `api_calls` table.
3.  **Mark as Shipped:** If the tracking update was successful, it makes a second API call to the `/ship` endpoint. This is the final step that typically triggers customer notifications. This call is also logged.
4.  **Update Internal Statuses:** If both API calls were successful, the workflow updates the status of the `shipments` record to `'tracking_updated'` and, most importantly, updates the main `orders` record status to `'shipped'`.

## 3. Database Schema Extensions

### `shipments` Table
-   **Purpose:** A central table to track the state of fulfillment for each order.
-   **Columns:**
    -   `shipment_id` (PK): A unique internal ID for the shipment.
    -   `order_id` (FK, UNIQUE): Links the shipment to a single order. The UNIQUE constraint ensures one shipment per order.
    -   `tracking_pin` (UNIQUE): The Canada Post tracking number.
    -   `status`: The internal status of the shipment (`label_creation_initiated`, `label_created`, `tracking_updated`).
    -   `label_pdf_path`: The local filesystem path to the saved PDF label.
    -   `cp_api_label_url`: The URL from Canada Post to re-download the label if needed.

### `api_calls` Table (Generic)
-   **Purpose:** A generic, unified table to log *all* third-party API interactions for complete auditability.
-   **Columns:**
    -   `call_id` (PK): A unique ID for the log entry.
    -   `service`: The service being called (e.g., `'BestBuy'`, `'CanadaPost'`).
    -   `endpoint`: The specific action or endpoint (e.g., `'CreateShipment'`, `'UpdateTracking'`).
    -   `related_id`: An identifier to link the call to an object, like an `order_id`.
    -   `request_payload` (JSONB): The request body sent. For XML, this is stored as a string within the JSON.
    -   `response_body` (TEXT): The raw response, accommodating both JSON and XML.
    -   `status_code`: The HTTP status code of the response.
    -   `is_success`: A boolean indicating if the call was successful.
