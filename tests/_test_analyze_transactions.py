import unittest
import json
from accounting.analyze_transactions import analyze_and_remodel_transactions

class TestAnalyzeTransactions(unittest.TestCase):

    def test_analyze_and_remodel_transactions(self):
        # Load the sample transactions
        with open("accounting/sample_transactions.json", "r") as f:
            transactions = json.load(f)

        analyzed_data = analyze_and_remodel_transactions(transactions)

        # There should be one order in the sample data
        self.assertEqual(len(analyzed_data), 1)

        order_analysis = analyzed_data[0]
        self.assertEqual(order_analysis["order_id"], "261305911-A")

        # Check the analysis results
        analysis = order_analysis["analysis"]
        self.assertAlmostEqual(analysis["selling_price"], 324.99)
        self.assertAlmostEqual(analysis["taxes"], 42.25)
        self.assertAlmostEqual(analysis["commission"], 26.0)
        self.assertAlmostEqual(analysis["commission_tax"], 3.38)
        self.assertAlmostEqual(analysis["net_revenue"], 337.86)

    def test_analyze_and_remodel_empty_transactions(self):
        analyzed_data = analyze_and_remodel_transactions([])
        self.assertEqual(len(analyzed_data), 0)

if __name__ == '__main__':
    unittest.main()
