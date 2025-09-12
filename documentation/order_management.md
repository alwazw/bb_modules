# Order Management Module

This module is responsible for managing the lifecycle of orders from the Best Buy Marketplace. It handles the initial acceptance of new orders and retrieves orders that are ready for shipment.

## Key Components

*   **`workflow.py`**: This is the main workflow for accepting new orders. It fetches orders that are `pending_acceptance` from the database, sends a request to the Best Buy API to accept them, and then validates that the order status has been updated correctly. This script uses the `order_status_history` table to track the state of each order.
*   **`awaiting_shipment/orders_awaiting_shipment/retrieve_pending_shipping.py`**: This script retrieves all orders from the Best Buy API that are in the `SHIPPING` state. These are orders that have been accepted and are now ready to be fulfilled and have a shipping label created.

## Workflow

1.  **Order Acceptance**: The `order_management/workflow.py` script is run on a schedule. It finds all orders in the database that are waiting to be accepted and sends a request to the Best Buy API to accept them. It then polls the API to validate that the order has been successfully accepted.
2.  **Retrieve Pending Shipping**: The `retrieve_pending_shipping.py` script is also run on a schedule. It fetches all orders that have been accepted and are now ready for shipment. These orders are saved to the `logs/best_buy/orders_pending_shipping.json` file, which is then used by the `shipping` module.

This module is the first step in the order processing pipeline, ensuring that new orders are acknowledged and queued for fulfillment in a timely manner.
