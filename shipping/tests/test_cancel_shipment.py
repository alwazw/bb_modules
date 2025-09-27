import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from shipping.canada_post import cp_cancel_shipment

class TestCancelShipment(unittest.TestCase):

    def setUp(self):
        """Set up test data and mock credentials."""
        self.cp_creds = {
            'api_user': 'testuser',
            'api_password': 'testpassword',
            'customer_number': '123456',
        }
        self.shipment_id = 101
        self.order_id = 'ORDER-101'
        self.shipment_details = {
            'shipment_id': self.shipment_id,
            'order_id': self.order_id,
            'cp_api_label_url': 'https://soa-gw.canadapost.ca/rs/123456/123456/shipment/abcdef123456/label',
            'status': 'label_created'
        }
        # Mock database connection
        self.mock_conn = MagicMock()

    @patch('requests.delete')
    def test_void_shipment_success(self, mock_delete):
        """Test successful voiding of a shipment."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        with patch('shipping.canada_post.cp_cancel_shipment.update_shipment_status_in_db') as mock_update_status, \
             patch('shipping.canada_post.cp_cancel_shipment.add_order_status_history') as mock_add_history, \
             patch('shipping.canada_post.cp_cancel_shipment.log_api_call') as mock_log_api:

            result = cp_cancel_shipment.void_shipment(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)

            self.assertEqual(result, "voided")
            mock_delete.assert_called_once()
            mock_update_status.assert_called_once_with(self.mock_conn, self.shipment_id, 'cancelled', 'Shipment successfully voided.')
            mock_add_history.assert_called_once_with(self.mock_conn, self.order_id, 'shipment_cancelled', notes='Shipment voided with Canada Post.')
            mock_log_api.assert_called_once()

    @patch('requests.delete')
    def test_void_shipment_already_transmitted(self, mock_delete):
        """Test voiding a shipment that has already been transmitted (Error 8064)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '<messages><message><code>8064</code></message></messages>'
        mock_delete.return_value = mock_response

        with patch('shipping.canada_post.cp_cancel_shipment.log_api_call'):
            result = cp_cancel_shipment.void_shipment(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)
            self.assertEqual(result, "transmitted")

    @patch('requests.post')
    def test_request_shipment_refund_success(self, mock_post):
        """Test successful refund request for a transmitted shipment."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<shipment-refund-request-info xmlns="http://www.canadapost.ca/ws/shipment-v8"><service-ticket-id>XYZ-789</service-ticket-id></shipment-refund-request-info>'
        mock_post.return_value = mock_response

        with patch('shipping.canada_post.cp_cancel_shipment.update_shipment_status_in_db') as mock_update_status, \
             patch('shipping.canada_post.cp_cancel_shipment.add_order_status_history') as mock_add_history, \
             patch('shipping.canada_post.cp_cancel_shipment.log_api_call'):

            result = cp_cancel_shipment.request_shipment_refund(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)

            self.assertEqual(result, "refund_requested")
            mock_update_status.assert_called_once_with(self.mock_conn, self.shipment_id, 'refund_requested', 'Refund requested. Service Ticket ID: XYZ-789')

    @patch('shipping.canada_post.cp_cancel_shipment.request_shipment_refund')
    @patch('shipping.canada_post.cp_cancel_shipment.void_shipment')
    def test_process_cancellation_void_path(self, mock_void, mock_request_refund):
        """Test the cancellation processor for the successful void path."""
        mock_void.return_value = "voided"

        cp_cancel_shipment.process_single_shipment_cancellation(self.mock_conn, self.cp_creds, self.shipment_details)

        mock_void.assert_called_once_with(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)
        mock_request_refund.assert_not_called()

    @patch('shipping.canada_post.cp_cancel_shipment.request_shipment_refund')
    @patch('shipping.canada_post.cp_cancel_shipment.void_shipment')
    def test_process_cancellation_refund_path(self, mock_void, mock_request_refund):
        """Test the cancellation processor for the refund path."""
        mock_void.return_value = "transmitted"
        mock_request_refund.return_value = "refund_requested"

        cp_cancel_shipment.process_single_shipment_cancellation(self.mock_conn, self.cp_creds, self.shipment_details)

        mock_void.assert_called_once_with(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)
        mock_request_refund.assert_called_once_with(self.mock_conn, self.cp_creds, self.shipment_id, self.shipment_details)

    @patch('shipping.canada_post.cp_cancel_shipment.void_shipment')
    def test_process_cancellation_skips_already_cancelled(self, mock_void):
        """Test that the processor skips shipments already in a final state."""
        details_cancelled = self.shipment_details.copy()
        details_cancelled['status'] = 'cancelled'
        cp_cancel_shipment.process_single_shipment_cancellation(self.mock_conn, self.cp_creds, details_cancelled)
        mock_void.assert_not_called()

        details_refunded = self.shipment_details.copy()
        details_refunded['status'] = 'refund_requested'
        cp_cancel_shipment.process_single_shipment_cancellation(self.mock_conn, self.cp_creds, details_refunded)
        mock_void.assert_not_called()

if __name__ == '__main__':
    unittest.main()