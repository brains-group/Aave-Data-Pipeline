"""Explicit core-event tasks, deterministic labels, portable feature/label exports."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .features import engineer, core_view

# Verified against local benchmark folders and all 25 journal data.csv paths.
BENCHMARK_TASKS = {
 'borrow': ('deposit','repay','withdraw','liquidation'),
 'deposit': ('borrow','repay','withdraw','liquidation'),
 'repay': ('borrow','deposit','withdraw','liquidation'),
 'withdraw': ('borrow','deposit','repay','liquidation'),
}
JOURNAL_TASKS = {
 'borrow': ('borrow','deposit','repay','withdraw','liquidation'),
 'deposit': ('borrow','deposit','repay','withdraw','liquidation'),
 'repay': ('borrow','deposit','repay','withdraw','liquidation'),
 'withdraw': ('borrow','deposit','repay','withdraw','liquidation'),
 'liquidation': ('borrow','deposit','repay','withdraw','liquidation'),
}


def read_frame(path):
    path = Path(path)
    if path.suffix == '.rds':
        import pyreadr
        return pyreadr.read_r(str(path))[None]
    return pd.read_csv(path)


def labels(frame, index_event, outcome_event, train_cutoff, test_cutoff,
           buffer_seconds=30*86400, semantics='corrected'):
    """R split membership, with separately named corrections. Durations in seconds.

    r-parity: pair-specific observed final time, forced user/reserve grouping,
    subtract one second from self outcomes. Corrected: honor borrower-wide
    liquidation target, strict later timestamp for self transitions, explicit
    cutoff censoring. Different event types can occur simultaneously.
    Left-censored rows lack index IDs and are excluded as in dataLoader.R.
    """
    if not train_cutoff < test_cutoff or buffer_seconds < 0:
        raise ValueError('Require increasing cutoffs and nonnegative buffer')
    if semantics not in ('r-parity','corrected'):
        raise ValueError('Unknown semantics')
    df = core_view(frame)
    result = []
    subjects = ['user'] if outcome_event == 'liquidation' and semantics == 'corrected' else ['user','reserve']
    for split, lower, upper in [('train',-np.inf,train_cutoff),('test',train_cutoff,test_cutoff)]:
        index = df[(df.type == index_event) & (df.timestamp > lower) & (df.timestamp <= upper-buffer_seconds)]
        outcome = df[df.type == outcome_event].copy()
        if index_event == outcome_event and semantics == 'r-parity':
            outcome['timestamp'] -= 1
        outcome = outcome[(outcome.timestamp > lower) & (outcome.timestamp <= upper)]
        final = max(index.timestamp.max(), outcome.timestamp.max()) if len(index) and len(outcome) else (index.timestamp.max() if not len(outcome) else outcome.timestamp.max())
        if semantics == 'corrected':
            final = upper
        groups = {(k if isinstance(k,tuple) else (k,)): g.sort_values('timestamp',kind='stable') for k,g in outcome.groupby(subjects, sort=False, dropna=False)}
        for _, row in index.iterrows():
            key = tuple(row[s] for s in subjects)
            group = groups.get(key)
            candidates = []
            if group is not None:
                side = 'right' if index_event == outcome_event and semantics == 'corrected' else 'left'
                pos = np.searchsorted(group.timestamp.to_numpy(), row.timestamp, side=side)
                if pos < len(group):
                    t = group.iloc[pos].timestamp
                    # data.table exact-time joins expand duplicate outcomes; rolling joins use first.
                    candidates = list(group[group.timestamp == t].itertuples()) if t == row.timestamp else [next(group.iloc[pos:pos+1].itertuples())]
            for n, target in enumerate(candidates or [None]):
                duration = target.timestamp-row.timestamp if target is not None else final-row.timestamp
                result.append({'observation_id':f'{index_event}:{outcome_event}:{row.id}:{split}:{n}',
                    'id':row.id, 'outcome_id':target.id if target is not None else None,
                    'timeDiff':duration, 'status':int(target is not None), 'split':split,
                    'Index Event':index_event, 'Outcome Event':outcome_event})
    return pd.DataFrame(result, columns=['observation_id','id','outcome_id','timeDiff','status','split','Index Event','Outcome Event'])


def join_features(features, targets):
    if features.id.duplicated().any():
        raise ValueError('Feature IDs must be unique within index event')
    return targets.merge(features, on='id', how='inner', validate='many_to_one')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--transactions',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stablecoins',type=Path,required=True,help='Versioned CSV with symbol column')
    p.add_argument('--tasks',choices=['benchmark','journal'],required=True)
    p.add_argument('--semantics',choices=['r-parity','corrected'],required=True)
    p.add_argument('--train-cutoff',type=int,required=True)
    p.add_argument('--test-cutoff',type=int,required=True)
    p.add_argument('--buffer-seconds',type=int,default=30*86400)
    p.add_argument('--timezone',default='UTC')
    a = p.parse_args(argv)
    if a.output.exists():
        p.error('Output already exists; choose a new run directory to preserve results')
    df = read_frame(a.transactions)
    df = df[df.timestamp <= a.test_cutoff]
    features = engineer(df, read_frame(a.stablecoins).symbol, a.semantics, a.timezone)
    a.output.mkdir(parents=True)
    features.to_csv(a.output/'features.csv',index=False)
    tasks = BENCHMARK_TASKS if a.tasks == 'benchmark' else JOURNAL_TASKS
    counts = {}
    for index, outcomes in tasks.items():
        for outcome in outcomes:
            target = labels(df,index,outcome,a.train_cutoff,a.test_cutoff,a.buffer_seconds,a.semantics)
            name = lambda x: 'Liquidated' if x == 'liquidation' else x.title()
            directory = a.output/name(index)/name(outcome)
            directory.mkdir(parents=True)
            target.to_csv(directory/'labels.csv',index=False)
            joined = join_features(features[features.type == index],target)
            if a.tasks == 'journal':
                for column in ['Index Event','Outcome Event']:
                    joined[column] = joined[column].replace({'liquidation':'liquidated'})
            joined.to_csv(directory/'data.csv',index=False)
            counts[f'{index}->{outcome}'] = {'observations':len(target),'joined':len(joined),'events':int(target.status.sum())}
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(2**20),b''): h.update(chunk)
        return h.hexdigest()
    manifest = {k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()}
    manifest.update(input_sha256=digest(a.transactions), stablecoins_sha256=digest(a.stablecoins),
       features=list(features.columns), counts=counts, unit='seconds',
       same_timestamp_order='stable source order, not verified EVM execution order',
       task_provenance='Local benchmark folder matrix / journal 25 pair CSVs inspected 2026-09-08',
       limitations='R parity refers to split/label primitives, not broken alias caller; journal historical CSVs drop IDs; original R output parity required before model use')
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__ == '__main__': main()
