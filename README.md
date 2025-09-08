# Best Buy Marketplace - Python Automation Suite

This project provides a robust, database-driven automation suite for managing orders from the Best Buy Marketplace. It handles the end-to-end process from order acceptance to shipping and tracking, with a focus on reliability, logging, and scalability. It also includes a web-based interface to guide the physical fulfillment process.

## Architecture Overview

The application is built on a modern, database-centric architecture.

-   **Database Backend:** A **PostgreSQL** database serves as the single source of truth for all data, managed via **Docker**.
-   **Modular Workflows:** The backend logic is broken into distinct, orchestrated workflows for order acceptance, shipping, and tracking.
-   **Web Interface:** A **Flask**-based web application provides a user interface for the fulfillment process, helping to guide technicians and prevent errors.

For more detailed documentation on each module, the database schema, and the overall project vision, please refer to the files in the `/docs` directory.

## 🚀 Getting Started

Getting the application running locally is a simple, three-step process thanks to the new setup scripts.

### Step 1: One-Time Project Setup

First, run the master setup script. This will start the database, create a Python virtual environment, install all dependencies, and initialize the database schema.

```bash
# Make the script executable (you only need to do this once)
chmod +x setup.sh

# Run the setup
./setup.sh
```

### Step 2: Running the Backend Workflows

To process any pending orders, create shipping labels, and update tracking information, run the core workflows script.

```bash
# Make the script executable (you only need to do this once)
chmod +x run_core_workflows.sh

# Run the workflows
./run_core_workflows.sh
```
This script can be run manually as needed, or integrated into a scheduler like `cron` to run periodically (e.g., every 15 minutes).

### Step 3: Running the Web Interface

To launch the web-based fulfillment service, run the web interface script.

```bash
# Make the script executable (you only need to do this once)
chmod +x run_web_interface.sh

# Run the web server
./run_web_interface.sh
```
Once started, you can access the web interface from a browser on your local network, typically at `http://<your_machine_ip>:5001`.

---

*Note: You will need to create a `secrets.txt` file in the project root containing the necessary API keys for the Best Buy and Canada Post APIs.*
