import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tracking import workflow

# --- Test Data ---
MOCK_SHIPMENT = {
    'shipment_id': 1,
    'order_id': 'BBY-TRACK-456',
    'tracking_pin': 'TRACK12345'
}

class TestTrackingWorkflowV2(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()

        self.patchers = {
            'get_db_connection': patch('tracking.workflow.get_db_connection', return_value=self.mock_conn),
            'get_best_buy_api_key': patch('tracking.workflow.get_best_buy_api_key', return_value='fake-bb-key'),
            'requests.put': patch('requests.put'),
            'log_api_call': patch('tracking.workflow.log_api_call'),
            'add_order_status_history': patch('tracking.workflow.add_order_status_history'),
            'log_process_failure': patch('tracking.workflow.log_process_failure'),
            'get_shipments_to_update': patch('tracking.workflow.get_shipments_to_update_on_bb')
        }
        self.mocks = {name: patcher.start() for name, patcher in self.patchers.items()}
        self.addCleanup(self.stop_all_patchers)

    def stop_all_patchers(self):
        for patcher in self.patchers.values():
            patcher.stop()

    def test_happy_path_tracking_update(self):
        """Tests the ideal scenario: tracking is updated and order is marked shipped."""
        # --- Arrange ---
        self.mocks['get_shipments_to_update'].return_value = [MOCK_SHIPMENT]
        # Mock both Best Buy API calls to succeed
        self.mocks['requests.put'].return_value = MagicMock(status_code=204, text="")

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that both API calls were made.
        self.assertEqual(self.mocks['requests.put'].call_count, 2)

        # 2. Check that the final status was updated to 'shipped'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'shipped', notes="Successfully marked as shipped on Best Buy."
        )
        # 3. Ensure no failure was logged.
        self.mocks['log_process_failure'].assert_not_called()

    def test_tracking_update_fails(self):
        """Tests that a failure in the first API call (update tracking) is handled."""
        # --- Arrange ---
        self.mocks['get_shipments_to_update'].return_value = [MOCK_SHIPMENT]
        # Mock the first API call to fail
        self.mocks['requests.put'].side_effect = requests.exceptions.RequestException(
            response=MagicMock(status_code=400, text="Bad tracking.")
        )

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that only ONE API call was made.
        self.mocks['requests.put'].assert_called_once()

        # 2. Check that a process failure was logged.
        self.mocks['log_process_failure'].assert_called_once()

        # 3. Check that the final status was updated to 'tracking_failed'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

    def test_mark_as_shipped_fails(self):
        """Tests that a failure in the second API call (mark as shipped) is handled."""
        # --- Arrange ---
        self.mocks['get_shipments_to_update'].return_value = [MOCK_SHIPMENT]
        # Mock the first call to succeed and the second to fail
        mock_success = MagicMock(status_code=204, text="")
        mock_fail = requests.exceptions.RequestException(response=MagicMock(status_code=500, text="Server error."))
        self.mocks['requests.put'].side_effect = [mock_success, mock_fail]

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that BOTH API calls were made.
        self.assertEqual(self.mocks['requests.put'].call_count, 2)

        # 2. Check that a process failure was logged.
        self.mocks['log_process_failure'].assert_called_once()

        # 3. Check that the final status was updated to 'tracking_failed'.
        self.mocks['add_order_status_history'].assert_called_with(
            self.mock_conn, MOCK_SHIPMENT['order_id'], 'tracking_failed', notes=unittest.mock.ANY
        )

if __name__ == '__main__':
    unittest.main()
