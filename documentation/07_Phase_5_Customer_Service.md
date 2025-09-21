# Phase 5: Customer Service Module

This document outlines the architecture and functionality of the Customer Service module, which is designed to centralize and streamline communication with customers.

## 1. Overview

The Customer Service module provides a "Slack-like" experience for handling customer communications from the Mirakl (Best Buy) platform. It aggregates all customer messages, intelligently organizes them into conversations, and provides a powerful, database-driven web interface for viewing and responding to them.

## 2. Message Synchronization Workflow

The core of the customer service module is a message synchronization workflow, executed by `main_customer_service.py`, which in turn calls the logic in `customer_service/message_aggregation/fetch_messages.py`. This workflow runs periodically as part of the master scheduler.

1.  **Fetch New Messages**: The script connects to the Mirakl API and fetches any new messages since the last successful sync. It uses a timestamp stored in a local file (`last_sync_time.txt`) to keep track of the last run time, ensuring it only pulls new data.

2.  **Process and Store (Ingestion Logic)**: For each new message, the script performs a series of checks and database operations to ensure the data is stored in a structured way:
    -   It first checks if the message belongs to an existing conversation by looking up the `mirakl_thread_id` in the `conversations` table.
    -   If a conversation doesn't exist, it creates a new one.
    -   It then checks if the customer associated with the message exists in our `customers` table. If not, it creates a new customer record.
    -   Finally, it saves the new message content to the `messages` table, linking it to the correct conversation.

3.  **Update Timestamps**: The `last_message_at` timestamp for the conversation is updated to reflect the new message. This allows the web interface to sort conversations by the most recent activity.

## 3. Database Schema

The customer service module introduces three new tables to the database schema, forming the foundation of the communication log.

-   **`customers`**: Stores customer information, including their unique Mirakl ID, first name, last name, and email.
-   **`conversations`**: Stores a record for each message thread. It links to a customer and (optionally) an order. Each conversation has a subject and a timestamp for the last message to enable easy sorting.
-   **`messages`**: Stores individual messages within a conversation, including the sender (`'customer'` or `'technician'`), the message body, and the timestamp.

## 4. RESTful API Endpoints

A set of RESTful API endpoints are provided by the `web_interface/customer_service_app.py` to allow the frontend to interact with the customer service data in the database.

-   `GET /api/conversations`: Returns a list of all conversations, sorted by the most recent message.
-   `GET /api/conversations/<id>`: Returns all messages for a single conversation, identified by its database ID.
-   `POST /api/conversations/<id>/messages`: Allows a technician to send a new message to a conversation. The new message is saved to the database and then sent to the customer via the Mirakl API.
-   `GET /api/orders/<orderId>/conversations`: Returns all conversations associated with a specific order ID.

## 5. Web Interface

A web-based interface provides a user-friendly way for customer service agents to interact with the system.

-   **Two-Column Layout**: The interface has a familiar two-column layout, with a list of conversations in a sidebar on the left and the selected message view on the right.
-   **Dynamic Updates**: The interface is a single-page application that uses JavaScript to dynamically fetch and display conversations and messages from the API without requiring page reloads.
-   **Send Messages**: Users can type and send new messages directly from the web interface.
-   **Auto-Reply Integration**: The system also includes an `auto_reply` module (`customer_service/src/auto_reply.py`) that can be run to automatically send templated responses to new customer messages based on a set of rules.
