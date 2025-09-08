import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from order_management import workflow

# --- Test Data ---
# MOCK_ORDER no longer has a 'status' field itself. Status is now managed in a separate table.
MOCK_ORDER = {
    'order_id': 'BBY-12345',
    'raw_order_data': {
        'order_id': 'BBY-12345',
        'order_lines': [{'order_line_id': 'L-1', 'offer_sku': 'SKU-A', 'quantity': 1}]
    }
}

class TestOrderAcceptanceWorkflowV2(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()
        self.mock_api_key = "fake-api-key"

        # Patch all external dependencies for the workflow
        self.patchers = {
            'get_db_connection': patch('order_management.workflow.get_db_connection', return_value=self.mock_conn),
            'get_best_buy_api_key': patch('order_management.workflow.get_best_buy_api_key', return_value=self.mock_api_key),
            'time.sleep': patch('time.sleep'),
            'requests.put': patch('requests.put'),
            'requests.get': patch('requests.get'),
            'log_api_call': patch('order_management.workflow.log_api_call'),
            'add_order_status_history': patch('order_management.workflow.add_order_status_history'),
            'log_process_failure': patch('order_management.workflow.log_process_failure'),
            'get_orders_to_accept': patch('order_management.workflow.get_orders_to_accept_from_db')
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_order_accepted(self):
        """Tests the ideal scenario: order is accepted and validated on the first attempt."""
        # --- Arrange ---
        self.mocks['get_orders_to_accept'].return_value = [MOCK_ORDER]
        # Mock successful API acceptance call
        self.mocks['requests.put'].return_value = MagicMock(status_code=204, json=lambda: {})
        # Mock successful validation status
        self.mocks['requests.get'].return_value = MagicMock(status_code=200, json=lambda: {'order_state': 'WAITING_DEBIT_PAYMENT'})

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Ensure we looked for orders
        self.mocks['get_orders_to_accept'].assert_called_once()
        # Ensure we tried to accept via API
        self.mocks['requests.put'].assert_called_once()
        # Ensure we tried to validate via API
        self.mocks['requests.get'].assert_called_once()

        # Crucially, assert that the final status was logged to the history table
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'accepted', notes="Validated as 'WAITING_DEBIT_PAYMENT'."
        )
        # Ensure no failure was logged
        self.mocks['log_process_failure'].assert_not_called()

    def test_validation_fails_then_succeeds(self):
        """Tests the scenario where validation requires one retry before succeeding."""
        # --- Arrange ---
        self.mocks['get_orders_to_accept'].return_value = [MOCK_ORDER]
        self.mocks['requests.put'].return_value = MagicMock(status_code=204, json=lambda: {})

        # Mock validation API to fail once, then succeed
        self.mocks['requests.get'].side_effect = [
            MagicMock(status_code=200, json=lambda: {'order_state': 'WAITING_ACCEPTANCE'}), # 1st call
            MagicMock(status_code=200, json=lambda: {'order_state': 'SHIPPING'})           # 2nd call
        ]

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Ensure validation was attempted twice
        self.assertEqual(self.mocks['requests.get'].call_count, 2)
        # Ensure the final status was 'accepted'
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'accepted', notes="Validated as 'SHIPPING'."
        )
        self.mocks['log_process_failure'].assert_not_called()

    def test_validation_fails_completely(self):
        """Tests the scenario where an order consistently fails validation and is logged as a failure."""
        # --- Arrange ---
        self.mocks['get_orders_to_accept'].return_value = [MOCK_ORDER]
        self.mocks['requests.put'].return_value = MagicMock(status_code=204, json=lambda: {})

        # Mock validation API to always return a non-final status
        self.mocks['requests.get'].return_value = MagicMock(status_code=200, json=lambda: {'order_state': 'PENDING'})

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Ensure validation was attempted the maximum number of times
        self.assertEqual(self.mocks['requests.get'].call_count, workflow.MAX_VALIDATION_ATTEMPTS)

        # Assert that a process failure was logged
        self.mocks['log_process_failure'].assert_called_once()

        # Assert that the final status was 'acceptance_failed'
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'acceptance_failed', notes=unittest.mock.ANY
        )

    def test_initial_acceptance_api_fails(self):
        """Tests that a failure from the initial 'accept' API call is handled correctly."""
        # --- Arrange ---
        self.mocks['get_orders_to_accept'].return_value = [MOCK_ORDER]
        # Mock a failed API acceptance call
        self.mocks['requests.put'].side_effect = requests.exceptions.RequestException(
            response=MagicMock(status_code=400, json=lambda: {'error': 'bad request'})
        )

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # Ensure the validation API was NEVER called
        self.mocks['requests.get'].assert_not_called()

        # Assert that a process failure was logged
        self.mocks['log_process_failure'].assert_called_once()

        # Assert that the final status was 'acceptance_failed'
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_ORDER['order_id'], 'acceptance_failed', notes=unittest.mock.ANY
        )

if __name__ == '__main__':
    unittest.main()
