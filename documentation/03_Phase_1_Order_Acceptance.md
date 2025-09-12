# Phase 1 (v2): Re-Architected Order Acceptance

This document provides a detailed breakdown of the **re-architected** Order Acceptance workflow. This version of the workflow is built upon a more robust, event-driven database schema that enhances auditability and resilience.

## 1. Strategic Goal

The primary goal of this re-architecture was to move from a simple status column to a full **status timeline**, providing a complete, auditable history of every order's journey through the system. This directly addresses the need for better troubleshooting and future business analytics.

-   **Full Audit Trail:** Every state change is now a permanent, timestamped record in the `order_status_history` table.
-   **Decoupled State:** The current status of an order is no longer a mutable field but is determined by querying for the most recent entry in its history. This is a more robust pattern that prevents inconsistent states.
-   **Generic Failure Logging:** A new `process_failures` table was introduced to act as a centralized inbox for all critical errors across all modules that require manual intervention.

## 2. The New Workflow

The core logic remains in `order_management/workflow.py`, but its interaction with the database has fundamentally changed.

1.  **Fetch Orders to Process:** The workflow no longer queries for `status = 'pending_acceptance'`. Instead, it executes a more sophisticated query to find all orders whose **most recent status** in the `order_status_history` table is `pending_acceptance`.

2.  **Initial Acceptance Call:** This remains the same: a single API call is made to Best Buy to accept the order. The full API call and response are logged to the `api_calls` table.

3.  **Handling Failure:** If the initial API call fails, the workflow now:
    -   Logs the issue to the new `process_failures` table with a process name of `OrderAcceptance`.
    -   Adds a new `'acceptance_failed'` status to the `order_status_history` table.

4.  **The Validation Loop:** If the acceptance call succeeds, the validation loop begins.
    -   It repeatedly calls the Best Buy API to check the order's status.
    -   **On Success:** If the status becomes `WAITING_DEBIT_PAYMENT` or `SHIPPING`, it logs a final `'accepted'` status to the `order_status_history` table and concludes.
    -   **On Cancellation:** It logs a `'cancelled'` status.
    -   **On Final Failure:** If the validation attempts are exhausted, it logs the event to `process_failures` and adds an `'acceptance_failed'` status to the history.

## 3. The Re-Architected Database Schema

The new schema is the backbone of this workflow.

### `orders` Table
-   The `status` column has been **removed**. The table now only stores the core, unchanging details of the order.

### `order_status_history` Table (New)
-   **Purpose:** The new source of truth for order state.
-   **Columns:**
    -   `history_id` (PK): A unique ID for the history event.
    -   `order_id` (FK): Links to the order.
    -   `status`: The new status being assigned (e.g., `'pending_acceptance'`, `'accepted'`).
    -   `notes`: Optional text for context (e.g., "Validated as 'SHIPPING'").
    -   `timestamp`: The exact time the status change occurred.

### `process_failures` Table (New)
-   **Purpose:** A generic, system-wide table for logging critical errors that need a human to review.
-   **Columns:**
    -   `failure_id` (PK): A unique ID for the failure log.
    -   `related_id`: The ID of the item that failed (e.g., the `order_id`).
    -   `process_name`: The name of the workflow that failed (e.g., `'OrderAcceptance'`).
    -   `details`: A human-readable description of the error.
    -   `payload` (JSONB): The data object being processed at the time of failure, for easy debugging.
