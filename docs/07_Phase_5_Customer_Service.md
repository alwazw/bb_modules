# Phase 5: Customer Service Module

This document outlines the architecture and functionality of the Customer Service module.

## 1. Overview

The Customer Service module provides a "Slack-like" experience for handling customer communications from the Mirakl platform. It aggregates customer messages, organizes them into conversations, and provides a web-based interface for viewing and responding to them.

## 2. Message Synchronization Workflow

The core of the customer service module is a message synchronization workflow (`customer_service/message_aggregation/fetch_messages.py`) that runs periodically.

1.  **Fetch New Messages:** The script connects to the Mirakl API and fetches any new messages since the last successful sync. It uses a timestamp stored in a local file to keep track of the last sync time.
2.  **Process and Store:** For each new message, the script:
    -   Determines if the message belongs to an existing conversation based on the Mirakl thread ID.
    -   If a conversation doesn't exist, it creates a new one.
    -   If the customer doesn't exist in the local database, it creates a new customer record.
    -   Saves the new message to the `messages` table.
3.  **Update Timestamps:** The `last_message_at` timestamp for the conversation is updated to reflect the new message.

## 3. Database Schema

The customer service module introduces three new tables to the database schema:

-   **`customers`:** Stores customer information, including their Mirakl ID, name, and email.
-   **`conversations`:** Stores conversations, linking them to customers and orders. Each conversation has a subject and a timestamp for the last message.
-   **`messages`:** Stores individual messages within a conversation, including the sender, body, and timestamp.

## 4. API Endpoints

A set of RESTful API endpoints are provided to interact with the customer service data.

-   `GET /api/conversations`: Returns a list of all conversations, sorted by the most recent message.
-   `GET /api/conversations/{id}`: Returns all messages for a single conversation.
-   `POST /api/conversations/{id}/messages`: Allows a technician to send a new message to a conversation.
-   `GET /api/orders/{orderId}/conversations`: Returns all conversations associated with a specific order.

## 5. Web Interface

A web-based interface (`web/customer_service_app.py`) provides a user-friendly way to interact with the customer service module.

-   **Two-Column Layout:** The interface has a two-column layout, with a list of conversations in a sidebar on the left and the message view on the right.
-   **Dynamic Updates:** The interface uses JavaScript to dynamically fetch and display conversations and messages from the API.
-   **Send Messages:** Users can send new messages directly from the web interface.
