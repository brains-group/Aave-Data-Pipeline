import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from aave_data_pipeline.datasets import read_config
from aave_data_pipeline.shared_cache import collection_lock
from aave_data_pipeline.indexed_supplementary import inspect_sources, collect_supplementary
from aave_data_pipeline.collect import EVENTS, FIELDS


def schema_fixture():
    scalar=lambda name:{'kind':'SCALAR','name':name}
    obj=lambda name:{'kind':'OBJECT','name':name}
    f=lambda name,typ:{'name':name,'type':typ}
    args=[f(n,{'kind':'INPUT_OBJECT' if n=='where' else 'ENUM','name':t}) for n,t in [('where','Transfer_filter'),('orderBy','Transfer_orderBy'),('first','Int'),('block','Block_height'),('orderDirection','OrderDirection')]]
    return {'queryType':{'name':'Query'},'types':[
        {'name':'Query','fields':[dict(f('transfers',obj('Transfer')),args=args)]},
        {'name':'Transfer','fields':[f('id',scalar('Bytes')),f('timestamp',scalar('BigInt')),f('amount',scalar('BigInt')),f('sender',obj('Account'))]},
        {'name':'Account','fields':[f('id',scalar('Bytes')),f('presentDayBalance',scalar('BigInt'))]},
        {'name':'Transfer_filter','inputFields':[{'name':n} for n in ['and','or','timestamp','timestamp_gt','timestamp_gte','timestamp_lt','id_gt']]},
        {'name':'Transfer_orderBy','enumValues':[{'name':'timestamp'}]}]}


class SharedCollectionTests(unittest.TestCase):
    def test_output_owns_cache_and_market_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config.json'
            config.write_text(json.dumps({'CACHE_DIR':'models','TRANSACTIONS_PATH':'export','USERS_PATH':'export'}))
            c=read_config(config)
            self.assertEqual(Path(c['COLLECTION_CACHE_DIR']),root/'export/.cache')
            self.assertEqual(Path(c['CACHE_DIR']),root/'models')
            with collection_lock(c['COLLECTION_CACHE_DIR'],'polygon'):
                with self.assertRaisesRegex(RuntimeError,'Another collector'):
                    with collection_lock(c['COLLECTION_CACHE_DIR'],'polygon'):pass
                with collection_lock(c['COLLECTION_CACHE_DIR'],'avalanche'):pass
            with collection_lock(c['COLLECTION_CACHE_DIR'],'polygon'):pass

    def test_schema_does_not_join_mutable_account_values(self):
        available,coverage=inspect_sources(schema_fixture())
        self.assertEqual(set(available),{'transfers'})
        self.assertNotIn('presentDayBalance',available['transfers']['fields'])
        self.assertEqual(coverage['collateral_changes']['status'],'unavailable')
        schema=schema_fixture();schema['types'][-2]['inputFields']=[]
        self.assertEqual(inspect_sources(schema)[0],{})
        schema=schema_fixture();schema['types'][1]['fields'][1]['type']['name']='Int'
        self.assertEqual(inspect_sources(schema)[0],{})

    def test_supplementary_cache_resume_keeps_core_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config={'COLLECTION_CACHE_DIR':str(root/'.cache'),'TRANSACTIONS_PATH':str(root)}
            client=Mock(requests=2,max_requests=20)
            client.query.side_effect=[{'__schema':schema_fixture()},{'transfers':[{'id':'a','timestamp':10,'amount':'4','sender':{'id':'u'}}]}]
            meta={'deployment':'fixture','block':{'number':100,'timestamp':20}}
            collect_supplementary(client,config,'polygon',meta,0,20,30,1000)
            self.assertEqual(client.query.call_count,2)
            client.query.reset_mock();client.query.side_effect=AssertionError('Unexpected network request')
            collect_supplementary(client,config,'polygon',meta,0,20,30,1000)
            client.query.assert_not_called()
            self.assertFalse((root/'.cache/data_collection').exists())
            self.assertNotIn('transfers',EVENTS);self.assertNotIn('transfers',FIELDS)
            report=json.loads(next(root.glob('supplementary/**/coverage.json')).read_text())
            self.assertEqual(report['entities']['transfers']['rows'],1)
            self.assertEqual(report['requested_end_exclusive'],30)
            self.assertEqual(report['indexed_end_exclusive'],20)
