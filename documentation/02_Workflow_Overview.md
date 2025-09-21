# High-Level Workflow Overview

This document provides a comprehensive overview of the entire automated order processing and customer service workflow. It explains how the different modules interact and the sequence of events from receiving an order to marking it as shipped.

## Core Philosophy: A Status-Driven System

The entire system is built around a **status-driven architecture**. Instead of just having a single `status` field on an order, we maintain a complete, timestamped history of every state change in the `order_status_history` table.

This approach provides several key advantages:
-   **Full Audit Trail**: We have a complete, immutable record of everything that happened to an order and when.
-   **Idempotency**: Workflows can be re-run without causing harm. For example, the shipping workflow only looks for orders with the status `accepted`. Once a label is created and the status changes to `label_created`, the shipping workflow will ignore it on subsequent runs.
-   **Resilience**: If a step fails, the order remains in its current state. When the script is re-run, it will automatically pick up the failed order and try again without manual intervention.
-   **Clarity**: It's easy to query the database to find all orders in a specific state (e.g., "all orders that failed during shipping label creation").

## The Main Workflow Cycle

The core of the application's backend logic is orchestrated by the `run_core_workflows.sh` script. This script is designed to be run periodically by a scheduler like `cron`. It executes a series of independent workflow scripts in a specific order.

Here is a visual representation of the main data flow:

```
[ Best Buy API ] <--> [ 1. Order Acceptance ] <--> [ PostgreSQL DB ] <--> [ 2. Shipping & Tracking ] <--> [ Canada Post API ]
                                                                 |
                                                                 |
                                     [ 3. Customer Service Sync ] <--> [ Best Buy API ]
```

---

### 1. Order Acceptance (`main_acceptance.py`)

-   **Trigger**: This is the first step in the cycle.
-   **Goal**: To formally accept new orders that have been placed on the Best Buy Marketplace.

**Process:**
1.  **Fetch Pending Orders**: The script queries the database for all orders whose most recent status in `order_status_history` is `pending_acceptance`. (These orders are inserted into the database by a separate, initial data-fetch process not covered in this core loop).
2.  **Accept via API**: For each pending order, it sends an API call to Best Buy to accept all the order lines.
3.  **Validate Status**: The script then enters a validation loop. It repeatedly polls the Best Buy API for that order's status, waiting for it to change from `PENDING_ACCEPTANCE` to a post-acceptance state like `SHIPPING` or `WAITING_DEBIT_PAYMENT`.
4.  **Update DB**: Once validated, it inserts an `accepted` record into the `order_status_history` table. If validation fails after several attempts, it inserts an `acceptance_failed` record for manual review.

---

### 2. Shipping & Tracking (`main_shipping.py` and `main_tracking.py`)

-   **Trigger**: Runs after the Order Acceptance workflow.
-   **Goal**: To create shipping labels for accepted orders and update Best Buy with the tracking information.

**Process (Label Creation - `main_shipping.py`):**
1.  **Fetch Shippable Orders**: Queries the database for all orders whose latest status is `accepted` and which do **not** already have a record in the `shipments` table. This is the key step that prevents duplicate label creation.
2.  **Create Shipment Record**: Creates a new record in the `shipments` table to represent the physical package.
3.  **Create Canada Post Shipment**: Sends a request to the Canada Post API with the order details to create a shipment and get a tracking number.
4.  **Download & Validate**: Downloads the PDF shipping label from the URL provided by Canada Post and validates its content to ensure it's correct.
5.  **Update DB**: Updates the `shipments` record with the new tracking PIN and file path, and adds a `label_created` status to the order's history.

**Process (Tracking Update - `main_tracking.py`):**
1.  **Fetch Orders to Update**: Queries the database for all shipments whose order status is `label_created`.
2.  **Update Tracking on Best Buy**: Calls the Best Buy API to submit the tracking number for the order.
3.  **Mark as Shipped**: Makes a second API call to mark the order as officially "shipped".
4.  **Update DB**: Adds a final `shipped` status to the order's history. The order is now complete from an automation perspective.

---

### 3. Customer Service Sync (`main_customer_service.py` & `main_auto_reply.py`)

-   **Trigger**: Runs independently as part of the main cycle.
-   **Goal**: To keep our internal database synchronized with customer messages from the Best Buy platform and to send automated replies.

**Process:**
1.  **Fetch New Messages**: Connects to the Mirakl (Best Buy) API to fetch any new messages.
2.  **Process and Store**: Ingests the messages, creates new `customer` and `conversation` records in the database if they don't exist, and saves the new `message` records.
3.  **Run Auto-Reply Logic**: After syncing messages, the `auto_reply` module scans for conversations that meet certain criteria (e.g., a new, unread message from a customer) and sends a templated, automated reply via the API.

## Web Interfaces and Other Components

-   **Fulfillment Service (`web_interface/fulfillment_service_app.py`):** A web GUI to assist warehouse staff in the physical picking and packing process. It allows for scanning component barcodes to ensure order accuracy.
-   **Customer Service UI (`web_interface/customer_service_app.py`):** A web GUI for human agents to view conversations and manually send replies. It is powered by the data synced by the Customer Service workflow.
-   **Grafana & Monitoring**: The Docker stack includes Grafana, which can be configured with dashboards to monitor the state of the database, providing insights into order volume, processing times, and error rates.
