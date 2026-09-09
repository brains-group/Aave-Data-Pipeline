import unittest
from unittest.mock import patch
from aave_data_pipeline.collect import Client

class BudgetTests(unittest.TestCase):
    def test_zero_budget_never_opens_network(self):
        with patch('aave_data_pipeline.collect.urlopen') as request:
            with self.assertRaisesRegex(RuntimeError,'budget exhausted'):
                Client('https://example.org').query('{}')
            request.assert_not_called()

    def test_retry_consumes_budget(self):
        with patch('aave_data_pipeline.collect.urlopen',side_effect=TimeoutError) as request, patch('aave_data_pipeline.collect.time.sleep'):
            client=Client('https://example.org',retries=8,max_requests=2)
            with self.assertRaisesRegex(RuntimeError,'budget exhausted'):
                client.query('{}')
            self.assertEqual(request.call_count,2)
            self.assertEqual(client.requests,2)
