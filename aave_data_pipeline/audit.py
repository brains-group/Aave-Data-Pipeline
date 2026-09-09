"""Read-only cache coverage and provenance audit; never constructs a live client."""
import argparse
import json
import sqlite3
from pathlib import Path
from .collect import EVENTS


def inspect_cache(path):
    path = Path(path).resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        counts = {r[0]:dict(rows=r[1], first_timestamp=r[2], last_timestamp=r[3])
                  for r in db.execute('SELECT entity,count(*),min(timestamp),max(timestamp) FROM rows GROUP BY entity')}
        jobs = [dict(zip(('entity','start','end','block','done','mode','time_cursor','cursor','legacy_floor'),r))
                for r in db.execute('SELECT entity,start,end,block,done,mode,time_cursor,cursor,legacy_floor FROM jobs')]
    return {'cache':str(path),'bytes':path.stat().st_size,'entities':counts,'jobs':jobs,
            'missing_core_entities':[e for e in EVENTS if e not in counts],
            'http_attempts':0,'consistency':'read-only SQLite transaction; cache may continue growing'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    if a.output.exists(): p.error('Refusing to overwrite existing audit')
    result=inspect_cache(a.cache)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'entities':result['entities'],'missing_core_entities':result['missing_core_entities'],'jobs':len(result['jobs']),'http_attempts':0},indent=2))

if __name__=='__main__':main()
