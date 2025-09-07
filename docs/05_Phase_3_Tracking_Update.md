# Phase 3: Tracking and Status Update

This phase handles the final step of updating the order on the Best Buy Marketplace with the new tracking information.

## Orchestrator

-   `main_tracking.py`: This script orchestrates the two-step process of updating tracking and marking the order as shipped.

## Scripts

1.  **`Orders/shipped_orders/update_tracking_info/update_tracking_numbers.py`**
    -   **Purpose:** This script contains all the logic for this phase.
    -   It reads the `cp_shipping_labels_data.json` log to get the list of recently created shipments and their tracking numbers.
    -   For each shipment, it performs a two-step update to the Best Buy API:
        1.  **Update Tracking (`/tracking`):** A `PUT` request is sent to add the carrier code (`CPCL`) and the tracking number to the order.
        2.  **Mark as Shipped (`/ship`):** A second `PUT` request is sent to mark the order as shipped. This is the action that changes the status visible to the customer.
    -   **Output:** After a successful update, it calls the Best Buy API again to get the full, final details of the shipped order and logs this data to `logs/best_buy/orders_shipped_and_validated.json` and `logs/customer_service/orders_shipped_and_validated.json`.

2.  **`Orders/shipped_orders/update_tracking_info/validate_shipped_status.py`**
    -   **Purpose:** After the tracking update, this script is called to make a final check on the order status, ensuring it is `SHIPPED`.
