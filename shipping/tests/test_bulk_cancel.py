import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import pandas as pd

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from shipping import bulk_cancel_shipments

class TestBulkCancelShipments(unittest.TestCase):

    def setUp(self):
        """Set up common test data."""
        self.mock_creds = {'api_user': 'user', 'api_password': 'password'}
        self.mock_conn = MagicMock()

    @patch('pandas.read_csv')
    def test_read_from_csv_success(self, mock_read_csv):
        """Test successfully reading identifiers from a CSV file."""
        csv_data = pd.DataFrame({'identifier': ['ID1', 'ID2']})
        mock_read_csv.return_value = csv_data
        with patch('os.path.exists', return_value=True):
            identifiers = bulk_cancel_shipments.read_identifiers_from_file('fake.csv', 'identifier')
            self.assertEqual(identifiers, ['ID1', 'ID2'])

    @patch('pandas.read_excel')
    def test_read_from_xlsx_success(self, mock_read_excel):
        """Test successfully reading identifiers from an XLSX file."""
        xlsx_data = pd.DataFrame({'tracking_number': ['T1', 'T2']})
        mock_read_excel.return_value = xlsx_data
        with patch('os.path.exists', return_value=True):
            identifiers = bulk_cancel_shipments.read_identifiers_from_file('fake.xlsx', 'tracking_number')
            self.assertEqual(identifiers, ['T1', 'T2'])

    def test_read_file_not_found(self):
        """Test that the file reader handles a non-existent file."""
        with patch('os.path.exists', return_value=False):
            identifiers = bulk_cancel_shipments.read_identifiers_from_file('nonexistent.csv', 'identifier')
            self.assertIsNone(identifiers)

    @patch('pandas.read_csv')
    def test_read_column_not_found(self, mock_read_csv):
        """Test that the file reader handles a missing column."""
        csv_data = pd.DataFrame({'other_column': ['ID1', 'ID2']})
        mock_read_csv.return_value = csv_data
        with patch('os.path.exists', return_value=True):
            identifiers = bulk_cancel_shipments.read_identifiers_from_file('fake.csv', 'identifier')
            self.assertIsNone(identifiers)

    @patch('shipping.bulk_cancel_shipments.get_canada_post_credentials')
    @patch('shipping.bulk_cancel_shipments.get_db_connection')
    @patch('shipping.bulk_cancel_shipments.read_identifiers_from_file')
    @patch('shipping.bulk_cancel_shipments.get_shipments_details_by_order_id')
    @patch('shipping.bulk_cancel_shipments.process_single_shipment_cancellation')
    def test_main_workflow_order_id(self, mock_process_cancellation, mock_get_shipments, mock_read_ids, mock_get_conn, mock_get_creds):
        """Test the main bulk workflow using order_id."""
        # Setup mocks
        mock_get_creds.return_value = self.mock_creds
        mock_get_conn.return_value = self.mock_conn
        mock_read_ids.return_value = ['ORDER-1', 'ORDER-2']

        # Mock the database to return one shipment for the first order and two for the second
        shipment1 = {'shipment_id': 101, 'order_id': 'ORDER-1'}
        shipment2 = {'shipment_id': 102, 'order_id': 'ORDER-2'}
        shipment3 = {'shipment_id': 103, 'order_id': 'ORDER-2'}
        mock_get_shipments.side_effect = [
            [shipment1],
            [shipment2, shipment3]
        ]

        # Mock sys.argv to simulate command-line arguments
        with patch.object(sys, 'argv', ['script_name', 'path/to/file.csv', 'order_id']):
            bulk_cancel_shipments.main()

        # Verify that the cancellation processor was called three times
        self.assertEqual(mock_process_cancellation.call_count, 3)
        mock_process_cancellation.assert_any_call(self.mock_conn, self.mock_creds, shipment1)
        mock_process_cancellation.assert_any_call(self.mock_conn, self.mock_creds, shipment2)
        mock_process_cancellation.assert_any_call(self.mock_conn, self.mock_creds, shipment3)

if __name__ == '__main__':
    unittest.main()