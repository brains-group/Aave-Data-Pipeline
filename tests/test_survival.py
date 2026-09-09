import unittest
import pandas as pd
from aave_data_pipeline.features import engineer, core_view
from aave_data_pipeline.survival import labels, join_features

class SurvivalTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame([
            dict(id='d1',type='deposit',timestamp=10,user='u',reserve='ETH',amount=2,amountUSD=4),
            dict(id='d2',type='deposit',timestamp=20,user='u',reserve='ETH',amount=3,amountUSD=6),
            dict(id='b1',type='borrow',timestamp=20,user='u',reserve='USD',amount=1,amountUSD=1),
            dict(id='l1',type='liquidation',timestamp=30,user=None,liquidatee='u',liquidator='other',reserve='USD',amount=1,amountUSD=1),
            dict(id='d3',type='deposit',timestamp=60,user='u',reserve='ETH',amount=4,amountUSD=8),
            dict(id='x',type='flashloan',timestamp=15,user='u',reserve='ETH',amount=900,amountUSD=1800),
        ])

    def test_core_identity_no_supplementary_or_account_snapshot_features(self):
        df=self.fixture(); df['borrowCount']=100000
        f=engineer(df,['USD'])
        self.assertNotIn('x',set(f.id)); self.assertNotIn('borrowCount',f)
        self.assertEqual(f.set_index('id').loc['l1','user'],'u')
        self.assertEqual(f.set_index('id').loc['d2','userDepositSum'],5)

    def test_prefix_invariance_and_features_align(self):
        df=self.fixture()
        f=engineer(df,['USD']).set_index('id')
        prefix=engineer(df[df.timestamp<=30],['USD']).set_index('id')
        pd.testing.assert_frame_equal(f.loc[prefix.index,prefix.columns],prefix)
        y=labels(df,'deposit','liquidation',40,80,0)
        joined=join_features(f.reset_index(),y)
        self.assertEqual(list(joined.id),list(y.id))
        self.assertEqual(list(y.status),[1,1,0])
        self.assertEqual(list(y.timeDiff),[20,10,20])

    def test_self_transition_parity_and_correction(self):
        df=self.fixture()
        parity=labels(df,'deposit','deposit',40,80,0,'r-parity')
        corrected=labels(df,'deposit','deposit',40,80,0,'corrected')
        self.assertEqual(parity.iloc[0].timeDiff,9)
        self.assertEqual(corrected.iloc[0].timeDiff,10)
        self.assertEqual(corrected.iloc[1].status,0)

    def test_buffer_membership_and_no_future_labels(self):
        y=labels(self.fixture(),'deposit','liquidation',25,80,5)
        self.assertEqual(list(y.id),['d1','d2','d3'])
        self.assertEqual(list(y.status),[0,0,0])
        self.assertEqual(list(y.split),['train','train','test'])

    def test_corrected_quarter_day(self):
        df=self.fixture().iloc[:1].copy(); df.timestamp=1704067200
        self.assertEqual(engineer(df,semantics='r-parity').dayOfQuarter.iloc[0],2)
        self.assertEqual(engineer(df,semantics='corrected').dayOfQuarter.iloc[0],1)

if __name__=='__main__':unittest.main()
