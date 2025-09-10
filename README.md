# Best Buy Marketplace - Python Automation Suite

This project provides a robust, database-driven automation suite for managing orders from the Best Buy Marketplace. It handles the end-to-end process from order acceptance to shipping and tracking, with a focus on reliability, logging, and scalability. It also includes web-based interfaces for fulfillment and customer service.

## Architecture Overview

The application is built on a modern, Docker-based architecture.

-   **Database Backend:** A **PostgreSQL** database serves as the single source of truth for all data.
-   **Application Services:** The backend logic is broken into distinct, orchestrated workflows. The web interfaces are served by Flask applications.
-   **Containerization:** The entire application stack (database and web applications) is managed via **Docker and Docker Compose**, ensuring a consistent and reproducible environment.

For more detailed documentation on each module, the database schema, and the overall project vision, please refer to the files in the `/docs` directory.

## 🚀 Getting Started

Getting the application running locally is a simple, two-step process thanks to the new Docker-based setup.

### Step 1: One-Time Project Setup

First, run the master setup script. This will build the Docker images and initialize the database schema.

```bash
# Make the script executable (you only need to do this once)
chmod +x setup.sh

# Run the setup
./setup.sh
```

### Step 2: Running the Application

To run the entire application stack (backend workflows and web interfaces), use the `docker-compose` command or the provided helper script.

```bash
# To run the web interfaces (and the database)
chmod +x run_web_interface.sh
./run_web_interface.sh

# To run the backend workflows (order acceptance, shipping, etc.)
chmod +x run_core_workflows.sh
./run_core_workflows.sh
```

Once started, you can access the web interfaces from a browser:
-   **Fulfillment Service:** `http://localhost:5001`
-   **Customer Service:** `http://localhost:5002/conversations`

---

*Note: You will need to create a `secrets.txt` file in the project root containing the necessary API keys for the Best Buy and Canada Post APIs.*
