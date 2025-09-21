# Setup and Deployment Guide

## Introduction

This guide provides comprehensive, step-by-step instructions for setting up the development environment and deploying the Best Buy Order Automation application. The entire system is containerized using Docker and Docker Compose, which makes the setup process reliable and consistent across different machines.

The goal is to get a fully functional instance of the application running, including the backend database, the web interfaces, and the command-line workflows.

## 1. Prerequisites

Before you begin, you must have the following software installed on your system. These are the only two dependencies required on your host machine.

-   **Docker**: The containerization platform used to build and run the application's services. For installation instructions, visit the [official Docker website](https://docs.docker.com/get-docker/).
-   **Docker Compose**: A tool for defining and running multi-container Docker applications. It allows us to manage our entire application stack with a single command. It is typically included with Docker Desktop, but if you need to install it separately, see the [official documentation](https://docs.docker.com/compose/install/).

You can verify your installation by running:
```bash
docker --version
docker compose version
```

## 2. One-Time Project Setup

This is a one-time process that prepares the entire project. It creates necessary directories, builds the custom Docker images, and initializes the database schema.

1.  **Clone the Repository:**
    First, clone the project repository from GitHub to your local machine.
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create the `secrets.txt` File:**
    The application requires a `secrets.txt` file in the project root to store sensitive API credentials. The Docker build process will fail if this file is not present.

    Create the file in the root of the project. You can do this with the `touch` command:
    ```bash
    touch secrets.txt
    ```

3.  **Run the Master Setup Script:**
    The `setup.sh` script is the master key to setting up the project. It automates several critical steps:
    -   Creates a `persistent_storage` directory for logs and generated PDF labels.
    -   Builds the custom Docker images defined in `docker-compose.yml`.
    -   Starts the PostgreSQL database container.
    -   Waits for the database to be ready.
    -   Runs a one-off container to execute the `database/schema.sql` script, which creates all the necessary tables and relationships.

    Make the script executable and run it:
    ```bash
    # This command gives the script permission to be executed.
    chmod +x setup.sh

    # This command runs the setup process.
    ./setup.sh
    ```
    This process may take a few minutes the first time as it downloads the necessary Docker images.

## 3. Configuration

All sensitive information is managed via the `secrets.txt` file. This file is intentionally excluded from version control (via `.gitignore`) to prevent credentials from being accidentally committed.

Open `secrets.txt` and add the following keys, replacing the placeholder values with your actual credentials.

```ini
# Best Buy Marketplace API Key
# This is required for all interactions with the Best Buy API.
BEST_BUY_API_KEY=your_best_buy_api_key_here

# Canada Post Production API Credentials
# These are required for generating shipping labels.
CANADA_POST_API_USER=your_production_api_user_here
CANADA_POST_API_PASSWORD=your_production_api_password_here
CANADA_POST_CUSTOMER_NUMBER=your_10_digit_customer_number_here
CANADA_POST_PAID_BY_CUSTOMER=your_10_digit_paid_by_customer_number_here
CANADA_POST_CONTRACT_ID=your_10_digit_contract_id_here
```

## 4. Running the Application

The application is divided into two main parts, which can be run independently: the web interfaces and the backend workflows.

### Running the Web Interfaces

The web interfaces provide a GUI for managing fulfillment and customer service.

1.  **Make the script executable:**
    ```bash
    chmod +x run_web_interface.sh
    ```

2.  **Start the services:**
    This script uses `docker compose up` to start all services defined in `docker-compose.yml` in detached mode (`-d`), including the web apps, the database, Redis, and PgAdmin.
    ```bash
    ./run_web_interface.sh
    ```

3.  **Access the GUIs:**
    Once the containers are running, you can access the web interfaces from your browser:
    -   **Fulfillment Service:** `http://localhost:5001/fulfillment`
    -   **Customer Service:** `http://localhost:5002/conversations`
    -   **PgAdmin (Database GUI):** `http://localhost:5050`
    -   **Grafana (Monitoring):** `http://localhost:3000`

### Running the Backend Workflows

The backend workflows are the core automated processes that handle order acceptance, shipping label creation, and tracking updates.

1.  **Make the script executable:**
    ```bash
    chmod +x run_core_workflows.sh
    ```

2.  **Run the workflows:**
    This script executes the main entry point scripts (`main_acceptance.py`, `main_shipping.py`, etc.) inside a new, temporary Docker container. This ensures the workflows run with the correct dependencies and environment variables.
    ```bash
    ./run_core_workflows.sh
    ```
    This script is designed for manual execution or to be run by a scheduling system like `cron`.
