import unittest
import json
from unittest.mock import patch

# Add project root to path to allow importing 'app'
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fulfillment_service.src.app import app
from fulfillment_service.src import app as main_app

class TestApi(unittest.TestCase):

    def setUp(self):
        """Set up a test client and clear sessions for each test."""
        self.app = app.test_client()
        self.app.testing = True
        main_app.fulfillment_sessions.clear()

    # Helper method to start a session for testing other endpoints
    def _start_session(self, order_id="ORDER-1", required_components=None):
        if required_components is None:
            required_components = {"BAR-123": "RAM", "BAR-456": "SSD"}
        main_app.fulfillment_sessions[order_id] = {
            "order": {"order_id": order_id},
            "required_components": required_components,
            "scanned_components": set()
        }

    @patch('fulfillment_service.src.logic.get_work_order_details')
    def test_start_fulfillment_success(self, mock_get_work_order):
        """Test successful start of a fulfillment process."""
        mock_get_work_order.return_value = ({"order": {"order_id": "ORDER-1"}, "required_components": {"BAR-123": "RAM"}}, None)
        response = self.app.post('/api/fulfillment/start', data=json.dumps({'order_id': 'ORDER-1'}), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['order_id'], 'ORDER-1')

    def test_start_fulfillment_no_order_id(self):
        """Test start fulfillment with no order_id provided."""
        response = self.app.post('/api/fulfillment/start', data=json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    @patch('fulfillment_service.src.logic.get_work_order_details')
    def test_start_fulfillment_order_not_found(self, mock_get_work_order):
        """Test start fulfillment for an order that doesn't exist."""
        mock_get_work_order.return_value = (None, "Order not found.")
        response = self.app.post('/api/fulfillment/start', data=json.dumps({'order_id': 'UNKNOWN-ORDER'}), content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_scan_component_success(self):
        """Test a successful component scan."""
        self._start_session()
        response = self.app.post('/api/fulfillment/scan', data=json.dumps({'order_id': 'ORDER-1', 'barcode': 'BAR-123'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['validation_status'], 'success')
        self.assertIn('RAM', main_app.fulfillment_sessions['ORDER-1']['scanned_components'])

    def test_scan_component_invalid(self):
        """Test scanning a component not required for the order."""
        self._start_session()
        response = self.app.post('/api/fulfillment/scan', data=json.dumps({'order_id': 'ORDER-1', 'barcode': 'INVALID-BAR'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['validation_status'], 'fail')

    def test_scan_component_duplicate(self):
        """Test scanning a component that has already been scanned."""
        self._start_session()
        # First scan
        self.app.post('/api/fulfillment/scan', data=json.dumps({'order_id': 'ORDER-1', 'barcode': 'BAR-123'}), content_type='application/json')
        # Second scan
        response = self.app.post('/api/fulfillment/scan', data=json.dumps({'order_id': 'ORDER-1', 'barcode': 'BAR-123'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['validation_status'], 'duplicate')

    @patch('fulfillment_service.src.logic.generate_shipping_label')
    def test_finalize_success(self, mock_generate_label):
        """Test successful finalization of an order."""
        self._start_session()
        main_app.fulfillment_sessions['ORDER-1']['scanned_components'] = {'RAM', 'SSD'}
        mock_generate_label.return_value = ({"tracking_pin": "TRACK-123", "pdf_path": "/path/to/label.pdf"}, None)

        response = self.app.post('/api/fulfillment/finalize', data=json.dumps({'order_id': 'ORDER-1'}), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['tracking_number'], 'TRACK-123')
        self.assertNotIn('ORDER-1', main_app.fulfillment_sessions) # Session should be cleaned up

    def test_finalize_not_all_components_scanned(self):
        """Test finalization when not all components have been scanned."""
        self._start_session()
        main_app.fulfillment_sessions['ORDER-1']['scanned_components'] = {'RAM'} # Missing SSD
        response = self.app.post('/api/fulfillment/finalize', data=json.dumps({'order_id': 'ORDER-1'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Not all required components', data['error'])
        self.assertIn('SSD', data['missing_components'])

    @patch('fulfillment_service.src.logic.generate_shipping_label')
    def test_finalize_label_generation_fails(self, mock_generate_label):
        """Test finalization when label generation fails."""
        self._start_session()
        main_app.fulfillment_sessions['ORDER-1']['scanned_components'] = {'RAM', 'SSD'}
        mock_generate_label.return_value = (None, "API Error")

        response = self.app.post('/api/fulfillment/finalize', data=json.dumps({'order_id': 'ORDER-1'}), content_type='application/json')

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('Label generation failed', data['error'])


if __name__ == '__main__':
    unittest.main()
