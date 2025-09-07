# Phase 1: Order Acceptance

This phase handles the detection and acceptance of new orders from the Best Buy Marketplace.

## Orchestrator

-   `main_acceptance.py`: This script orchestrates the three steps of the acceptance phase.

## Scripts

1.  **`Orders/pending_acceptance/orders_pending_acceptance/retieve_pending_acceptance.py`**
    -   **Purpose:** Retrieves all orders with the status `WAITING_ACCEPTANCE` from the Best Buy API.
    -   **Output:** Saves the retrieved orders to `logs/best_buy/pending_acceptance.json`.

2.  **`Orders/pending_acceptance/accept_orders_pending_confirmation/accept_orders.py`**
    -   **Purpose:** Reads the `pending_acceptance.json` file and calls the Best Buy API to accept each order line.
    -   **Output:** Logs successfully accepted orders to `logs/best_buy/accepted_orders_log.json` and creates a detailed journal in `logs/best_buy/order_acceptance_journal.json`.

3.  **`Orders/pending_acceptance/accept_pending_orders_validation/order_acceptance_validation.py`**
    -   **Purpose:** Makes a final API call to Best Buy to ensure no orders are left in the `WAITING_ACCEPTANCE` state, confirming the success of the phase.
    -   **Output:** Returns a status of `SUCCESS`, `VALIDATION_FAILED`, or `NEW_ORDERS_FOUND`.
