import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# The module to be tested
from order_management import workflow

# --- Test Data ---
MOCK_ORDER = {
    'order_id': 'BBY-12345',
    'status': 'pending_acceptance',
    'raw_order_data': {
        'order_id': 'BBY-12345',
        'order_lines': [{'order_line_id': 'L-1', 'offer_sku': 'SKU-A', 'quantity': 1}]
    }
}

class TestOrderWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        # Mock the database connection and cursor
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        # Mock the API key utility
        self.mock_api_key = "fake-api-key"

        # Patch external dependencies
        self.patchers = [
            patch('order_management.workflow.get_db_connection', return_value=self.mock_conn),
            patch('order_management.workflow.get_best_buy_api_key', return_value=self.mock_api_key),
            patch('order_management.workflow.time.sleep'), # To avoid actual waiting
            patch('requests.put'),
            patch('requests.get'),
            patch('builtins.print') # To capture print statements
        ]

        # Start patchers
        self.mock_get_db_connection = self.patchers[0].start()
        self.mock_get_api_key = self.patchers[1].start()
        self.mock_sleep = self.patchers[2].start()
        self.mock_requests_put = self.patchers[3].start()
        self.mock_requests_get = self.patchers[4].start()
        self.mock_print = self.patchers[5].start()

    def tearDown(self):
        """Stop all patchers."""
        for p in self.patchers:
            p.stop()

    def test_happy_path_order_accepted_first_try(self):
        """Tests the ideal scenario: order is accepted and validated on the first attempt."""
        # --- Arrange ---
        # DB returns one order to process
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]

        # Mock a successful API acceptance call
        self.mock_requests_put.return_value.status_code = 204
        self.mock_requests_put.return_value.content = b''

        # Mock a successful validation status
        self.mock_requests_get.return_value.json.return_value = {'order_state': 'WAITING_DEBIT_PAYMENT'}

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Check that the DB was queried for orders
        self.mock_cursor.execute.assert_any_call("SELECT * FROM orders WHERE status = 'pending_acceptance';")

        # Check that the acceptance API was called
        self.mock_requests_put.assert_called_once()

        # Check that the validation API was called
        self.mock_requests_get.assert_called_once()

        # Check that the order status was updated to 'accepted' in the DB
        self.mock_cursor.execute.assert_any_call("UPDATE orders SET status = %s WHERE order_id = %s;", ('accepted', MOCK_ORDER['order_id']))

        # Check that one successful attempt was logged
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            (MOCK_ORDER['order_id'], 1, 'success', unittest.mock.ANY)
        )

        # Check that no debug log was created
        self.assertNotIn(
            call("INSERT INTO order_acceptance_debug_logs (order_id, details, raw_request_payload) VALUES (%s, %s, %s);", unittest.mock.ANY),
            self.mock_cursor.execute.call_args_list
        )

    def test_retry_path_validates_on_second_try(self):
        """Tests the scenario where validation fails once, then succeeds."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]
        self.mock_requests_put.return_value.status_code = 204
        self.mock_requests_put.return_value.content = b''

        # Mock validation API to fail once, then succeed
        self.mock_requests_get.side_effect = [
            MagicMock(json=MagicMock(return_value={'order_state': 'WAITING_ACCEPTANCE'})), # 1st validation call
            MagicMock(json=MagicMock(return_value={'order_state': 'SHIPPING'})) # 2nd validation call
        ]

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Acceptance API should be called only ONCE
        self.mock_requests_put.assert_called_once()

        # Validation API should be called twice
        self.assertEqual(self.mock_requests_get.call_count, 2)

        # Check status is updated to 'accepted'
        self.mock_cursor.execute.assert_any_call("UPDATE orders SET status = %s WHERE order_id = %s;", ('accepted', MOCK_ORDER['order_id']))

        # Check that ONLY ONE acceptance attempt was logged
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            (MOCK_ORDER['order_id'], 1, 'success', unittest.mock.ANY)
        )
        # Ensure a second attempt was NOT logged
        with self.assertRaises(AssertionError):
            self.mock_cursor.execute.assert_any_call(
                unittest.mock.ANY,
                (MOCK_ORDER['order_id'], 2, unittest.mock.ANY, unittest.mock.ANY)
            )

    def test_failure_path_exceeds_max_retries(self):
        """Tests the scenario where an order consistently fails validation."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]
        self.mock_requests_put.return_value.status_code = 204
        self.mock_requests_put.return_value.content = b''

        # Mock validation API to always fail
        self.mock_requests_get.return_value.json.return_value = {'order_state': 'WAITING_ACCEPTANCE'}

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Check it tried to accept ONCE
        self.mock_requests_put.assert_called_once()
        # Check it tried to validate 3 times
        self.assertEqual(self.mock_requests_get.call_count, workflow.MAX_ACCEPTANCE_ATTEMPTS)

        # Check that a debug log was created on the 3rd failure
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY, # Using ANY for the SQL string for now to debug
            (MOCK_ORDER['order_id'], unittest.mock.ANY, unittest.mock.ANY)
        )

        # Check that the final status is 'acceptance_failed'
        self.mock_cursor.execute.assert_any_call("UPDATE orders SET status = %s WHERE order_id = %s;", ('acceptance_failed', MOCK_ORDER['order_id']))

        # Check that the notification placeholder was printed
        self.mock_print.assert_any_call("!!! NOTIFICATION: Manual intervention required !!!")

    def test_cancelled_order_path(self):
        """Tests that a cancelled order is handled correctly."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_ORDER]
        self.mock_requests_put.return_value.status_code = 204
        self.mock_requests_get.return_value.json.return_value = {'order_state': 'CANCELLED'}

        # --- Act ---
        workflow.main()

        # --- Assert ---
        self.mock_requests_get.assert_called_once()
        self.mock_cursor.execute.assert_any_call("UPDATE orders SET status = %s WHERE order_id = %s;", ('cancelled', MOCK_ORDER['order_id']))

if __name__ == '__main__':
    unittest.main()
