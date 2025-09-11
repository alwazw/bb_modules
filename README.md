# Best Buy Marketplace - Python Automation Suite

This project is a comprehensive, database-driven automation suite for managing a Best Buy Marketplace store. It handles the entire lifecycle of an order, from acceptance and inventory management to shipping, tracking, and customer service. The suite is designed for reliability and scalability, featuring detailed logging and containerized deployment.

## Core Architecture

The application is built on a modern, Docker-based architecture to ensure consistency and ease of deployment.

-   **Database Backend:** A **PostgreSQL** database serves as the single source of truth for all order, customer, and inventory data. This ensures data integrity and provides a solid foundation for all modules.
-   **Application Services:** The backend logic is broken into distinct modules, each responsible for a specific part of the business process. These modules are designed to be run as scheduled workflows.
-   **Web Interfaces:** The project includes two web-based GUIs built with **Flask** for managing fulfillment and customer service tasks.
-   **Containerization:** The entire application stack (database, web applications, and backend services) is managed via **Docker and Docker Compose**, allowing for a one-command setup.

For detailed documentation on each module, the database schema, and the overall project vision, please refer to the files in the `/documentation` directory.

## Modules Overview

The project is divided into several key modules:

-   **Order Management:** Handles the initial acceptance of new orders from the marketplace.
-   **Inventory:** Manages product and component data.
-   **Shipping:** Responsible for creating shipping labels (initially with Canada Post) and managing the shipping process.
-   **Tracking:** Updates the marketplace with tracking information after an order has been shipped.
-   **Fulfillment Service:** Provides a web interface for fulfillment tasks.
-   **Customer Service:** Includes a web interface for managing customer conversations and a new auto-reply bot to handle initial customer messages.
-   **Accounting:** Fetches and analyzes transaction data from the marketplace.
-   **Offers & Catalog:** Manages product offers and catalog information.

## 🚀 Getting Started

Getting the application running locally is a simple, two-step process.

### Prerequisites

-   Docker and Docker Compose must be installed on your system.

### Step 1: One-Time Project Setup

First, run the master setup script. This will build the Docker images, initialize the database schema, and create the necessary directories for persistent storage.

```bash
# Make the setup script executable (you only need to do this once)
chmod +x setup.sh

# Run the setup
./setup.sh
```

### Step 2: Running the Application

To run the entire application stack, use the `docker-compose` command or the provided helper script.

```bash
# To run the web interfaces (and the database)
# This will start the Fulfillment and Customer Service GUIs.
chmod +x run_web_interface.sh
./run_web_interface.sh
```

Once started, you can access the web interfaces from your browser:
-   **Fulfillment Service:** `http://localhost:5001`
-   **Customer Service:** `http://localhost:5002/conversations`

To run the backend workflows (order acceptance, shipping, etc.), use the `run_core_workflows.sh` script. This is typically done on a schedule (e.g., via a cron job).

```bash
chmod +x run_core_workflows.sh
./run_core_workflows.sh
```

## Important Notes

-   **API Keys:** You must create a `secrets.txt` file in the project root containing the necessary API keys for the Best Buy and Canada Post APIs.
-   **Persistent Storage:** The application uses a `persistent_storage` directory at the project root to store generated files like PDF shipping labels and logs. This directory is created automatically by the `setup.sh` script and is mounted into the Docker containers to ensure data persists even if the containers are removed. The database data is also persisted using a named Docker volume (`postgres_data`).
