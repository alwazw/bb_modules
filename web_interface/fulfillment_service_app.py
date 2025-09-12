from flask import Flask, request, jsonify, render_template, redirect, url_for
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fulfillment_service.src import logic

app = Flask(__name__, template_folder='templates')

# In-memory storage for fulfillment sessions.
fulfillment_sessions = {}

@app.route('/fulfillment')
def index():
    # For demonstration, redirect to a default order.
    # In a real app, you might have a dashboard of orders.
    return redirect(url_for('fulfillment_page', order_id='261305911-A'))

@app.route('/fulfillment/<order_id>')
def fulfillment_page(order_id):
    """Render the fulfillment page for a given order."""
    if order_id not in fulfillment_sessions:
        work_order, error = logic.get_work_order_details(order_id)
        if error:
            return f"Error: {error}", 404

        fulfillment_sessions[order_id] = {
            "order": work_order['order'],
            "required_components": work_order['required_components'],
            "scanned_components": set()
        }

    session_data = fulfillment_sessions[order_id]
    return render_template('fulfillment_service/fulfillment.html',
                           order_id=order_id,
                           order_data=session_data['order'],
                           required_components=session_data['required_components'],
                           scanned_components=list(session_data['scanned_components']))

@app.route('/api/fulfillment/start', methods=['POST'])
def start_fulfillment():
    """
    Initializes a new fulfillment process for a given order.
    Expects JSON body: {"order_id": "some-order-id"}
    """
    data = request.get_json()
    if not data or 'order_id' not in data:
        return jsonify({"error": "order_id is required in the request body"}), 400

    order_id = data['order_id']

    if order_id in fulfillment_sessions:
        return jsonify({"error": f"Fulfillment for order '{order_id}' is already in progress"}), 409

    work_order, error = logic.get_work_order_details(order_id)
    if error:
        return jsonify({"error": error}), 404

    # Store the entire work order details in the session
    fulfillment_sessions[order_id] = {
        "status": "in_progress",
        "order": work_order['order'],
        "required_components": work_order['required_components'], # map of barcode -> component name
        "scanned_components": set()
    }

    return jsonify({
        "message": "Fulfillment process started successfully.",
        "order_id": order_id,
        "required_components": list(work_order['required_components'].values())
    }), 201

@app.route('/api/fulfillment/scan', methods=['POST'])
def scan_component():
    """
    Validates a component barcode against the active order.
    Expects JSON body: {"order_id": "some-order-id", "barcode": "some-barcode"}
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

    if barcode not in required_barcodes:
        return jsonify({
            "message": "Invalid component for this order.",
            "order_id": order_id,
            "barcode": barcode,
            "validation_status": "fail"
        }), 400

    component_name = session['required_components'][barcode]
    if component_name in session['scanned_components']:
        return jsonify({
            "message": "Component already scanned.",
            "order_id": order_id,
            "barcode": barcode,
            "validation_status": "duplicate"
        }), 400

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
    Finalizes the assembly and triggers shipping label generation.
    Expects JSON body: {"order_id": "some-order-id"}
    """
    data = request.get_json()
    if not data or 'order_id' not in data:
        return jsonify({"error": "order_id is required"}), 400

    order_id = data['order_id']
    session = fulfillment_sessions.get(order_id)

    if not session:
        return jsonify({"error": "Fulfillment not started for this order"}), 404

    # Verify all components were scanned
    if len(session['scanned_components']) != len(session['required_components']):
        return jsonify({
            "error": "Not all required components have been scanned.",
            "missing_components": [name for barcode, name in session['required_components'].items() if name not in session['scanned_components']]
        }), 400

    # Trigger real shipping label generation
    label_info, error = logic.generate_shipping_label(session['order'])
    if error:
        return jsonify({"error": f"Label generation failed: {error}"}), 500

    # Clean up the session
    del fulfillment_sessions[order_id]

    return jsonify({
        "message": "Fulfillment process finalized successfully.",
        "order_id": order_id,
        "tracking_number": label_info['tracking_pin'],
        "label_path": label_info['pdf_path']
    }), 200

if __name__ == '__main__':
    # This allows running the app directly for development and testing.
    # For production, a proper WSGI server like Gunicorn or uWSGI should be used.
    app.run(debug=True, host='0.0.0.0', port=5001)
