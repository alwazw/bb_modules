import unittest
import os
import sys
import json
from unittest.mock import patch, mock_open
from datetime import datetime, timedelta, timezone

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from customer_service.message_aggregation import fetch_messages
from web_interface.customer_service_app import app

class TestMessageSync(unittest.TestCase):

    @patch('customer_service.message_aggregation.fetch_messages.datetime')
    def test_load_last_sync_timestamp_no_file(self, mock_dt):
        """
        Test that load_last_sync_timestamp returns a recent timestamp when the file doesn't exist.
        """
        mock_now = datetime(2023, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = mock_now
        expected_timestamp = (mock_now - timedelta(days=30)).isoformat()

        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = FileNotFoundError
            timestamp = fetch_messages.load_last_sync_timestamp()
            self.assertEqual(timestamp, expected_timestamp)


    def test_load_last_sync_timestamp_with_file(self):
        """
        Test that load_last_sync_timestamp reads the timestamp from the file.
        """
        mock_timestamp = "2023-01-01T12:00:00+00:00"
        with patch("builtins.open", mock_open(read_data=mock_timestamp)) as mock_file:
            timestamp = fetch_messages.load_last_sync_timestamp()
            self.assertEqual(timestamp, mock_timestamp)

    @patch("os.makedirs")
    def test_save_last_sync_timestamp(self, mock_makedirs):
        """
        Test that save_last_sync_timestamp writes the timestamp to the file.
        """
        mock_timestamp = "2023-01-01T13:00:00+00:00"
        with patch("builtins.open", mock_open()) as mock_file:
            fetch_messages.save_last_sync_timestamp(mock_timestamp)
            mock_makedirs.assert_called_once_with(os.path.dirname(fetch_messages.TIMESTAMP_FILE), exist_ok=True)
            mock_file.assert_called_once_with(fetch_messages.TIMESTAMP_FILE, "w")
            mock_file().write.assert_called_once_with(mock_timestamp)

class TestCustomerServiceAPI(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('customer_service.src.logic.get_all_conversations')
    def test_get_conversations_success(self, mock_get_all_conversations):
        """
        Test GET /api/conversations success
        """
        mock_conversations = [{"id": 1, "subject": "Test"}]
        mock_get_all_conversations.return_value = mock_conversations, None

        response = self.app.get('/api/conversations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), mock_conversations)

    @patch('customer_service.src.logic.get_conversation_by_id')
    def test_get_conversation_by_id_success(self, mock_get_conversation_by_id):
        """
        Test GET /api/conversations/<id> success
        """
        mock_conversation = [{"id": 1, "body": "Test message"}]
        mock_get_conversation_by_id.return_value = mock_conversation, None

        response = self.app.get('/api/conversations/1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), mock_conversation)

    @patch('customer_service.src.logic.add_message_to_conversation')
    def test_post_message_success(self, mock_add_message_to_conversation):
        """
        Test POST /api/conversations/<id>/messages success
        """
        mock_message = {"id": 1, "body": "New message"}
        mock_add_message_to_conversation.return_value = mock_message, None

        response = self.app.post('/api/conversations/1/messages',
                                 data=json.dumps({"body": "New message"}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.data), mock_message)

    @patch('customer_service.src.logic.get_conversations_by_order_id')
    def test_get_conversations_by_order_id_success(self, mock_get_conversations_by_order_id):
        """
        Test GET /api/orders/<orderId>/conversations success
        """
        mock_conversations = [{"id": 1, "subject": "Test"}]
        mock_get_conversations_by_order_id.return_value = mock_conversations, None

        response = self.app.get('/api/orders/123/conversations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), mock_conversations)


if __name__ == '__main__':
    unittest.main()
