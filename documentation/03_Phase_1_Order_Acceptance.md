# Phase 1 (v2): Re-Architected Order Acceptance

This document provides a detailed breakdown of the **re-architected** Order Acceptance workflow. This version of the workflow is built upon a more robust, event-driven database schema that enhances auditability and resilience.

## 1. Strategic Goal

The primary goal of this re-architecture was to move from a simple, mutable `status` column on the main `orders` table to a full **status timeline**. This provides a complete, auditable history of every order's journey through the system. This design directly addresses the need for better troubleshooting and future business analytics.

The key benefits of this approach are:

-   **Full Audit Trail**: Every state change is now a permanent, timestamped record in the `order_status_history` table. We can see exactly when an order was accepted, when its label was created, and when it was shipped.
-   **Idempotency and Resilience**: The current status of an order is determined by querying for the most recent entry in its history. This is a more robust pattern that prevents inconsistent states and allows workflows to be re-run safely.
-   **Generic Failure Logging**: A new `process_failures` table was introduced to act as a centralized "inbox" for all critical errors across all modules that require manual intervention.

## 2. The New Workflow Logic

The core logic resides in `order_management/workflow.py`, but its interaction with the database has been fundamentally improved.

1.  **Fetch Orders to Process**
    The workflow no longer runs a simple `SELECT ... WHERE status = 'pending_acceptance'`. Instead, it executes a more sophisticated query to find all orders whose **most recent status** in the `order_status_history` table is `pending_acceptance`. This ensures that we only process orders that are truly in the correct state.

2.  **Initial Acceptance API Call**
    This part of the process remains the same: a single API call is made to Best Buy to accept all the lines of the order. For auditing purposes, the full API call and its response are logged to the `api_calls` table.

3.  **Handling API Failure**
    If the initial API call to Best Buy fails (e.g., due to a network error or a 5xx response), the workflow now:
    -   Logs the issue to the new `process_failures` table with a `process_name` of `OrderAcceptance`.
    -   Adds a new `'acceptance_failed'` status to the `order_status_history` table.
    -   Stops processing for this order, to be retried on the next scheduler run.

4.  **The Validation Loop**
    If the acceptance call succeeds, the workflow enters a validation loop to confirm that Best Buy's systems have processed the acceptance.
    -   It repeatedly calls the "Get Order" endpoint on the Best Buy API to check the order's status.
    -   **On Success**: If the status becomes `WAITING_DEBIT_PAYMENT` or `SHIPPING`, the workflow logs a final `'accepted'` status to the `order_status_history` table and concludes its work for this order.
    -   **On Cancellation**: If Best Buy has cancelled the order in the meantime, it logs a `'cancelled'` status.
    -   **On Final Failure**: If the validation attempts are exhausted and the status has not changed, it logs the event to `process_failures` and adds an `'acceptance_failed'` status to the history for manual review.

## 3. The Re-Architected Database Schema

The new schema is the backbone of this robust workflow.

### `orders` Table
-   The `status` column has been **removed**. The table now only stores the core, unchanging details of the order, such as the `order_id` and the raw JSON data from the initial fetch.

### `order_status_history` Table (New)
-   **Purpose**: The new source of truth for an order's current state.
-   **Columns**:
    -   `history_id` (PK): A unique ID for the history event itself.
    -   `order_id` (FK): Links to the `orders` table.
    -   `status` (VARCHAR): The new status being assigned (e.g., `'pending_acceptance'`, `'accepted'`, `'shipped'`).
    -   `notes` (TEXT): Optional text for context (e.g., "Validated as 'SHIPPING' after 2 attempts.").
    -   `timestamp` (TIMESTAMPTZ): The exact time the status change occurred.

### `process_failures` Table (New)
-   **Purpose**: A generic, system-wide table for logging critical errors that need a human to review.
-   **Columns**:
    -   `failure_id` (PK): A unique ID for the failure log.
    -   `related_id` (VARCHAR): The ID of the item that failed (e.g., the `order_id`).
    -   `process_name` (VARCHAR): The name of the workflow that failed (e.g., `'OrderAcceptance'`, `'ShippingLabelCreation'`).
    -   `details` (TEXT): A human-readable description of the error.
    -   `payload` (JSONB): The data object that was being processed at the time of failure, for easy debugging.
