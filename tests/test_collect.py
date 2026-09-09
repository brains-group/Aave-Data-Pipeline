"""Offline correctness checks: pagination, resume, coverage, units and isolation."""
import csv
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aave_data_pipeline.collect import Cache, Client, transaction, date_value, main, collect_range
from aave_data_pipeline.datasets import dataset_path


class Fake:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.queries = []

    def query(self, query):
        self.queries.append(query)
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return {"borrows": page}


class CollectionTests(unittest.TestCase):
    def test_resume_and_equal_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.sqlite3'
            cache = Cache(path)
            first = Fake([[{'id': 'a', 'timestamp': 10}, {'id': 'b', 'timestamp': 10}], RuntimeError('network')])
            with self.assertRaises(RuntimeError):
                cache.collect(first, 'borrows', 0, 20, 100, 2)
            cache.db.close()
            cache = Cache(path)
            second = Fake([[{'id': 'c', 'timestamp': 10}]])
            cache.collect(second, 'borrows', 0, 20, 200, 2)
            self.assertIn('id_gt: "b"', second.queries[0])
            self.assertIn('number: 100', second.queries[0])
            self.assertEqual(len(list(cache.rows('borrows'))), 3)
            self.assertEqual(list(cache.missing('borrows', 0, 30)), [(20, 30)])
            self.assertEqual(list(cache.missing('borrows', 3, 15)), [])
            cache.db.close()

    def test_empty_intervals_and_expansion_both_directions(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            cache.collect(Fake([[]]), 'borrows', 10, 20, 100, 2)
            self.assertEqual(list(cache.missing('borrows', 0, 30)), [(0, 10), (20, 30)])
            cache.db.close()

    def test_amounts_and_profit(self):
        row = dict(id='x', timestamp=10, amount='1234567', amountUSD='1.25',
                   asset=dict(decimals=6, symbol='USDC'), market=dict(id='pool'),
                   liquidatee=dict(id='a'), liquidator=dict(id='b'), profitUSD='0.12')
        result = transaction(row, 'liquidates', 'polygon')
        self.assertEqual(result['amount'], '1.234567')
        self.assertEqual(result['profitUSD'], '0.12')

    def test_paths_and_dates(self):
        config = {'TRANSACTIONS_PATH': '/tmp/data'}
        self.assertNotEqual(dataset_path(config, 'transactions', 'polygon'), dataset_path(config, 'transactions', 'avalanche'))
        with self.assertRaises(ValueError):
            dataset_path(config, 'transactions', '../escape')
        self.assertEqual(date_value('2024-01-01', True) - date_value('2024-01-01'), 86400)

    def test_full_export_and_cached_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({'CACHE_DIR': 'cache', 'TRANSACTIONS_PATH': 'tx', 'USERS_PATH': 'users'}))
            queries = []
            def query(client, text):
                queries.append(text)
                if '_meta' in text:
                    return {'_meta': {'deployment': 'test', 'hasIndexingErrors': False,
                                      'block': {'number': 100, 'timestamp': 200}}}
                entity = re.search(r'{ (\w+)\(', text).group(1)
                if entity == 'borrows':
                    return {entity: [dict(id='0x01', timestamp=100, amount='1000000', amountUSD='1',
                                         asset=dict(id='token', symbol='USDC', decimals=6),
                                         market=dict(id='pool'), account=dict(id='0x02'))]}
                if entity == 'accounts':
                    return {entity: [dict(id='0x02', borrowCount=1)]}
                return {entity: []}
            argv = ['collect', '--config', str(config), '--endpoint', 'https://example.org', '--free-access-confirmed', '--max-requests', '20']
            with patch('sys.argv', argv), patch.object(Client, 'query', query):
                main()
            tx = root / 'tx/transactions_aave_v3_polygon.csv'
            with tx.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['amount'], '1')
            queries.clear()
            with patch('sys.argv', argv), patch.object(Client, 'query', query):
                main()
            self.assertEqual(len(queries), 1)  # Only metadata; progress makes no API calls.
            self.assertTrue((root / 'users/users_aave_v3_polygon.csv').exists())

    def test_unavailable_snapshot_keeps_cursor_and_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            first = Fake([[{'id': 'a', 'timestamp': 10}], RuntimeError('interrupted')])
            with self.assertRaises(RuntimeError):
                cache.collect(first, 'borrows', 0, 20, 100, 1)
            client = Fake([])
            responses = iter([
                RuntimeError('missing block: 100'),
                {'_meta': {'hasIndexingErrors': False, 'block': {'number': 200, 'timestamp': 30}}},
                {'borrows': [{'id': 'b', 'timestamp': 10}]},
            ])
            def query(text):
                client.queries.append(text)
                result = next(responses)
                if isinstance(result, Exception):
                    raise result
                return result
            client.query = query
            cache.collect(client, 'borrows', 0, 20, 100, 2)
            self.assertIn('number: 200', client.queries[-1])
            self.assertIn('id_gt: "a"', client.queries[-1])
            self.assertIn('timestamp_lt: "20"', client.queries[-1])
            self.assertEqual(len(list(cache.rows('borrows'))), 2)
            self.assertEqual(list(cache.missing('borrows', 0, 20)), [])
            cache.db.close()

    def test_snapshot_can_expire_again_after_page_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            responses = []
            # More total recoveries than the consecutive-failure limit is valid
            # when every recovery allows another page to be saved.
            for i in range(5):
                responses.extend([
                    RuntimeError('missing block: old'),
                    {'_meta': {'hasIndexingErrors': False,
                               'block': {'number': 200 + i, 'timestamp': 30}}},
                    {'borrows': [{'id': str(i), 'timestamp': 10}]},
                ])
            responses.append({'borrows': []})
            with patch.object(Client, 'query', side_effect=responses) as query:
                cache.collect(Client('https://example.org'), 'borrows', 0, 20, 100, 1)
            self.assertEqual(len(list(cache.rows('borrows'))), 5)
            self.assertEqual(list(cache.missing('borrows', 0, 20)), [])
            last_query = query.call_args.args[0]
            self.assertIn('id_gt: "4"', last_query)
            self.assertIn('number: 204', last_query)
            self.assertIn('timestamp_lt: "20"', last_query)
            cache.db.close()

    def test_snapshot_recovery_stops_without_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            responses = []
            for i in range(3):
                responses.extend([
                    RuntimeError('missing block: old'),
                    {'_meta': {'hasIndexingErrors': False,
                               'block': {'number': 200 + i, 'timestamp': 30}}},
                ])
            responses.append(RuntimeError('missing block: old'))
            with patch.object(Client, 'query', side_effect=responses) as query:
                with self.assertRaisesRegex(RuntimeError, '3 times without page progress'):
                    cache.collect(Client('https://example.org'), 'borrows', 0, 20, 100, 1)
            self.assertEqual(query.call_count, 7)
            self.assertEqual(list(cache.rows('borrows')), [])
            self.assertEqual(list(cache.missing('borrows', 0, 20)), [(0, 20)])
            cache.db.close()

    def test_progress_keeps_full_pages_across_days(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            rows = [{'id': f'{i:04}', 'timestamp': 1 + i * 400} for i in range(1000)]
            client = Fake([rows, []])
            with patch('aave_data_pipeline.collect.tqdm') as bars:
                collect_range(cache, client, 'borrows', 0, 500000, 100, 1000)
                bar = bars.return_value.__enter__.return_value
                self.assertAlmostEqual(sum(call.args[0] for call in bar.update.call_args_list), 499999 / 86400)
            self.assertEqual(len(client.queries), 2)
            self.assertTrue(all('first: 1000' in q for q in client.queries))
            self.assertTrue(all('timestamp_lt: "500000"' in q for q in client.queries))
            self.assertIn('id_gt: "0999"', client.queries[-1])
            with patch('aave_data_pipeline.collect.tqdm'):
                collect_range(cache, client, 'borrows', 0, 500000, 100, 1000)
            self.assertEqual(len(client.queries), 2)
            cache.db.close()

    def test_progress_preserves_old_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            with cache.db:
                cache.db.execute("INSERT INTO jobs(entity,start,end,block,cursor) VALUES('borrows',0,200000,100,'b')")
            client = Fake([[{'id': 'c', 'timestamp': 100000}]])
            with patch('aave_data_pipeline.collect.tqdm'):
                collect_range(cache, client, 'borrows', 0, 200000, 100, 1000)
            self.assertEqual(len(client.queries), 1)
            self.assertIn('id_gt: "b"', client.queries[0])
            cache.db.close()

    def test_chronological_cursor_allows_smaller_ids_at_later_times(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            client = Fake([
                [{'id': 'y', 'timestamp': 10}, {'id': 'z', 'timestamp': 10}],
                [{'id': 'a', 'timestamp': 11}, {'id': 'b', 'timestamp': 11}],
                [{'id': 'c', 'timestamp': 11}],
            ])
            cache.collect(client, 'borrows', 0, 20, 100, 2)
            self.assertEqual(len(list(cache.rows('borrows'))), 5)
            self.assertIn('orderBy: timestamp', client.queries[1])
            self.assertIn('timestamp_gt: "10"', client.queries[1])
            self.assertIn('timestamp: "10", id_gt: "z"', client.queries[1])
            self.assertIn('timestamp: "11", id_gt: "b"', client.queries[2])
            cache.db.close()

    def test_more_than_1000_events_at_one_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Cache(Path(directory) / 'db')
            rows = [{'id': f'{i:05}', 'timestamp': 10} for i in range(2501)]
            client = Fake([rows[:1000], rows[1000:2000], rows[2000:]])
            cache.collect(client, 'borrows', 0, 20, 100, 1000)
            self.assertEqual(len(list(cache.rows('borrows'))), 2501)
            self.assertEqual(len(client.queries), 3)
            self.assertIn('timestamp: "10", id_gt: "01999"', client.queries[-1])
            cache.db.close()

    def test_error_redacts_key(self):
        client = Client('https://gateway.thegraph.com/api/secret-key/subgraphs/id/example')
        detail = client.error_detail('failure secret-key ' + client.endpoint)
        self.assertNotIn('secret-key', detail)

    def test_retry_exhaustion(self):
        with patch('aave_data_pipeline.collect.urlopen', side_effect=TimeoutError), patch('aave_data_pipeline.collect.time.sleep') as sleep:
            with self.assertRaises(RuntimeError):
                Client('https://example.org', retries=3, max_requests=3).query('{}')
            self.assertEqual(sleep.call_count, 2)


if __name__ == '__main__':
    unittest.main()
