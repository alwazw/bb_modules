# Best Buy Marketplace - Python Automation Suite

This project provides a robust, database-driven automation suite for managing orders from the Best Buy Marketplace. It handles the end-to-end process from order acceptance to shipping and tracking, with a focus on reliability, logging, and scalability.

## Architecture Overview

The application has been refactored from a script-based, JSON file-driven system to a modern, database-centric architecture.

-   **Database Backend:** At its core, the application uses a **PostgreSQL** database to store all order data, logs, and workflow states. This provides data integrity, scalability, and a single source of truth.
-   **Containerization:** The database and its environment are managed via **Docker and Docker Compose**, ensuring a consistent and easy-to-set-up development environment.
-   **Modular Workflows:** The logic for each major process (e.g., Order Acceptance) is encapsulated in its own workflow module, providing a clean separation of concerns.
-   **Configuration:** The system is configured through environment variables, allowing for flexible deployment across different environments (dev, staging, prod) without code changes.

## Project Modules

The project is broken down into several key modules:

-   **`order_management`**: Handles the initial ingestion and acceptance of new orders from Best Buy. This module is responsible for the crucial first step of acknowledging an order and preparing it for the next phase.
-   **`shipping`**: Manages the creation of shipping labels via the Canada Post API for orders that are ready for fulfillment.
-   **`tracking`**: Updates Best Buy with the new tracking information and marks the order as shipped.
-   **`database`**: Contains all database-related utilities, including the master `schema.sql` file, connection helpers, and migration scripts.
-   **Other Modules**: `accounting`, `customer_service`, `catalog`, etc., are other components of the larger system.

For more detailed documentation on each module and the overall project vision, please refer to the files in the `/docs` directory.

## 🚀 Getting Started

Follow these steps to set up and run the application locally.

### 1. Prerequisites

-   [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/)
-   Python 3.8+
-   A `secrets.txt` file in the project root (this is not tracked by git). See `common/utils.py` for details on what keys are needed (e.g., `BEST_BUY_API_KEY`).

### 2. Environment Setup

1.  **Clone the Repository:**
    `git clone <repository_url>`

2.  **Start the Database:**
    Navigate to the project root and run Docker Compose. This will start the PostgreSQL database in a container.
    ```bash
    docker-compose up -d
    ```

3.  **Set Up Python Environment:**
    It is highly recommended to use a virtual environment.
    ```bash
    # Create a virtual environment
    python3 -m venv venv

    # Activate it
    source venv/bin/activate  # On macOS/Linux
    # .\venv\Scripts\activate  # On Windows
    ```

4.  **Install Dependencies:**
    The required Python libraries are `requests`, `psycopg2-binary`, and `PyPDF2` (for shipping label validation).
    ```bash
    pip install requests psycopg2-binary PyPDF2
    ```

5.  **Initialize the Database Schema:**
    Run the database utility script to create all the necessary tables. You will be prompted to confirm this action.
    ```bash
    python3 database/db_utils.py
    ```
    *Note: This is a destructive operation that will drop and recreate tables if they already exist.*

6.  **(Optional) Migrate Old Data:**
    If you have old data in the legacy JSON files (`logs/best_buy/pending_acceptance.json`, etc.), you can migrate it to the new database by running:
    ```bash
    python3 database/migrate_json_to_db.py
    ```

### 3. Running the Application

Each major workflow has its own main entry point script.

```bash
# Run the Order Acceptance workflow
python3 main_acceptance.py

# Run the Shipping Label Creation workflow (once refactored)
# python3 main_shipping.py

# Run the Tracking Update workflow (once refactored)
# python3 main_tracking.py
```

### 4. Running Tests

To run the entire test suite:
```bash
python3 -m unittest discover tests
```
*Note: Some older, out-of-scope tests may currently be disabled in the repository to allow for a clean test run of the core modules. These are named with a leading underscore (e.g., `_test_accounting.py`).*
