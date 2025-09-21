# -*- coding: utf-8 -*-
"""
================================================================================
Fulfillment Service Web Application
================================================================================
Purpose:
----------------
This script launches a Flask-based web application for the fulfillment service.
It provides a user interface for warehouse staff to assemble orders by scanning
the barcodes of computer components.

The application uses a simple in-memory dictionary (`fulfillment_sessions`) to
manage the state of each order being assembled. This is a temporary solution
and is not suitable for a production environment with multiple workers, as the
session data would not be shared.

Key Features:
- **Web Interface**: Renders an HTML page for a specific order, showing the
  required components and which ones have been scanned.
- **API for Scanning**: Provides an API endpoint (`/api/fulfillment/scan`) that
  the frontend JavaScript calls every time a barcode is scanned.
- **API for Finalization**: An endpoint (`/api/fulfillment/finalize`) to mark
  the order as fully assembled, which then triggers the shipping label
  generation process.

NOTE: This module currently has a significant architectural flaw. It relies on
a file-based data source (`processed_orders.json`) and an in-memory session,
while other parts of the system are database-driven. This will need to be
refactored to use the PostgreSQL database for a production-ready system.
----------------
"""

# =====================================================================================
# --- Imports and Setup ---
# =====================================================================================
from flask import Flask, request, jsonify, render_template, redirect, url_for
import os
import sys

# --- Project Path Setup ---
# Allows the script to import modules from other directories in the project.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the business logic for the fulfillment service.
from fulfillment_service.src import logic

# Initialize the Flask application.
app = Flask(__name__, template_folder='templates')

# --- In-Memory Session Storage ---
# WARNING: This is a temporary, non-production solution.
# This dictionary stores the state of each active fulfillment session.
# The key is the order_id, and the value is another dictionary containing the
# order details, required components, and a set of scanned components.
# In a real-world scenario, this state should be stored in a shared cache like
# Redis or in the database to support multiple workers and prevent data loss.
fulfillment_sessions = {}


# =====================================================================================
# --- HTML Page Routes ---
# =====================================================================================

@app.route('/fulfillment')
def index():
    """
    The root URL for the fulfillment service.
    Currently, it redirects to a hardcoded default order for demonstration purposes.
    In a real application, this would likely be a dashboard showing all orders
    that are ready for fulfillment.
    """
    return redirect(url_for('fulfillment_page', order_id='261305911-A'))

@app.route('/fulfillment/<order_id>')
def fulfillment_page(order_id):
    """
    Renders the main fulfillment page for a given order.

    If this is the first time this order is being accessed, it fetches the
    order details and required components from the business logic layer and
    initializes a new session in the `fulfillment_sessions` dictionary.

    Args:
        order_id (str): The ID of the order to be fulfilled.

    Returns:
        Rendered HTML page or an error message.
    """
    # If we don't have a session for this order yet, create one.
    if order_id not in fulfillment_sessions:
        work_order, error = logic.get_work_order_details(order_id)
        if error:
            return f"Error: {error}", 404

        # Initialize the session for this order.
        fulfillment_sessions[order_id] = {
            "order": work_order['order'],
            "required_components": work_order['required_components'],
            "scanned_components": set()  # Using a set for efficient add/check operations.
        }

    session_data = fulfillment_sessions[order_id]
    # Render the HTML template, passing in all the necessary data.
    return render_template('fulfillment_service/fulfillment.html',
                           order_id=order_id,
                           order_data=session_data['order'],
                           required_components=session_data['required_components'],
                           scanned_components=list(session_data['scanned_components']))


# =====================================================================================
# --- JSON API Endpoints ---
# =====================================================================================

@app.route('/api/fulfillment/scan', methods=['POST'])
def scan_component():
    """
    API endpoint to validate a scanned component barcode against the active order.

    The frontend JavaScript calls this endpoint via a POST request every time
    the user "scans" a barcode in the input field.

    Expects a JSON body like: {"order_id": "...", "barcode": "..."}
    """
    data = request.get_json()
    if not data or 'order_id' not in data or 'barcode' not in data:
        return jsonify({"error": "order_id and barcode are required"}), 400

    order_id = data['order_id']
    barcode = data['barcode']

    session = fulfillment_sessions.get(order_id)
    if not session:
        return jsonify({"error": "Fulfillment not started for this order"}), 404

    required_barcodes = session['required_components'].keys()

    # --- Validation Logic ---
    # 1. Check if the scanned barcode is valid for this order.
    if barcode not in required_barcodes:
        return jsonify({
            "message": "Invalid component for this order.",
            "order_id": order_id,
            "barcode": barcode,
            "validation_status": "fail"
        }), 400

    # 2. Check if this component has already been scanned.
    component_name = session['required_components'][barcode]
    if component_name in session['scanned_components']:
        return jsonify({
            "message": "Component already scanned.",
            "order_id": order_id,
            "barcode": barcode,
            "validation_status": "duplicate"
        }), 400

    # If validation passes, add the component to the set of scanned items.
    session['scanned_components'].add(component_name)

    return jsonify({
        "message": f"Component '{component_name}' scanned successfully.",
        "order_id": order_id,
        "barcode": barcode,
        "validation_status": "success"
    }), 200

@app.route('/api/fulfillment/finalize', methods=['POST'])
def finalize_fulfillment():
    """
    API endpoint to finalize the assembly process and trigger shipping label generation.

    The frontend calls this when the user clicks the "Finalize Order" button.

    Expects a JSON body like: {"order_id": "..."}
    """
    data = request.get_json()
    if not data or 'order_id' not in data:
        return jsonify({"error": "order_id is required"}), 400

    order_id = data['order_id']
    session = fulfillment_sessions.get(order_id)

    if not session:
        return jsonify({"error": "Fulfillment not started for this order"}), 404

    # --- Final Validation ---
    # Ensure all required components have been scanned before proceeding.
    if len(session['scanned_components']) != len(session['required_components']):
        missing = [name for barcode, name in session['required_components'].items() if name not in session['scanned_components']]
        return jsonify({
            "error": "Not all required components have been scanned.",
            "missing_components": missing
        }), 400

    # --- Trigger Shipping ---
    # If everything is correct, call the business logic to generate the label.
    label_info, error = logic.generate_shipping_label(session['order'])
    if error:
        return jsonify({"error": f"Label generation failed: {error}"}), 500

    # Clean up the in-memory session for this order.
    del fulfillment_sessions[order_id]

    return jsonify({
        "message": "Fulfillment process finalized successfully.",
        "order_id": order_id,
        "tracking_number": label_info['tracking_pin'],
        "label_path": label_info['pdf_path']
    }), 200


# =====================================================================================
# --- Direct Execution (for development) ---
# =====================================================================================
if __name__ == '__main__':
    # This block allows the Flask development server to be run directly for testing.
    # For production, a proper WSGI server like Gunicorn should be used.
    app.run(debug=True, host='0.0.0.0', port=5001)
