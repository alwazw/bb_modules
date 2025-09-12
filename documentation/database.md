# Database Schema

This document provides a detailed overview of the PostgreSQL database schema used in this application. The database is the central source of truth for all data related to orders, customers, inventory, and application operations.

## Schema Overview

The schema is divided into several logical sections:

1.  **Customer and Conversation Schema**: Manages customer data and their communications.
2.  **Core Order Processing Schema**: Handles all data related to marketplace orders.
3.  **Auditing and Error Logging Schema**: Provides tables for logging API calls and critical process failures.
4.  **Inventory Management Schema**: Defines the structure for tracking products, components, and stock.

---

## 1. Customer and Conversation Schema

### `customers`
*   **Purpose**: Stores a unique record for each customer.
*   **Key Columns**:
    *   `id`: A unique internal ID for the customer.
    *   `mirakl_customer_id`: The customer's unique ID from the Best Buy Marketplace (Mirakl platform).

### `conversations`
*   **Purpose**: Represents a single conversation thread with a customer. A conversation can be linked to a specific order.
*   **Key Columns**:
    *   `id`: A unique internal ID for the conversation.
    *   `mirakl_thread_id`: The conversation's unique ID from the Mirakl platform.
    *   `customer_id`: A foreign key linking to the `customers` table.
    *   `order_id`: A foreign key linking to the `orders` table.
    *   `status`: The current status of the conversation (e.g., `unread`, `read`, `archived`).

### `messages`
*   **Purpose**: Stores an individual message within a conversation.
*   **Key Columns**:
    *   `conversation_id`: A foreign key linking to the `conversations` table.
    *   `sender_type`: Indicates whether the message was from a `customer` or a `technician`.
    *   `message_type`: Differentiates between a `manual` reply and an `auto_reply`.

---

## 2. Core Order Processing Schema

### `orders`
*   **Purpose**: The main table for storing order information. It includes the raw order data from the API for auditing and reprocessing purposes.
*   **Key Columns**:
    *   `order_id`: The unique ID for the order from the marketplace.
    *   `raw_order_data`: A `JSONB` column containing the original, unmodified order data from the API.

### `order_lines`
*   **Purpose**: Stores information about each individual line item within an order.
*   **Key Columns**:
    *   `order_line_id`: A unique ID for the line item.
    *   `order_id`: A foreign key linking to the `orders` table.
    *   `sku`: The SKU of the product ordered.

### `order_status_history`
*   **Purpose**: Provides a complete, timestamped audit trail of an order's state. Instead of a single `status` column on the `orders` table, a new row is added here every time the order's status changes.
*   **Key Columns**:
    *   `order_id`: A foreign key linking to the `orders` table.
    *   `status`: The status of the order at that point in time (e.g., `pending_acceptance`, `accepted`, `shipped`).

### `shipments`
*   **Purpose**: Stores shipment information, which is created when the shipping process for an order begins.
*   **Key Columns**:
    *   `order_id`: A unique foreign key linking to the `orders` table.
    *   `tracking_pin`: The tracking number for the shipment.
    *   `label_pdf_path`: The local file path to the downloaded shipping label.

---

## 3. Auditing and Error Logging Schema

### `api_calls`
*   **Purpose**: A generic table to log all third-party API calls (e.g., to Best Buy, Canada Post). This is crucial for debugging and auditing.
*   **Key Columns**:
    *   `service`: The name of the service being called (e.g., `BestBuy`, `CanadaPost`).
    *   `request_payload`: The data sent in the API request.
    *   `response_body`: The response received from the API.

### `process_failures`
*   **Purpose**: Logs critical, unrecoverable failures that require manual intervention.
*   **Key Columns**:
    *   `process_name`: The name of the workflow where the failure occurred (e.g., `OrderAcceptance`).
    *   `details`: A human-readable description of the error.

---

## 4. Inventory Management Schema

### `components`
*   **Purpose**: Stores individual, sellable/trackable components (e.g., RAM, SSDs).
*   **Key Columns**:
    *   `name`: The name of the component.
    *   `type`: The type of component (e.g., `RAM`, `SSD`).

### `base_products`
*   **Purpose**: Stores the base laptop models, stripped of their configurable components.
*   **Key Columns**:
    *   `model_name`: The model name of the base product.

### `product_variants`
*   **Purpose**: Represents a specific, sellable configuration of a base product. This is the canonical representation of a product.
*   **Key Columns**:
    *   `internal_sku`: A unique, internal SKU for this specific variant.

### `variant_components`
*   **Purpose**: A join table that defines the "Bill of Materials" for each product variant, linking it to the specific components that make it up.
*   **Key Columns**:
    *   `variant_id`: A foreign key linking to the `product_variants` table.
    *   `component_id`: A foreign key linking to the `components` table.

### `shop_sku_map`
*   **Purpose**: Maps a marketplace-facing "shop SKU" back to an internal `variant_id`. This allows for multiple listings for the same product.
*   **Key Columns**:
    *   `shop_sku`: The SKU used on the marketplace.
    *   `variant_id`: A foreign key linking to the `product_variants` table.
