import os
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# The module to be tested
from tracking import workflow

# --- Test Data ---
MOCK_SHIPMENT = {
    'shipment_id': 1,
    'order_id': 'BBY-TRACK-456',
    'tracking_pin': 'TRACK12345'
}

class TestTrackingWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for each test."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor

        self.patchers = [
            patch('tracking.workflow.get_db_connection', return_value=self.mock_conn),
            patch('tracking.workflow.get_best_buy_api_key', return_value='fake-bb-key'),
            patch('requests.put')
        ]

        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_happy_path_tracking_update(self):
        """Tests the ideal scenario: tracking is updated and order is marked shipped."""
        # --- Arrange ---
        # DB returns one shipment to process
        self.mock_cursor.fetchall.return_value = [MOCK_SHIPMENT]

        # Mock both Best Buy API calls to succeed
        workflow.requests.put.return_value = MagicMock(status_code=204)

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that we fetched shipments to update
        self.mock_cursor.execute.assert_any_call(unittest.mock.ANY) # Simplified check

        # 2. Check that both API calls were made
        self.assertEqual(workflow.requests.put.call_count, 2)

        # 3. Check that both API calls were logged successfully
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('BestBuy', 'UpdateTracking', MOCK_SHIPMENT['order_id'], unittest.mock.ANY, unittest.mock.ANY, 204, True)
        )
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('BestBuy', 'MarkAsShipped', MOCK_SHIPMENT['order_id'], unittest.mock.ANY, unittest.mock.ANY, 204, True)
        )

        # 4. Check that the final statuses were updated in the DB
        self.mock_cursor.execute.assert_any_call(
            "UPDATE shipments SET status = 'tracking_updated' WHERE shipment_id = %s;", (MOCK_SHIPMENT['shipment_id'],)
        )
        self.mock_cursor.execute.assert_any_call(
            "UPDATE orders SET status = 'shipped' WHERE order_id = %s;", (MOCK_SHIPMENT['order_id'],)
        )

    def test_tracking_update_fails(self):
        """Tests that the workflow stops if the first API call (update tracking) fails."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_SHIPMENT]

        # Mock the first API call to fail. We use side_effect on the mock object itself.
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad tracking."
        workflow.requests.put.side_effect = requests.exceptions.RequestException(response=mock_response)

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that only ONE API call was made (the first one)
        workflow.requests.put.assert_called_once()

        # 2. Check that the failed API call was logged
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('BestBuy', 'UpdateTracking', MOCK_SHIPMENT['order_id'], unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY, False)
        )

        # 3. Check that the database statuses were NOT updated
        for call_args in self.mock_cursor.execute.call_args_list:
            sql = call_args[0][0]
            self.assertNotIn("UPDATE shipments", sql)
            self.assertNotIn("UPDATE orders", sql)

    def test_mark_as_shipped_fails(self):
        """Tests that a failure in the second API call is handled correctly."""
        # --- Arrange ---
        self.mock_cursor.fetchall.return_value = [MOCK_SHIPMENT]

        # Mock the first call to succeed and the second to fail
        mock_success_response = MagicMock(status_code=204, text="")
        mock_fail_response = MagicMock(status_code=500, text="Server error.")
        workflow.requests.put.side_effect = [
            mock_success_response,
            requests.exceptions.RequestException(response=mock_fail_response)
        ]

        # --- Act ---
        workflow.main()

        # --- Assert ---
        # 1. Check that BOTH API calls were made
        self.assertEqual(workflow.requests.put.call_count, 2)

        # 2. Check that both calls were logged (one success, one failure)
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('BestBuy', 'UpdateTracking', MOCK_SHIPMENT['order_id'], unittest.mock.ANY, unittest.mock.ANY, 204, True)
        )
        self.mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
            ('BestBuy', 'MarkAsShipped', MOCK_SHIPMENT['order_id'], unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY, False)
        )

        # 3. Check that the database statuses were NOT updated
        for call_args in self.mock_cursor.execute.call_args_list:
            sql = call_args[0][0]
            self.assertNotIn("UPDATE shipments", sql)
            self.assertNotIn("UPDATE orders", sql)

if __name__ == '__main__':
    unittest.main()
