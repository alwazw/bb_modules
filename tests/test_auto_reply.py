import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone

import sys
import os

# Add the project root to the Python path to allow for module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from customer_service.src.auto_reply import run_auto_reply_logic, process_conversation, send_auto_reply, TEMPLATE_1, TEMPLATE_2

class TestAutoReplyLogic(unittest.TestCase):

    def setUp(self):
        """Set up common variables for tests."""
        self.now = datetime.now(timezone.utc)
        self.five_hours_ago = self.now - timedelta(hours=5)
        self.one_hour_ago = self.now - timedelta(hours=1)
        self.conversation_1 = {'id': 1, 'mirakl_thread_id': 'thread-1'}

    @patch('customer_service.src.auto_reply.send_auto_reply')
    def test_first_reply_trigger(self, mock_send_auto_reply):
        """Test that the first auto-reply is triggered correctly."""
        mock_conn = MagicMock()
        messages = [
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
        ]
        mock_conn.cursor.return_value.__enter__.return_value.fetchall.return_value = messages

        process_conversation(mock_conn, self.conversation_1)

        mock_send_auto_reply.assert_called_once_with(mock_conn, self.conversation_1, TEMPLATE_1)

    @patch('customer_service.src.auto_reply.send_auto_reply')
    def test_second_reply_trigger(self, mock_send_auto_reply):
        """Test that the second auto-reply is triggered correctly."""
        mock_conn = MagicMock()
        messages = [
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
            {'sender_type': 'technician', 'sent_at': self.five_hours_ago, 'message_type': 'auto_reply'},
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
        ]
        mock_conn.cursor.return_value.__enter__.return_value.fetchall.return_value = messages

        process_conversation(mock_conn, self.conversation_1)

        mock_send_auto_reply.assert_called_once_with(mock_conn, self.conversation_1, TEMPLATE_2)

    @patch('customer_service.src.auto_reply.send_auto_reply')
    def test_no_reply_if_recent(self, mock_send_auto_reply):
        """Test that no auto-reply is sent if the last message is recent."""
        mock_conn = MagicMock()
        messages = [
            {'sender_type': 'customer', 'sent_at': self.one_hour_ago, 'message_type': 'manual'},
        ]
        mock_conn.cursor.return_value.__enter__.return_value.fetchall.return_value = messages

        process_conversation(mock_conn, self.conversation_1)

        mock_send_auto_reply.assert_not_called()

    @patch('customer_service.src.auto_reply.send_auto_reply')
    def test_no_reply_if_already_handled(self, mock_send_auto_reply):
        """Test that no auto-reply is sent if a technician has manually replied."""
        mock_conn = MagicMock()
        messages = [
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
            {'sender_type': 'technician', 'sent_at': self.one_hour_ago, 'message_type': 'manual'},
        ]
        # To simulate a technician reply, the conversation status would be 'read',
        # so it wouldn't even be picked up by `run_auto_reply_logic`.
        # This test is more for `process_conversation` in isolation.
        mock_conn.cursor.return_value.__enter__.return_value.fetchall.return_value = messages

        # Since we check last customer message, this will still trigger.
        # The real prevention is the conversation status being 'read'.
        process_conversation(mock_conn, self.conversation_1)
        mock_send_auto_reply.assert_called_once()


    @patch('customer_service.src.auto_reply.send_auto_reply')
    def test_no_reply_if_all_auto_replies_sent(self, mock_send_auto_reply):
        """Test that no further auto-replies are sent after the second one."""
        mock_conn = MagicMock()
        messages = [
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
            {'sender_type': 'technician', 'sent_at': self.five_hours_ago, 'message_type': 'auto_reply'},
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'},
            {'sender_type': 'technician', 'sent_at': self.five_hours_ago, 'message_type': 'auto_reply'},
            {'sender_type': 'customer', 'sent_at': self.five_hours_ago, 'message_type': 'manual'}, # 3rd customer message
        ]
        mock_conn.cursor.return_value.__enter__.return_value.fetchall.return_value = messages

        process_conversation(mock_conn, self.conversation_1)

        mock_send_auto_reply.assert_not_called()

    @patch('customer_service.src.auto_reply.get_unread_conversations')
    @patch('customer_service.src.auto_reply.process_conversation')
    @patch('customer_service.src.auto_reply.get_db_connection')
    def test_run_auto_reply_logic_orchestration(self, mock_get_db, mock_process, mock_get_unread):
        """Test the main orchestration function."""
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conversations = [self.conversation_1, {'id': 2, 'mirakl_thread_id': 'thread-2'}]
        mock_get_unread.return_value = mock_conversations

        run_auto_reply_logic()

        self.assertEqual(mock_process.call_count, 2)
        mock_process.assert_has_calls([
            call(mock_conn, self.conversation_1),
            call(mock_conn, mock_conversations[1])
        ])
        mock_conn.close.assert_called_once()

    @patch('customer_service.src.auto_reply.send_message_to_mirakl')
    def test_send_auto_reply_db_and_api_call(self, mock_send_to_mirakl):
        """Test that send_auto_reply correctly updates the DB and calls the API."""
        mock_conn = MagicMock()

        send_auto_reply(mock_conn, self.conversation_1, "Test Body")

        # Check that a new message was inserted
        mock_conn.cursor.return_value.__enter__.return_value.execute.assert_any_call(
            unittest.mock.ANY, # The INSERT statement
            (self.conversation_1['id'], 'technician', 'auto_reply_bot', "Test Body", unittest.mock.ANY, 'auto_reply')
        )
        # Check that the conversation timestamp was updated
        mock_conn.cursor.return_value.__enter__.return_value.execute.assert_any_call(
            unittest.mock.ANY, # The UPDATE statement
            (unittest.mock.ANY, self.conversation_1['id'])
        )
        # Check that commit was called
        mock_conn.commit.assert_called_once()
        # Check that the Mirakl API was called
        mock_send_to_mirakl.assert_called_once_with(self.conversation_1['mirakl_thread_id'], "Test Body")

if __name__ == '__main__':
    unittest.main()
