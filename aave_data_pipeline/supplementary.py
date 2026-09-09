"""Offline ingestion of decoded simulator evidence, isolated from core cache.

No assumed GraphQL entity names, no RPC, no expansion into survival observations.
Input is JSON Lines decoded by a provenance-identified source. Unsupported or
incomplete histories remain explicitly incomplete in the manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from .datasets import market_name

SOURCES = {'collateral_usage','atoken_transfer','emode','reserve_parameters',
           'reserve_indices','oracle_prices','rate_mode','flashloan','user_reserve_snapshot'}


def ingest(path, cache_root, manifest):
    required={'market','chain_id','source','source_identity','coverage_start','coverage_end','coverage_complete','deployment_address'}
    if required-manifest.keys(): raise ValueError('Missing source provenance fields')
    market=market_name(manifest['market']); source=manifest['source']
    if source not in SOURCES: raise ValueError('Unsupported supplementary source')
    if manifest['coverage_complete'] not in (True,False): raise ValueError('Explicit coverage completeness required')
    if manifest['coverage_start']>=manifest['coverage_end']: raise ValueError('Invalid coverage interval')
    if market in {'polygon','avalanche'} and manifest['chain_id'] != {'polygon':137,'avalanche':43114}[market]:
        raise ValueError('Market and chain ID disagree')
    identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    target=Path(cache_root)/'supplementary'/'aave_v3'/market/source/identity
    target.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(target/'raw.sqlite3')
    digest=hashlib.sha256(); count=0
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            with Path(path).open('rb') as stream:
                for line in stream:
                    digest.update(line); row=json.loads(line)
                    for key in ('id','timestamp','blockNumber','transactionHash','logIndex'):
                        if key not in row: raise ValueError('Supplementary row lacks '+key)
                    if not manifest['coverage_start']<=row['timestamp']<manifest['coverage_end']:
                        raise ValueError('Row outside declared source interval')
                    payload=json.dumps(row,sort_keys=True)
                    old=db.execute('SELECT payload FROM records WHERE id=?',(row['id'],)).fetchone()
                    if old and old[0]!=payload: raise ValueError('Source changed an existing record; use a new source identity')
                    db.execute('INSERT OR IGNORE INTO records VALUES(?,?)',(row['id'],payload)); count+=1
        info=dict(manifest,input_sha256=digest.hexdigest(),input_rows=count,http_attempts=0,
                  survival_view=False,execution_order='blockNumber, transactionIndex if supplied, logIndex')
        (target/'manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    finally: db.close()
    return target


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path); p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--cache-root',required=True,type=Path)
    a=p.parse_args(argv); print(ingest(a.input,a.cache_root,json.loads(a.manifest.read_text())))

if __name__=='__main__':main()
