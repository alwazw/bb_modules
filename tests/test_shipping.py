import unittest
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestShippingWorkflow(unittest.TestCase):

    def test_import(self):
        """
        Test that the shipping workflow module can be imported.
        """
        try:
            from shipping import workflow
        except ImportError as e:
            self.fail(f"Failed to import shipping.workflow: {e}")

if __name__ == '__main__':
    unittest.main()
