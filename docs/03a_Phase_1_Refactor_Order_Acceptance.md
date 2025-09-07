# Phase 1 (Refactored): Database-Driven Order Acceptance

This document provides a detailed breakdown of the refactored Order Acceptance workflow. This initial phase of the order lifecycle is critical, and its redesign was the first step in transforming the application from a collection of scripts into a robust, scalable system.

## 1. Strategic Goal

The primary goal of this refactoring was to replace the brittle and fragmented JSON file-based system with a centralized, reliable **PostgreSQL database**. This change provides several key advantages that align with the project's long-term vision:

-   **Single Source of Truth:** All order data, from initial acceptance to final shipment, now resides in one place. This eliminates data duplication and inconsistencies.
-   **Data Integrity:** The database schema enforces rules (e.g., foreign key constraints) that protect the relationships between data, ensuring high data quality.
-   **Scalability:** A relational database is designed to handle a large volume of transactions efficiently, ensuring the system can grow without performance degradation.
-   **Auditability & Debugging:** By logging every state change and API call to the database, we now have a powerful, queryable audit trail. This makes debugging issues and understanding order history trivial compared to parsing scattered log files.
-   **Foundation for Future Modules:** This robust data layer is the necessary foundation upon which all future modules (Shipping, Inventory, Analytics, Web UI) will be built.

## 2. The New Workflow

The core logic is now consolidated in `order_management/workflow.py`. The new process for handling an order is more intelligent and resilient than the previous version.

Here is the step-by-step flow for each order pending acceptance:

1.  **Initial Acceptance Call (Once Only):**
    -   The system makes a single API call to Best Buy to accept the order.
    -   The result of this specific API call (success or failure) is immediately logged to the `order_acceptance_attempts` table.
    -   **Design Rationale:** We only attempt the *acceptance action* once. Sending multiple acceptance requests for the same order is inefficient and could lead to unintended behavior with the external API. The real challenge is not accepting the order, but confirming its status has updated in Best Buy's system, which can take time.

2.  **Immediate Failure Check:**
    -   If the initial acceptance API call fails (e.g., due to a network error or invalid data), the system immediately halts processing for that order.
    -   It logs the failure details to the `order_acceptance_debug_logs` table for manual review and updates the order's status to `acceptance_failed`.

3.  **The Validation Loop (Up to 3 Retries):**
    -   If the acceptance call was successful, the system enters a validation loop. It knows the acceptance *request* was received, but now it must verify that the order's *status* has changed on Best Buy's end.
    -   **Pause:** The system waits for 60 seconds before the first check. This gives the external API time to process the request.
    -   **Validate:** It makes a `GET` request to fetch the order's current status.
    -   **Success:** If the status is `WAITING_DEBIT_PAYMENT` or `SHIPPING`, the process is considered a success. The order's status is updated to `accepted` in our database, and the workflow for this order concludes.
    -   **Cancellation:** If the status is `CANCELLED`, our database is updated accordingly, and the workflow concludes.
    -   **Retry:** If the status is still `WAITING_ACCEPTANCE` or another intermediate state, the loop continues to the next attempt (up to 3 total validation attempts).

4.  **Final Failure & Notification:**
    -   If, after all validation attempts, the order status has still not updated to a recognized final state, the workflow considers the process to have failed.
    -   A detailed entry is made in the `order_acceptance_debug_logs` table, including the final status that was observed.
    -   The order's status is updated to `acceptance_failed` in our database.
    -   A placeholder "notification" is printed to the console, indicating that the order requires manual intervention.

## 3. Database Schema

The new database schema is the backbone of this workflow.

### `orders` Table
-   **Purpose:** The central table holding the primary record for every order.
-   **Columns:**
    -   `order_id` (PK): The unique Best Buy order ID.
    -   `status`: The current state of the order within our internal workflow (e.g., `pending_acceptance`, `accepted`, `acceptance_failed`, `shipped`).
    -   `created_at` / `updated_at`: Timestamps for tracking record changes.
    -   `raw_order_data` (JSONB): Stores the complete, original JSON object for the order received from Best Buy. This is crucial for debugging, future data analysis, and avoids needing to re-fetch data.

### `order_lines` Table
-   **Purpose:** Stores the individual line items for each order.
-   **Columns:**
    -   `order_line_id` (PK): The unique ID for the line item.
    -   `order_id` (FK): Links the line item back to its parent order in the `orders` table.
    -   `sku`, `quantity`: Key details about the product ordered.
    -   `raw_line_data` (JSONB): The original JSON for the line item.

### `order_acceptance_attempts` Table
-   **Purpose:** Provides a complete and detailed audit trail of the initial acceptance API call for every order.
-   **Columns:**
    -   `attempt_id` (PK): A unique ID for the log entry.
    -   `order_id` (FK): Links to the order.
    -   `attempt_number`: In the current workflow, this will always be `1`.
    -   `status`: 'success' or 'failure', indicating the result of the API call itself.
    -   `api_response` (JSONB): The full API response (headers and body) received from Best Buy, essential for debugging API-level issues.

### `order_acceptance_debug_logs` Table
-   **Purpose:** A dedicated table for logging orders that have failed the workflow and require a human to investigate.
-   **Columns:**
    -   `log_id` (PK): A unique ID for the debug log.
    -   `order_id` (FK): Links to the problematic order.
    -   `details`: A human-readable text field explaining why the order failed (e.g., "Initial API call failed" or "Validation failed after 3 attempts").
    -   `raw_request_payload` (JSONB): The exact payload that was sent to the Best Buy API, allowing developers to perfectly replicate the failed request.
