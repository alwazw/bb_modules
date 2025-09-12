# Customer Service Module

This module provides a comprehensive suite of tools for managing customer communications from the Best Buy Marketplace. It includes a web-based interface for viewing and responding to messages, as well as an automated auto-reply bot.

## Key Components

*   **`message_aggregation/fetch_messages.py`**: This script connects to the Mirakl API and fetches all new customer messages, storing them in the database. It is the primary mechanism for ingesting customer communications.
*   **`src/logic.py`**: Contains the core business logic for the customer service module, including functions for retrieving conversations and messages from the database, and for sending messages to the Mirakl API.
*   **`src/auto_reply.py`**: This script contains the logic for the auto-reply bot. It checks for unanswered messages and sends templated replies based on a set of predefined rules.
*   **`web_interface/customer_service_app.py`**: The Flask web application that provides the user interface for viewing and responding to customer messages.

## Workflow

1.  **Message Sync**: The `main_customer_service.py` script is run on a schedule to execute the `fetch_messages.py` script. This keeps the local database in sync with the messages on the Best Buy Marketplace.
2.  **Auto-Reply**: The `main_auto_reply.py` script is also run on a schedule. This script executes the logic in `auto_reply.py` to send automated responses to customers who have not received a timely reply.
3.  **Manual Interaction**: A customer service agent can use the web interface (running on port 5002) to view all customer conversations, read messages, and send manual replies.

This module is designed to improve customer response times and ensure that no customer message goes unanswered.
