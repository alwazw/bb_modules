#!/bin/bash

# This script runs the main data processing workflows in sequence.
# It assumes that `setup.sh` has already been run successfully.

set -e

echo "========================================="
echo "  RUNNING CORE WORKFLOWS"
echo "========================================="

echo
echo ">>> STEP 1: Running Order Acceptance Workflow..."
sudo docker compose exec web python3 main_acceptance.py
echo "--- Order Acceptance Finished ---"
echo

# A short pause between workflows can sometimes be beneficial
sleep 5

echo ">>> STEP 2: Running Shipping Label Creation Workflow..."
sudo docker compose exec web python3 main_shipping.py
echo "--- Shipping Label Creation Finished ---"
echo

sleep 5

echo ">>> STEP 3: Running Tracking Update Workflow..."
sudo docker compose exec web python3 main_tracking.py
echo "--- Tracking Update Finished ---"
echo

echo "========================================="
echo "✅ ALL CORE WORKFLOWS COMPLETE"
echo "========================================="
