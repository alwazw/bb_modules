# Fulfillment Service

This service provides a robust, API-driven system for managing the laptop fulfillment process. It ensures assembly accuracy through barcode validation and integrates with shipping providers to generate labels only after a successful build.

## Project Description

The Fulfillment Service is designed to eliminate assembly errors and shipping label mix-ups. It achieves this by creating a digital, stateful process that guides a technician through two main stages:

1.  **Guided Assembly:** The service exposes an API to start a fulfillment session for an order. It validates each component's barcode in real-time against the specific requirements of the order.
2.  **Validated Packaging:** Once all components are successfully validated, the service can be triggered to generate the correct shipping label, ensuring the right product gets the right label.

This service is built with Flask and is designed to be run as a standalone microservice.

## Getting Started

### Prerequisites

*   Python 3.6+
*   Dependencies listed in `requirements.txt`

### Installation & Setup

1.  **Navigate to the service directory:**
    ```bash
    cd fulfillment_service
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Ensure Data Files Are Present:**
    This service relies on `products.json` and `orders_pending_shipping.json` from the main project. Ensure these files exist in the `catalog/` and `logs/best_buy/` directories at the project root.

4.  **Run the Service:**
    For development, you can run the Flask app directly:
    ```bash
    python3 src/app.py
    ```
    The service will start on `http://127.0.0.1:5000`. For production, use a WSGI server like Gunicorn.

## API Endpoints

The service exposes the following RESTful API endpoints:

### 1. Start Fulfillment

*   **URL:** `/api/fulfillment/start`
*   **Method:** `POST`
*   **Description:** Initializes a new fulfillment session for an order.
*   **Request Body:**
    ```json
    {
      "order_id": "YOUR_ORDER_ID"
    }
    ```
*   **Success Response (201):**
    ```json
    {
      "message": "Fulfillment process started successfully.",
      "order_id": "YOUR_ORDER_ID",
      "required_components": ["component_name_1", "component_name_2"]
    }
    ```
*   **Error Responses:** `400` (bad request), `404` (order not found), `409` (already in progress).

### 2. Scan Component

*   **URL:** `/api/fulfillment/scan`
*   **Method:** `POST`
*   **Description:** Validates a scanned component barcode for the active order.
*   **Request Body:**
    ```json
    {
      "order_id": "YOUR_ORDER_ID",
      "barcode": "SCANNED_BARCODE"
    }
    ```
*   **Success Response (200):**
    ```json
    {
      "message": "Component 'component_name' scanned successfully.",
      "order_id": "YOUR_ORDER_ID",
      "barcode": "SCANNED_BARCODE",
      "validation_status": "success"
    }
    ```
*   **Error Responses:** `400` (invalid barcode or duplicate scan), `404` (session not started).

### 3. Finalize Fulfillment

*   **URL:** `/api/fulfillment/finalize`
*   **Method:** `POST`
*   **Description:** Verifies that all components have been scanned and triggers the generation of a shipping label. It also updates the inventory and records the Cost of Goods Sold (COGS).
*   **Request Body:**
    ```json
    {
      "order_id": "YOUR_ORDER_ID"
    }
    ```
*   **Success Response (200):**
    ```json
    {
      "message": "Fulfillment process finalized successfully.",
      "order_id": "YOUR_ORDER_ID",
      "tracking_number": "ACTUAL_TRACKING_PIN",
      "label_path": "path/to/downloaded/label.pdf"
    }
    ```
*   **Error Responses:** `400` (not all components scanned), `404` (session not started), `500` (label generation failed).

## Shipping Integration

This service is integrated with the `shipping` module to generate shipping labels. When the `/api/fulfillment/finalize` endpoint is called, the service calls the `create_shipment_and_get_label` function from the `shipping.canada_post.cp_shipping.cp_pdf_labels` module. This function creates the shipping label with Canada Post and returns the tracking number and a URL to the PDF label. The fulfillment service then downloads the PDF label and saves it to the `logs/canada_post/cp_pdf_shipping_labels` directory.
