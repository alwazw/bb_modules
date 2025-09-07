# Workflow Overview

This document provides a high-level overview of the entire automated order processing workflow.

## Master Scheduler (`main_scheduler.py`)

The heart of the application is the master scheduler. It is designed to be run as a continuous process. Every 15 minutes, it executes the main workflow cycle.

The cycle consists of three main phases:

### Phase 1: Order Acceptance

1.  **Retrieve Pending Orders:** The scheduler first calls the Best Buy API to check for any orders in the `WAITING_ACCEPTANCE` state.
2.  **Accept Orders:** For each new order found, the script makes an API call to accept the order lines.
3.  **Log Accepted Orders:** The IDs of successfully accepted orders are logged.
4.  **Validate:** The script re-checks the Best Buy API to ensure that there are no more orders pending acceptance, confirming the success of the phase.

Once an order is accepted, it typically moves to a `WAITING_DEBIT_PAYMENT` state on the Best Buy side.

### Phase 2: Shipping Label Creation

1.  **Retrieve Shippable Orders:** The scheduler calls the Best Buy API to get a list of all orders currently in the `SHIPPING` state. This state indicates that payment has been cleared and the order is ready to be shipped.
2.  **Duplicate Check:** For each shippable order, the system checks its internal logs (`logs/canada_post/cp_shipping_history_log.json`) to see if a shipping label has already been created. If it has, the order is skipped to prevent creating duplicate shipments.
3.  **Transform Data:** For new shippable orders, the order data is transformed into the required XML format for the Canada Post "Create Shipment" API.
4.  **Create CP Shipment:** The script calls the Canada Post API with the XML payload. This is a **live production call** that uses the `transmit-shipment` flag, meaning it creates a real, billable shipment.
5.  **Validate Shipment:** After creating the shipment, the script makes a second call to the Canada Post "Get Tracking Summary" API to validate that the new tracking PIN is active and recognized.
6.  **Download PDF Label:** A 4x6 PDF shipping label is downloaded and saved with a unique timestamped filename (e.g., `{order_id}_{timestamp}.pdf`).
7.  **Log Shipment Data:** The full details of the Canada Post shipment are saved to history logs.

### Phase 3: Tracking and Status Update

1.  **Update Tracking on Best Buy:** The scheduler takes the valid tracking number from the previous phase and calls the Best Buy API to add it to the order.
2.  **Mark as Shipped:** Immediately after adding the tracking number, a second API call is made to mark the order as shipped. This is the action that updates the order status for the end customer.
3.  **Log Order Data:** After the order is successfully marked as shipped, the script makes a final API call to get all available details for the now-shipped order and saves this data to history logs.
4.  **Final Validation:** The script validates that the final order status on Best Buy is `SHIPPED`.

This cycle repeats every 15 minutes, creating a fully automated, end-to-end fulfillment process.
