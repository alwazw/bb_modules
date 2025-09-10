from flask import Flask, request, jsonify
from . import logic
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

app = Flask(__name__)

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """
    Returns a list of all conversations.
    """
    conversations, error = logic.get_all_conversations()
    if error:
        return jsonify({"error": error}), 500
    return jsonify(conversations), 200

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """
    Returns a single conversation by its ID.
    """
    conversation, error = logic.get_conversation_by_id(conversation_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(conversation), 200

@app.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
def post_message(conversation_id):
    """
    Adds a new message to a conversation.
    """
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify({"error": "Message body is required"}), 400

    message, error = logic.add_message_to_conversation(conversation_id, data)
    if error:
        return jsonify({"error": error}), 500
    return jsonify(message), 201

@app.route('/api/orders/<order_id>/conversations', methods=['GET'])
def get_order_conversations(order_id):
    """
    Returns all conversations for a given order ID.
    """
    conversations, error = logic.get_conversations_by_order_id(order_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(conversations), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
