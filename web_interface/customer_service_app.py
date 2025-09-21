# -*- coding: utf-8 -*-
"""
================================================================================
Customer Service Web Application
================================================================================
Purpose:
----------------
This script launches a Flask-based web application that serves as the graphical
user interface (GUI) for the customer service module. It provides two main
functions:
1.  **Web Interface**: It renders an HTML page where a customer service agent can
    view and manage customer conversations.
2.  **JSON API**: It provides a set of API endpoints that the frontend JavaScript
    can use to fetch conversation data, view messages, and send replies.

The application is designed to be run by a production-grade WSGI server like
Gunicorn (as configured in `supervisord.conf`), not by running this script directly.
----------------
"""

# =====================================================================================
# --- Imports and Setup ---
# =====================================================================================
from flask import Flask, request, jsonify, render_template, redirect, url_for
import os
import sys

# --- Project Path Setup ---
# This is crucial for ensuring that the application can find and import modules
# from other parts of the project, like the business logic in the 'customer_service'
# directory. It adds the project's root directory to Python's import search path.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the business logic functions from the customer service module.
# This keeps the web routes clean and separates the web layer from the data layer.
from customer_service.src import logic

# Initialize the Flask application.
# `template_folder` and `static_folder` tell Flask where to find the HTML templates
# and static assets (CSS, JavaScript), respectively.
app = Flask(__name__, template_folder='templates', static_folder='static')


# =====================================================================================
# --- HTML Page Routes ---
# =====================================================================================

@app.route('/')
def index():
    """
    The root URL of the application. It immediately redirects the user to the
    main conversations page.
    """
    # `url_for('show_conversations')` generates the URL for the `show_conversations`
    # function, which is '/conversations'.
    return redirect(url_for('show_conversations'))

@app.route('/conversations')
def show_conversations():
    """
    Renders the main conversations web interface.
    This route serves the single-page application's main HTML file. All the
    dynamic data is loaded asynchronously by the JavaScript on the page using
    the API endpoints below.
    """
    return render_template('customer_service/conversations.html')


# =====================================================================================
# --- JSON API Endpoints ---
# =====================================================================================
# These endpoints are designed to be called by the frontend JavaScript. They
# receive requests, call the appropriate business logic function, and return
# the data in JSON format.
# =====================================================================================

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """
    API endpoint to fetch a list of all customer conversations.
    The frontend calls this to populate the conversation list on the left sidebar.
    """
    conversations, error = logic.get_all_conversations()
    if error:
        # If the business logic returns an error, return a 500 Internal Server Error.
        return jsonify({"error": error}), 500
    return jsonify(conversations), 200

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """
    API endpoint to fetch the details and messages for a single conversation.
    The frontend calls this when a user clicks on a conversation in the sidebar.
    """
    # The `<int:conversation_id>` in the route path captures the ID from the URL.
    conversation, error = logic.get_conversation_by_id(conversation_id)
    if error:
        # Return a 404 Not Found if the conversation ID is invalid.
        return jsonify({"error": error}), 404
    return jsonify(conversation), 200

@app.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
def post_message(conversation_id):
    """
    API endpoint for sending a new message from a customer service agent.
    The frontend calls this when the user types a reply and clicks 'Send'.
    """
    # Get the JSON payload from the incoming request.
    data = request.get_json()
    if not data or 'body' not in data:
        # Basic validation to ensure a message body was sent.
        return jsonify({"error": "Message body is required"}), 400

    # Call the business logic to add the message to the database and send it
    # via the Best Buy API.
    message, error = logic.add_message_to_conversation(conversation_id, data)
    if error:
        return jsonify({"error": error}), 500
    # Return the newly created message object with a 201 Created status.
    return jsonify(message), 201

@app.route('/api/orders/<order_id>/conversations', methods=['GET'])
def get_order_conversations(order_id):
    """
    API endpoint to fetch all conversations associated with a specific order ID.
    This could be used for a feature that shows conversation history on an order page.
    """
    conversations, error = logic.get_conversations_by_order_id(order_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(conversations), 200


# =====================================================================================
# --- Direct Execution (for development) ---
# =====================================================================================
if __name__ == '__main__':
    # This block allows the Flask development server to be run directly for testing.
    # `debug=True` enables auto-reloading when code changes.
    # `host='0.0.0.0'` makes the server accessible from outside the container.
    # For production, a proper WSGI server like Gunicorn should be used instead.
    app.run(debug=True, host='0.0.0.0', port=5002)
