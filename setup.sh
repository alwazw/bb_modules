#!/bin/bash

# This script performs the one-time setup for the entire application suite.
# It should be run once after cloning the repository.

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- 1. Checking for Docker ---"
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo "Docker and/or docker-compose could not be found. Please install them to continue."
    exit 1
fi
echo "SUCCESS: Docker and docker-compose are installed."
echo

echo "--- 2. Building Docker Images ---"
docker-compose build
echo "SUCCESS: Docker images built successfully."
echo

echo "--- 3. Starting Database Service ---"
docker-compose up -d postgres-db
echo "SUCCESS: PostgreSQL container started."
echo

echo "--- 4. Initializing Database Schema ---"
echo "Waiting for PostgreSQL to be ready..."
sleep 10 # Simple wait, a more robust solution would be to poll the DB.
docker-compose run --rm web python database/db_utils.py --init
echo "SUCCESS: Database schema initialized."
echo

echo "========================================="
echo "✅ SETUP COMPLETE"
echo "You can now run the application using:"
echo "   - ./run_core_workflows.sh (for backend processing)"
echo "   - ./run_web_interface.sh (for the web UI)"
echo "========================================="
