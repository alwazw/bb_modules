#!/bin/bash

# This script launches the web interfaces for the Fulfillment and Customer Service.
# It assumes that `setup.sh` has already been run successfully.

set -e

echo "--- Activating Python Virtual Environment ---"
source venv/bin/activate
echo

echo "========================================="
echo "  LAUNCHING CUSTOMER SERVICE WEB INTERFACE"
echo "========================================="
echo
echo "The web server will start now."
echo "You can access it from your browser, typically at http://<your_machine_ip>:5002"
echo
python3 customer_service/src/app.py &

echo "========================================="
echo "  LAUNCHING FULFILLMENT WEB INTERFACE"
echo "========================================="
echo
echo "The web server will start now."
echo "You can access it from your browser, typically at http://<your_machine_ip>:5001"
echo "Press CTRL+C to stop all servers."
echo

# Run the Flask application script.
# The app is configured in app.py to run on host 0.0.0.0, making it
# accessible across the local network.
python3 fulfillment_service/src/app.py &

# Wait for all background jobs to finish
wait
