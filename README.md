# Aave Data Pipeline

Extracted from the existing CRAFT-SOC Python collector; chronological pagination,
snapshot recovery, legacy cursors, decimal amounts, credentials redaction and
market/source cache namespaces remain intact. The package does not contain models
or the simulator. See [progress and evidence](docs/HANDOFF.md).

```bash
python -m pip install --no-deps --no-build-isolation -e .
python -m unittest discover -s tests -v
python -m aave_data_pipeline.collect --help
python -m aave_data_pipeline.audit --cache /absolute/path/raw.sqlite3 --output /tmp/cache-audit-new.json
```

Configure paths relative to the config file, never the installed package. Standalone
CLI defaults to `config.json` in the current directory or `AAVE_PIPELINE_CONFIG`.
Copy sample.config.json and sample.env; keep the actual .env ignored. Pass --env-file
when outside its directory. Consumer wrappers preserve their root .env and craft-soc's
codes/config.json, root log/, and original codes/cache directory. The recommender's
pipeline.sample.config.json explicitly points to that same cache without moving it.
Only one writer may use a cache at a time.

CSV output paths are directories. Filenames include protocol/version/market.
Cache paths are `CACHE_DIR/data_collection/aave_v3/<market>/<deployment-hash>/raw.sqlite3`.
Never copy an empty cache over the old one. Supplementary evidence lives in a separate
`supplementary/aave_v3/<market>/<source>/<provenance-hash>/` tree.

## Collection and zero spending

Default market is Polygon; default request range is all history through now.
Start is inclusive. Calendar end dates include the entire UTC day; ISO instants
are exclusive. Exports record requested and indexed intervals separately and
exclude the indexed tip second. Polygon and Avalanche IDs are retained from the
original collector, but current endpoint availability is not certified by offline tests.

The Graph advertises 100,000 monthly free queries ([pricing](https://thegraph.com/studio-pricing/),
checked September 8, 2026). Remaining account capacity and disabled paid overage must
be established independently. No billing activation or positive paid allowance is
required or recommended here. The default request budget is zero.

Only when free capacity is established:

```bash
python -m aave_data_pipeline.collect --config /absolute/path/config.json \
  --market polygon --start-date 2023-01-01 --end-date 2023-12-31 \
  --free-access-confirmed --max-requests 100
```

100 is an example cap, not a claim about available allowance. Every HTTP attempt,
including retries and metadata, counts. Saved pages survive exhaustion. No new
requests measure progress. Authentication errors redact secrets. Snapshot recovery
can mix historical indexing revisions between jobs/blocks; it cannot discover records
inserted behind a cursor. A successful monotonic page check cannot prove endpoint
secondary-order guarantees; the Graph Node implementation uses ID tie ordering,
but the serving indexer version is not independently known.

## Survival formatting

```bash
python -m aave_data_pipeline.survival \
  --transactions /path/transactions_aave_v3_polygon.csv \
  --stablecoins /path/stablecoins.csv --output /tmp/survival-new-run \
  --tasks journal --semantics corrected \
  --train-cutoff 1722526142 --test-cutoff 1755726959 --buffer-seconds 2592000
```

Cutoffs above come from the local R caller, not the misleading date comments in it.
Choose `benchmark` for its verified 16 task folders, `journal` for the verified 25
core-event pair folders. Supplementary event types never enter this view. Liquidations
are attributed to the liquidated borrower; liquidator identities are not predictors.

Outputs: features.csv, each pair's labels.csv/data.csv, and manifest.json with hashes,
feature schema, counts, units and assumptions. Observation IDs and source event IDs
remain aligned; repeated exact-time outcomes get distinct observation IDs. Existing
output directories are refused. RDS input is optional through pyreadr, and no R
runtime is required. `AAVE_SURVIVAL_DATA=/tmp/survival-new-run` selects these CSVs in
the recommender. Existing model caches must be isolated for a new dataset.

`r-parity` preserves the local R primitive's one-second self-outcome shift,
user/reserve grouping and pair-specific observed censoring end. `corrected` uses
strictly later timestamps for self-transitions, borrower-wide liquidation targets,
and explicit split cutoffs for censoring. Different event types may coincide at
zero duration; classification preprocessing excludes nonpositive durations.
Both modes use the original chronological split with a 30-day index buffer by default;
no random split is regenerated. The local R alias caller is defective: its extra
account-liquidated rows never reach the label builder. This port uses explicit tasks;
`r-parity` is not a claim of whole-dataset parity with that broken caller.

The active cumulative user, running modes, active-day windows, 30-day market windows,
cyclic calendar, price ratio and logarithm features are ported. They include the index
event, which is observed at prediction origin. Stable input order resolves timestamp
ties; this is not verified EVM ordering. The historical quarter-day formula is kept
only in parity mode. `Preprocessor` provides train-fitted sample-standard-deviation
scaling, categorical encoding, optional PCA, separated identities/targets and the
R horizon classification filter. Encoding alignment intentionally corrects the R
independent-test-dummy behavior. Full R/Python output parity has not been established;
R execution was deprioritized at the user's request. Original label RDS was inspected
using Python and uses a different ID format from the current transaction source.

Do not use these outputs for manuscript results until representative feature/label
parity and source/split lineage have been resolved. The implementation is currently
in-memory and is not benchmarked for a full multi-million-row formatting run.

## Supplementary simulator evidence

```bash
python -m aave_data_pipeline.supplementary --input decoded-events.jsonl \
  --manifest source-manifest.json --cache-root /path/cache
```

This offline importer requires explicit chain/market, deployment address, source
identity, source kind, coverage start/end and completeness; rows retain ordering
metadata and lossless decoded payloads. It does not claim unavailable historical
RPC/subgraph coverage or generate survival events. See docs/SOURCES.md. Live source
adapters and historical deployment mapping remain unfinished.
