#!/bin/bash

# This script launches the web interfaces for the Fulfillment and Customer Service.
# It uses Docker Compose to build and run the services.

set -e

echo "--- Starting Web Interfaces using Docker Compose ---"
sudo docker compose up --build
