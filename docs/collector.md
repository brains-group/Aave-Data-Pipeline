# Aave V3 collection

First, follow the [API key setup instructions](../../README.md#api-key-for-data-collection)
to create a key in Subgraph Studio and put it in the project-root `.env`.
The collector loads that file automatically; an existing shell variable takes
precedence. Use `sample.env` as the template and keep the actual key in `.env`,
which is ignored by Git.
Live collection requires independently verified free capacity and an explicit
`--free-access-confirmed --max-requests N` attempt budget. The default is zero requests.

Run these commands from the project root (config paths are relative to the config
file; an absolute script path also works from another working directory):

```bash
python codes/data_collection/collect.py
python codes/data_collection/collect.py --start-date 2023-01-01 --end-date 2023-12-31
python codes/data_collection/collect.py --market avalanche
python run_all.py --market avalanche
python codes/analysis.py --market avalanche
```

The default market is Polygon (`AAVE_MARKET` in config). The default interval is
all indexed history through now. A start date is inclusive; an end calendar date
includes that entire UTC day, while an end timestamp is exclusive. Collection
reports its actual indexed cutoff, which may lag the requested end. No full
historical download is performed during installation or tests.

`codes/config.json` supplies `TRANSACTIONS_PATH` and `USERS_PATH` as **directories**.
Outputs are `transactions_aave_v3_polygon.csv` and `users_aave_v3_polygon.csv`, or
the corresponding market names. Existing legacy CSVs must be explicitly renamed
or copied to these names if you wish to use them; the collector does not silently
assume their market or coverage. Existing files are replaced atomically after
collection; each export contains the requested transaction interval. Expanding or
shrinking the interval retains cached history. Transaction ordering is by event
type then timestamp/ID; the analysis loader sorts chronologically.

`CACHE_DIR` remains the shared cache root. Collection uses
`data_collection/aave_v3/<market>/<subgraph-deployment>/raw.sqlite3` beneath it.
Raw pages and cursors commit in one SQLite transaction. Chronological pagination uses a `(timestamp, ID)` cursor within the requested
interval, preserving events sharing a timestamp. Completed
intervals (including empty intervals) are reused; interrupted intervals resume
against their original block. If indexers stop serving that block, transaction
collection switches to a healthy newer block covering the same date range,
retaining the saved timestamp and ID cursor. Recovery can repeat throughout a long download;
three snapshot changes without a successfully saved page stop the run, preventing
an endless loop. A saved page resets that limit. This recovery applies to immutable transactions;
mutable account/token snapshots are not mixed across blocks. The indexed tip second is left for the next run.
Raw CSV exports retain the full GraphQL record as a JSON payload. Analysis caches
are separated by market and input file fingerprint, and figures by market.
Run only one collector per market at a time.

The implementation consolidates the **active** Polygon R collectors: borrows,
deposits, withdraws, repays, liquidates, tokens and accounts. The disabled V2-era
collateral/flashloan/price-history collectors are not ported. Account counters
are mutable and are refreshed at each new indexed block; they describe the whole
subgraph at that block, not activity within the requested transaction dates.
User aliases are deterministic address-based labels rather than random names.
Token base units use decimal arithmetic. `profitUSD` is already USD and is not
divided by 10^18 as in the old R processor. A metadata sidecar records the indexed
block and actual transaction interval.

Polygon and Avalanche subgraph IDs come from the supplied R scripts. For another
Aave V3 deployment with the same Messari lending schema, add its ID under
`AAVE_V3_SUBGRAPHS`, add a full endpoint under `AAVE_V3_ENDPOINTS`, or use:

```bash
python codes/data_collection/collect.py --market arbitrum --endpoint 'https://YOUR_ENDPOINT'
```

Do not point this collector at an old Aave V2 or native Aave-schema endpoint.
Authentication uses your `THEGRAPH_API_KEY`; no key from the R source is copied.
Endpoints and schema availability require a live check with your credentials.
HTTP, transport and GraphQL failures retry with capped exponential backoff and
jitter (`--retries`, default 8); authentication and basic HTTP request errors fail
immediately. Exhausted retries preserve completed pages for the next invocation.

The pagination and snapshot approach follows
[The Graph GraphQL API](https://thegraph.com/docs/en/subgraphs/querying/graphql-api/).
The field model follows the supplied scripts and
[Messari lending schema](https://github.com/messari/subgraphs/blob/master/schema-lending.graphql).

Offline tests:

```bash
python -m unittest codes.data_collection.test_collect -v
```

The terminal shows a separate `tqdm` progress bar per transaction type, with
chronologically traversed days, elapsed time, and an approximate remaining time.
A 1,000-record page can advance it by multiple days; no daily windows or extra
progress queries are needed. The current timestamp remains open until all its
records are collected. Busy periods, API retries, and empty date ranges affect
the estimate. For the default all-history range, the first returned/cached event
sets the displayed starting date; this can adjust while an old cache is migrated.
Token and account snapshots still show row counts without a days-based ETA.

Transactions are requested with `orderBy: timestamp`, ascending. Graph Node uses
ID as the secondary sort key, so the next-page filter includes timestamps greater
than the saved timestamp OR the same timestamp with a greater ID. The collector
validates that `(timestamp, ID)` strictly increases and saves both cursor values
atomically with each page. This handles more than 1,000 events at one timestamp
without additional tie-check requests. See the
[Graph Node ordering implementation](https://github.com/graphprotocol/graph-node/blob/master/store/postgres/src/relational_queries.rs).

Old ID-ordered jobs are migrated in place. Their old ID cursor remains a fixed
filter excluding records already downloaded; the remaining records are fetched
chronologically. Completed intervals remain cached. Existing partial-cache
boundaries can divide resumed work, but new daily windows are not created. Do not
run an older collector version against the migrated cache, or run two collectors
against it simultaneously.

Page counts, row counts, cursors, snapshot recoveries, and retry details are written
to a unique per-run file in the project-root `log/` directory, with the market in
its filename. The terminal prints the log path at startup. `log/` is ignored by
Git. To watch the details separately, use `tail -f log/<filename>.log`.
