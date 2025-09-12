# Workflow Overview

This document provides a high-level overview of the entire automated order processing and customer service workflow.

## Master Scheduler (`run_core_workflows.sh`)

The heart of the application is the master scheduler. It is designed to be run periodically (e.g., via `cron`). It executes the main workflow cycle.

The cycle consists of two main backend processes:

### 1. Order Fulfillment Workflow (`shipping/workflow.py`)

This workflow handles the entire process of shipping an order, from label creation to final status updates.

-   **Phase 1: Shipping Label Creation**
    1.  **Retrieve Shippable Orders:** The system queries its internal database for orders that have been accepted and are ready for shipment.
    2.  **Duplicate Check:** The system checks if a shipment has already been created for an order to prevent duplicate labels.
    3.  **Create CP Shipment:** The script calls the Canada Post API to create a real, billable shipment.
    4.  **Validate and Download:** The script validates the response from Canada Post, downloads the PDF shipping label, and saves it.
    5.  **Update Database:** The shipment details, including the tracking PIN, are saved to the database.

-   **Phase 2: Tracking and Status Update**
    1.  **Update Tracking on Best Buy:** The workflow takes the tracking number and calls the Best Buy API to add it to the order.
    2.  **Mark as Shipped:** A second API call is made to mark the order as shipped, which updates the status for the end customer.
    3.  **Update Database:** The final `shipped` status is recorded in the local database.

### 2. Customer Service Message Sync (`customer_service/message_aggregation/fetch_messages.py`)

This workflow runs independently to keep customer communications up to date.

1.  **Fetch New Messages:** The script connects to the Mirakl API and fetches any new messages since the last time it was run. It keeps track of the last sync time in a local file.
2.  **Process and Store:** For each new message, the script:
    -   Checks if the message belongs to an existing conversation.
    -   If not, it creates a new conversation and a new customer record if necessary.
    -   Saves the new message to the database.
3.  **Update Timestamps:** The `last_message_at` timestamp for the conversation is updated to reflect the new message.

## Web Interfaces

The application also includes two web interfaces for manual tasks and viewing data.

-   **Fulfillment Service (`web_interface/fulfillment_service_app.py`):** A web-based interface to guide the physical fulfillment process (e.g., scanning components).
-   **Customer Service (`web_interface/customer_service_app.py`):** A Slack-like web interface for viewing customer conversations and sending messages. This interface is powered by the data synced by the customer service message sync workflow.
