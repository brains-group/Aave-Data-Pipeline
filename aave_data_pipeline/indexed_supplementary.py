"""Opt-in, schema-checked indexed evidence; never appended to core survival CSVs.

Only scalar event/snapshot fields and related IDs are downloaded. Related account,
market and position objects are mutable: their current balances/risk flags are not
joined into historical rows. Schema support is not proof of complete chain history.
"""
import hashlib
import json
from pathlib import Path
from .collect import Cache, collect_range, write_csv, LOGGER

# Candidate roots are checked, not assumed to exist on a Messari or official endpoint.
SOURCES = {
    'transfers': ('transaction', ('transfers',)),
    'collateral_changes': ('transaction', ('usageAsCollaterals', 'reserveUsedAsCollateralEnableds', 'reserveUsedAsCollateralDisableds')),
    'emode_changes': ('transaction', ('userEModeSets', 'userEModeSetEvents')),
    'rate_mode_changes': ('transaction', ('swapBorrowRates', 'swapBorrowRateModes')),
    'flashloans': ('transaction', ('flashloans', 'flashLoans')),
    'position_snapshots': ('state_snapshot', ('positionSnapshots',)),
    'reserve_parameter_history': ('parameter_history', ('reserveParamsHistoryItems', 'reservesParamsHistoryItems')),
    'oracle_price_history': ('price_history', ('priceHistoryItems',)),
}


def type_ref(depth=6):
    return 'kind name' + (' ofType { ' + type_ref(depth-1) + ' }' if depth else '')


INTROSPECTION = '{ __schema { queryType { name } types { kind name fields { name type { '+type_ref()+' } args { name type { '+type_ref()+' } } } inputFields { name } enumValues { name } } } }'


def base_type(ref):
    while ref and ref.get('ofType'):
        ref = ref['ofType']
    return ref or {}


def inspect_sources(schema):
    """Select only roots compatible with the collector's timestamp/ID tie pagination."""
    types = {t['name']: t for t in schema['types']}
    roots = {f['name']: f for f in types[schema['queryType']['name']]['fields']}
    available, coverage = {}, {}
    for source, (kind, candidates) in SOURCES.items():
        matches = []
        reasons = []
        for name in candidates:
            if name not in roots:
                continue
            root = roots[name]
            fields = {f['name']: f for f in types[base_type(root['type'])['name']].get('fields') or []}
            args = {a['name']: base_type(a['type']).get('name') for a in root.get('args') or []}
            filters = {f['name'] for f in types.get(args.get('where'), {}).get('inputFields') or []}
            orders = {v['name'] for v in types.get(args.get('orderBy'), {}).get('enumValues') or []}
            required = {'id', 'timestamp'}
            if not required <= fields.keys() or not {'first','where','block','orderBy','orderDirection'} <= args.keys() or not {'and','or','timestamp','timestamp_gt','timestamp_gte','timestamp_lt','id_gt'} <= filters or 'timestamp' not in orders:
                reasons.append(name + ': missing required timestamp/ID pagination fields or filters')
                continue
            selection = []
            for field, info in fields.items():
                ref = base_type(info['type'])
                if ref.get('kind') in ('SCALAR','ENUM'):
                    selection.append(field)
                elif ref.get('kind') == 'OBJECT':
                    nested = {f['name']: f for f in types.get(ref.get('name'), {}).get('fields') or []}
                    if 'id' in nested:
                        # Only asset definitions, not mutable historical state, may be joined.
                        chosen = ['id']
                        if field in ('asset', 'collateralAsset', 'principalAsset'):
                            chosen += [f for f in ('symbol','decimals') if f in nested]
                        selection.append(field + ' { ' + ' '.join(chosen) + ' }')
            available[name] = {'fields': ' '.join(selection), 'source': source, 'kind': kind}
            matches.append(name)
        coverage[source] = {'kind':kind, 'entities':matches, 'status':'supported' if matches else 'unavailable',
                            'reason':'; '.join(reasons) if reasons else (None if matches else 'No candidate entity in serving schema'),
                            'chain_history_complete':False}
    return available, coverage


def atomic_json(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, indent=2) + '\n')
    temp.replace(path)


def collect_supplementary(client, config, market, meta, start, end, requested_end, page_size):
    namespace = hashlib.sha256(meta['deployment'].encode()).hexdigest()[:16]
    root = Path(config['COLLECTION_CACHE_DIR']) / 'supplementary' / 'aave_v3' / market / namespace
    output = Path(config['TRANSACTIONS_PATH']) / 'supplementary' / 'aave_v3' / market / namespace
    root.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    schema_path = root / 'schema.json'
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
    else:
        schema = client.query(INTROSPECTION)['__schema']
        atomic_json(schema_path, schema)
    available, coverage = inspect_sources(schema)
    report = {'market':market, 'deployment':meta['deployment'], 'snapshot_block':meta['block']['number'],
              'requested_start_inclusive':start, 'requested_end_exclusive':requested_end,
              'indexed_end_exclusive':end, 'sources':coverage, 'entities':{},
              'schema_sha256':hashlib.sha256(schema_path.read_bytes()).hexdigest(),
              'limitations':['Schema availability does not certify historical completeness.',
                  'Transfer records can represent collateral or debt tokens; do not blindly treat every transfer as collateral.',
                  'Position snapshots are post-event indexed reconstructions, not independent pre-event chain truth.',
                  'Timestamp/ID collection order is not EVM execution order.',
                  'Nested related objects contain identities, not present-day balances or collateral flags.'],
              'http_attempts_total':client.requests, 'request_budget':client.max_requests}
    manifest = output / 'coverage.json'
    atomic_json(manifest, report)
    for entity, spec in available.items():
        selection_hash = hashlib.sha256(spec['fields'].encode()).hexdigest()[:16]
        cache_path = root / entity / selection_hash / 'raw.sqlite3'
        cache = Cache(cache_path, fields={entity:spec['fields']}, chronological={entity})
        entry = {'status':'incomplete', 'cache':str(cache_path), 'query_fields':spec['fields'],
                 'source_kind':spec['kind'], 'start_inclusive':start,'end_exclusive':end}
        report['entities'][entity] = entry
        atomic_json(manifest, report)
        try:
            collect_range(cache, client, entity, start, end, int(meta['block']['number']), page_size)
            csv_path = output / f'{entity}_{selection_hash}.csv'
            write_csv(csv_path, ['id','timestamp','transactionHash','blockNumber','logIndex','payload'],
                ({'id':row['id'], 'timestamp':row['timestamp'], 'transactionHash':row.get('hash'),
                  'blockNumber':row.get('blockNumber'), 'logIndex':row.get('logIndex'),
                  'payload':json.dumps(row)} for row in cache.rows(entity,start,end)))
            entry.update(status='indexed_interval_complete', csv=str(csv_path),
                rows=cache.db.execute('SELECT COUNT(*) FROM rows WHERE entity=? AND timestamp>=? AND timestamp<?',(entity,start,end)).fetchone()[0])
            LOGGER.info('Supplementary %s: %s rows exported', entity, entry['rows'])
        except BaseException as exc:
            entry['error'] = client.error_detail(exc)
            raise
        finally:
            entry['jobs'] = [dict(zip(('start','end','block','done','cursor','time_cursor'),r)) for r in cache.db.execute('SELECT start,end,block,done,cursor,time_cursor FROM jobs WHERE entity=?',(entity,))]
            cache.db.close()
            report['http_attempts_total'] = client.requests
            atomic_json(manifest, report)
    print(f'Supplementary availability/coverage: {manifest}')
