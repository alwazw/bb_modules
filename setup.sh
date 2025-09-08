#!/bin/bash

# This script performs the one-time setup for the entire application suite.
# It should be run once after cloning the repository.

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- 1. Starting Docker Services ---"
# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null
then
    echo "docker-compose could not be found. Please install it to continue."
    exit 1
fi
# Start the postgres database container in detached mode.
docker-compose up -d
echo "SUCCESS: PostgreSQL container started."
echo

echo "--- 2. Setting up Python Environment ---"
# Check for a virtual environment, create if it doesn't exist.
if [ ! -d "venv" ]; then
    echo "No virtual environment found. Creating one now..."
    python3 -m venv venv
    echo "SUCCESS: Virtual environment 'venv' created."
fi
# Activate the virtual environment.
source venv/bin/activate
echo "SUCCESS: Virtual environment activated."
echo

echo "--- 3. Installing Python Dependencies ---"
# Install dependencies for the core workflows and the web interface.
pip install -r requirements.txt
pip install -r fulfillment_service/requirements.txt
echo "SUCCESS: All Python dependencies installed."
echo

echo "--- 4. Initializing Database Schema ---"
# Run the db_utils script to create the tables.
# The 'yes' command automatically answers the confirmation prompt.
yes | python3 database/db_utils.py
echo "SUCCESS: Database schema initialized."
echo

echo "========================================="
echo "✅ SETUP COMPLETE"
echo "You can now run the application using:"
echo "   - ./run_core_workflows.sh (for backend processing)"
echo "   - ./run_web_interface.sh (for the web UI)"
echo "========================================="
