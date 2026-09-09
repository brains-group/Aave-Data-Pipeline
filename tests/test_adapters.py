import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from aave_data_pipeline.preprocessing import Preprocessor,classification_view
from aave_data_pipeline.supplementary import ingest

class AdapterTests(unittest.TestCase):
    def test_preprocess_train_fit_identity_and_horizon(self):
        df=pd.DataFrame(dict(id=['a','b','c'],outcome_id=['secret']*3,split=['train']*3,
            observation_id=['x','y','z'],amount=[1.,2.,3.],reserve=['USD','USD','ETH'],timeDiff=[86400,172800,86400],status=[1,0,0]))
        p=Preprocessor().fit(df)
        future=df.iloc[:1].copy();future.amount=1000;future.reserve='new'
        x,y,ids=p.transform(future)
        self.assertAlmostEqual(x.amount.iloc[0],998)
        self.assertNotIn('outcome_id',x)
        self.assertEqual(ids.id.iloc[0],'a')
        self.assertEqual(list(classification_view(df,1).id),['a','b'])

    def test_supplementary_isolation_resume_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'events.jsonl'
            row=dict(id='x',timestamp=10,blockNumber=1,transactionHash='0x1',logIndex=2,enabled=False)
            file.write_text(json.dumps(row)+'\n')
            m=dict(market='polygon',chain_id=137,source='collateral_usage',source_identity='fixture-v1',coverage_start=0,coverage_end=20,coverage_complete=False,deployment_address='fixture')
            target=ingest(file,root,m);self.assertEqual(target,ingest(file,root,m))
            self.assertFalse((root/'data_collection').exists())
            row['enabled']=True;file.write_text(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'changed'):ingest(file,root,m)
            m['market']='avalanche'
            with self.assertRaisesRegex(ValueError,'chain ID'):ingest(file,root,m)
