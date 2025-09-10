#!/bin/bash

# This script runs all the unit tests for the project.

set -e

echo "--- Running Unit Tests ---"
python -m unittest discover -s tests
