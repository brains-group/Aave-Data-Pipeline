"""Collect Messari-schema Aave V3 transactions and account snapshots."""
import argparse
import csv
from datetime import datetime, timezone, timedelta
from decimal import Decimal, localcontext
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import shlex
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .datasets import dataset_path, market_name, read_config
from tqdm import tqdm

LOGGER = logging.getLogger("aave_collection")
LOGGER.addHandler(logging.NullHandler())

SUBGRAPHS = {
    "polygon": "6yuf1C49aWEscgk5n9D1DekeG1BCk5Z9imJYJT3sVmAT",
    "avalanche": "72Cez54APnySAn6h8MswzYkwaL9KjvuuKnKArnPJ8yxb",
}
EVENTS = {"borrows": "borrow", "deposits": "deposit", "withdraws": "withdraw",
          "repays": "repay", "liquidates": "liquidation"}
ACCOUNT_FIELDS = "id borrowCount depositCount closedPositionCount flashloanCount liquidateCount liquidationCount openPositionCount positionCount receivedCount repayCount rewardsClaimedUSD transferredCount withdrawCount"
FIELDS = {name: "id timestamp amount amountUSD asset { id symbol decimals } market { id } hash blockNumber logIndex gasLimit gasPrice gasUsed nonce " + (
    "liquidatee { id } liquidator { id } profitUSD" if name == "liquidates" else "account { id } position { id }") for name in EVENTS}
FIELDS.update(tokens="id decimals name symbol type", accounts=ACCOUNT_FIELDS)
COLUMNS = "id type timestamp user userAlias pool reserve amount amountUSD liquidatee liquidateeAlias liquidator liquidatorAlias profitUSD version deployment transactionHash blockNumber logIndex assetAddress".split()


def load_api_key(path=None):
    """Read the API key from the project .env without overriding the shell."""
    if "THEGRAPH_API_KEY" in os.environ:
        return
    path = Path(path) if path is not None else Path.cwd() / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if separator and name.strip() == "THEGRAPH_API_KEY":
            # Accept plain or quoted keys and comments; never execute shell code.
            parts = shlex.split(value, comments=True)
            if len(parts) > 1:
                raise ValueError("THEGRAPH_API_KEY in .env must be a single value")
            os.environ["THEGRAPH_API_KEY"] = parts[0] if parts else ""
            return


class Client:
    def __init__(self, endpoint, retries=8, timeout=60, max_requests=0):
        self.endpoint, self.retries, self.timeout = endpoint, retries, timeout
        if retries < 1 or max_requests < 0:
            raise ValueError("Positive retries and nonnegative request budget required")
        self.max_requests = max_requests
        self.requests = 0

    def error_detail(self, value):
        text = str(value)
        secrets = [os.environ.get("THEGRAPH_API_KEY", "")]
        match = re.search(r"/api/([^/]+)/subgraphs/", self.endpoint)
        if match:
            secrets.append(match.group(1))
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        text = text.replace(self.endpoint, "[endpoint]")
        text = re.sub(r"https?://[^\s\"<>]+", "[URL]", text)
        return " ".join(text.split())[:1200]

    def query(self, query):
        for attempt in range(self.retries):
            if self.requests >= self.max_requests:
                raise RuntimeError(f"Request budget exhausted ({self.requests}/{self.max_requests}); saved pages can be resumed")
            self.requests += 1  # Count every attempted HTTP request, including retries.
            LOGGER.info("HTTP attempt %s/%s", self.requests, self.max_requests)
            try:
                request = Request(self.endpoint, data=json.dumps({"query": query}).encode(),
                                  headers={"Content-Type": "application/json",
                                           "Accept": "application/json",
                                           "User-Agent": "craft-soc-aave-collector/1.0"})
                with urlopen(request, timeout=self.timeout) as response:
                    result = json.load(response)
                if result.get("errors"):
                    raise ValueError("GraphQL errors: " + json.dumps(result["errors"]))
                if not isinstance(result.get("data"), dict):
                    raise ValueError("GraphQL response is missing data")
                return result["data"]
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                if isinstance(exc, HTTPError):
                    try:
                        body = exc.read(4096).decode(errors="replace")
                    except OSError:
                        body = "(error body unavailable)"
                    detail = self.error_detail(f"HTTP {exc.code}: {body}")
                else:
                    detail = self.error_detail(f"{type(exc).__name__}: {exc}")
                if isinstance(exc, HTTPError) and exc.code in (400, 401, 402, 403, 404):
                    raise RuntimeError(f"Graph endpoint rejected request: {detail}") from None
                if "missing block:" in detail:
                    raise RuntimeError(f"Snapshot unavailable: {detail}") from None
                if attempt + 1 == self.retries:
                    raise RuntimeError(f"Graph request failed after {self.retries} attempts: {detail}; saved pages can be resumed") from None
                delay = min(60, 2 ** attempt) + random.random()
                LOGGER.warning(f"Request failed ({detail}); retry {attempt + 1}/{self.retries} in {delay:.1f}s")
                time.sleep(delay)


class Cache:
    def __init__(self, path, fields=None, chronological=None):
        self.fields = FIELDS if fields is None else fields
        self.chronological = set(EVENTS) if chronological is None else set(chronological)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS rows(entity TEXT, id TEXT, timestamp INTEGER, payload TEXT,
            PRIMARY KEY(entity,id));
          CREATE INDEX IF NOT EXISTS event_time ON rows(entity,timestamp);
          CREATE TABLE IF NOT EXISTS jobs(entity TEXT, start INTEGER, end INTEGER, block INTEGER,
            cursor TEXT DEFAULT '', done INTEGER DEFAULT 0, PRIMARY KEY(entity,start,end));
        ''')
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(jobs)')}
        for name, declaration in (("mode", "TEXT DEFAULT 'id'"),
                                  ("time_cursor", "INTEGER"),
                                  ("legacy_floor", "TEXT DEFAULT ''")):
            if name not in columns:
                with self.db:
                    self.db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {declaration}')

    def missing(self, entity, start, end):
        intervals = self.db.execute("SELECT start,end FROM jobs WHERE entity=? AND done=1 ORDER BY start", (entity,))
        for lo, hi in intervals:
            if hi <= start:
                continue
            if lo >= end:
                break
            if lo > start:
                yield start, lo
            start = max(start, hi)
        if start < end:
            yield start, end

    def collect(self, client, entity, start, end, block, page_size, on_page=None):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO jobs(entity,start,end,block) VALUES(?,?,?,?)", (entity, start, end, block))
        cursor, done, block = self.db.execute("SELECT cursor,done,block FROM jobs WHERE entity=? AND start=? AND end=?", (entity, start, end)).fetchone()
        chronological = entity in self.chronological
        if chronological:
            with self.db:
                self.db.execute("UPDATE jobs SET mode='time', legacy_floor=cursor, cursor='', time_cursor=start "
                                "WHERE entity=? AND start=? AND end=? AND mode='id' AND done=0",
                                (entity, start, end))
            cursor, time_cursor, legacy_floor = self.db.execute(
                "SELECT cursor,time_cursor,legacy_floor FROM jobs WHERE entity=? AND start=? AND end=?",
                (entity, start, end)).fetchone()
        else:
            time_cursor, legacy_floor = None, ''
        snapshot_recoveries = 0
        pages = 0
        collected = 0
        while not done:
            if chronological:
                filters = [f'{{timestamp_gte: "{start}", timestamp_lt: "{end}"}}']
                if legacy_floor:
                    filters.append(f'{{id_gt: {json.dumps(legacy_floor)}}}')
                if cursor:
                    filters.append(f'{{or: [{{timestamp_gt: "{time_cursor}"}}, '
                                   f'{{timestamp: "{time_cursor}", id_gt: {json.dumps(cursor)}}}]}}')
                elif time_cursor is not None:
                    filters.append(f'{{timestamp_gte: "{time_cursor}"}}')
                where = 'and: [' + ', '.join(filters) + ']'
                order = 'timestamp'
            else:
                where = f'id_gt: {json.dumps(cursor)}' if cursor else ''
                order = 'id'
            query = f'{{ {entity}(first: {page_size}, orderBy: {order}, orderDirection: asc, block: {{number: {block}}}, where: {{{where}}}) {{ {self.fields[entity]} }} }}'
            try:
                rows = client.query(query).get(entity)
            except RuntimeError as exc:
                if entity not in self.chronological or "missing block:" not in str(exc):
                    raise
                if snapshot_recoveries >= 3:
                    raise RuntimeError("Snapshot recovery failed 3 times without page progress; "
                                       "saved pages can be resumed") from exc
                # Transaction entities are immutable. Keep the covered time range and
                # cursor, but replace a snapshot that indexers have stopped serving.
                meta = client.query("{ _meta { hasIndexingErrors block { number timestamp } } }")["_meta"]
                new_block = int(meta["block"]["number"])
                if (meta["hasIndexingErrors"] or new_block <= block
                        or int(meta["block"]["timestamp"]) < end):
                    raise RuntimeError("No healthy newer snapshot covers the saved interval") from exc
                with self.db:
                    self.db.execute("UPDATE jobs SET block=? WHERE entity=? AND start=? AND end=?",
                                    (new_block, entity, start, end))
                LOGGER.info(f"{entity}: snapshot block {block} unavailable; resuming at block "
                      f"{new_block} with the saved cursor and date range")
                block = new_block
                snapshot_recoveries += 1
                continue
            if not isinstance(rows, list):
                raise RuntimeError(f"Missing {entity} response; page was not cached")
            ids = [row["id"] for row in rows]
            if chronological:
                keys = [(int(row['timestamp']), row['id']) for row in rows]
                if (keys != sorted(set(keys)) or len(ids) != len(set(ids))
                        or any(not start <= t < end or (legacy_floor and i <= legacy_floor) for t, i in keys)
                        or (keys and time_cursor is not None and keys[0] <= (time_cursor, cursor))):
                    raise RuntimeError("Non-advancing chronological pagination; page was not cached")
                if rows:
                    time_cursor = keys[-1][0]
            elif ids != sorted(set(ids)) or (ids and ids[0] <= cursor):
                raise RuntimeError("Non-advancing or unordered pagination; page was not cached")
            done = len(rows) < page_size
            cursor = ids[-1] if ids else cursor
            with self.db:
                self.db.executemany("INSERT OR REPLACE INTO rows VALUES(?,?,?,?)", [(entity, r["id"], int(r.get("timestamp", 0)), json.dumps(r)) for r in rows])
                self.db.execute("UPDATE jobs SET cursor=?,done=?,time_cursor=? WHERE entity=? AND start=? AND end=?", (cursor, done, time_cursor, entity, start, end))
            if on_page is not None:
                on_page(rows)
            # Bound consecutive failures, not recoveries over the entire download.
            snapshot_recoveries = 0
            pages += 1
            collected += len(rows)
            status = "complete" if done else "continuing"
            LOGGER.info(f"{entity}: page {pages} cached {len(rows):,} rows; "
                  f"{collected:,} rows this pass; cursor={cursor or '(empty)'}; "
                  f"{status} (range {start}..{end})")

    def rows(self, entity, start=0, end=2**63-1):
        for (payload,) in self.db.execute("SELECT payload FROM rows WHERE entity=? AND timestamp>=? AND timestamp<? ORDER BY timestamp,id", (entity, start, end)):
            yield json.loads(payload)



def collect_range(cache, client, entity, start, end, block, page_size):
    origin = start
    if start == 0:
        origin = cache.db.execute("SELECT MIN(timestamp) FROM rows WHERE entity=?", (entity,)).fetchone()[0]
    def covered_days():
        if origin is None:
            return 0.0
        intervals = cache.db.execute(
            "SELECT start, CASE WHEN done=1 THEN end ELSE time_cursor END FROM jobs "
            "WHERE entity=? AND (done=1 OR mode='time') ORDER BY start", (entity,))
        position, covered = origin, 0
        for lo, hi in intervals:
            if hi is None:
                continue
            lo, hi = max(lo, origin), min(hi, end)
            if hi > max(position, lo):
                covered += hi - max(position, lo)
                position = hi
        return covered / 86400

    displayed = covered_days()
    # tqdm's initial value excludes cached coverage from its rate/ETA samples.
    with tqdm(desc=entity, total=(end - origin) / 86400 if origin is not None else 0,
              initial=displayed, unit="day", dynamic_ncols=True,
              bar_format="{desc}: {percentage:3.0f}%|{bar}| {n:.1f}/{total:.1f} days "
                         "[{elapsed}<{remaining}, {rate_fmt}{postfix}]") as progress:
        def update(rows):
            nonlocal origin, displayed
            if start == 0 and rows:
                earliest = min(int(row['timestamp']) for row in rows)
                origin = min(origin, earliest) if origin is not None else earliest
            if origin is None:
                return
            progress.total = max(0, (end - origin) / 86400)
            covered = covered_days()
            progress.update(max(0, covered - displayed))
            displayed = covered
            if rows:
                progress.set_postfix_str(datetime.fromtimestamp(int(rows[-1]['timestamp']), timezone.utc).strftime('%Y-%m-%d'))
        pending = list(cache.db.execute(
            "SELECT start,end,cursor,block,mode,time_cursor,legacy_floor FROM jobs WHERE entity=? AND done=0 "
            "AND start<? AND end>?", (entity, end, start)))
        for a, b in list(cache.missing(entity, start, end)):
            bounds = sorted({a, b} | {x for job in pending for x in job[:2] if a < x < b})
            for left, right in zip(bounds, bounds[1:]):
                parents = [job for job in pending if job[0] <= left and job[1] >= right]
                if parents:
                    parent = max(parents, key=lambda job: job[6] if job[4] == 'time' else job[2])
                    with cache.db:
                        cache.db.execute(
                            "INSERT OR IGNORE INTO jobs(entity,start,end,block,cursor,mode,time_cursor,legacy_floor) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (entity, left, right, parent[3], parent[2], parent[4], parent[5], parent[6]))
                cache.collect(client, entity, left, right, block, page_size, on_page=update)
        progress.set_postfix_str("complete")


def configure_logging(market, directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"aave_v3_{market}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_{os.getpid()}.log"
    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(handler)
    return path, handler


def alias(address):
    return "Account " + address.lower() if address else ""


def transaction(row, entity, market):
    with localcontext() as ctx:
        ctx.prec = 100
        amount = format(Decimal(row["amount"]) / Decimal(10) ** int(row["asset"]["decimals"]), "f")
    result = dict(id=row["id"], type=EVENTS[entity], timestamp=row["timestamp"],
                  pool=row["market"]["id"], reserve=row["asset"]["symbol"], amount=amount,
                  amountUSD=row["amountUSD"], version="V3", deployment=market.title())
    for field in (["liquidatee", "liquidator"] if entity == "liquidates" else ["user"]):
        address = row[field if field != "user" else "account"]["id"]
        result[field], result[field + "Alias"] = address, alias(address)
    if entity == "liquidates":
        # Messari's profitUSD is already a USD BigDecimal, not wei.
        result["profitUSD"] = row["profitUSD"]
    result.update(transactionHash=row.get("hash"), blockNumber=row.get("blockNumber"),
                  logIndex=row.get("logIndex"), assetAddress=row["asset"].get("id"))
    return result


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def date_value(value, end=False):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if end and len(value) == 10:
        parsed += timedelta(days=1)
    return int(parsed.timestamp())


def main(argv=None, default_config=None, default_env=None, default_log=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--log-dir", type=Path, default=default_log)
    parser.add_argument("--env-file", type=Path, default=default_env)
    parser.add_argument("--max-requests", type=int, default=0, help="Hard HTTP attempt budget, including retries; default disables live queries")
    parser.add_argument("--free-access-confirmed", action="store_true", help="Confirm account free capacity covers this budget and paid overage is disabled")
    parser.add_argument("--include-supplementary", action="store_true", help="Collect supported simulator events/history separately after schema verification")
    parser.add_argument("--supplementary-only", action="store_true", help="Only supplementary collection; avoid core/account refresh")
    parser.add_argument("--market", type=market_name, default=None)
    parser.add_argument("--start-date", help="Inclusive ISO date/time (UTC); default: all history")
    parser.add_argument("--end-date", help="Inclusive calendar date, or exclusive ISO instant; default: now")
    parser.add_argument("--endpoint", help="Compatible Messari Aave V3 GraphQL endpoint")
    parser.add_argument("--allow-new-source", action="store_true", help="Explicitly allow a new deployment cache alongside existing market caches")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--retries", type=int, default=8)
    args = parser.parse_args(argv)
    config = read_config(args.config)
    legacy = Path(config["CACHE_DIR"]) / "data_collection"
    shared = Path(config["COLLECTION_CACHE_DIR"]) / "data_collection"
    if legacy.exists() and legacy.resolve() != shared.resolve() and any(legacy.glob("aave_v3/*/*/raw.sqlite3")):
        parser.error("Legacy collection cache exists: migrate it to TRANSACTIONS_PATH/.cache/data_collection before collecting; refusing an empty replacement cache")
    load_api_key(args.env_file)
    if args.max_requests <= 0 or not args.free_access_confirmed:
        parser.error("Live collection disabled: establish free capacity and disabled paid overage, then supply --free-access-confirmed --max-requests N. Use aave-cache-audit offline.")
    market = args.market or market_name(os.environ.get("AAVE_MARKET", config.get("AAVE_MARKET", "polygon")))
    start = date_value(args.start_date) if args.start_date else 0
    end = date_value(args.end_date, True) if args.end_date else int(time.time())
    requested_end = end
    if not 0 <= start < end or not 1 <= args.page_size <= 1000 or args.retries < 1:
        parser.error("Require 0 <= start < end, page size 1..1000, and positive retries")
    endpoints = config.get("AAVE_V3_ENDPOINTS", {})
    endpoint = args.endpoint or endpoints.get(market)
    if not endpoint:
        subgraph = config.get("AAVE_V3_SUBGRAPHS", {}).get(market, SUBGRAPHS.get(market))
        key = os.environ.get("THEGRAPH_API_KEY")
        if not subgraph or not key:
            parser.error("Set THEGRAPH_API_KEY and a market subgraph ID, or supply --endpoint / AAVE_V3_ENDPOINTS")
        endpoint = f"https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph}"
    log_path, log_handler = configure_logging(market, Path(args.log_dir or config["LOG_DIR"]))
    tqdm.write(f"Detailed collection log: {log_path}")
    client = Client(endpoint, args.retries, max_requests=args.max_requests)
    from .shared_cache import collection_lock
    try:
        with collection_lock(Path(config["COLLECTION_CACHE_DIR"]), market):
            return run_collection(args, config, market, start, end, requested_end, client)
    finally:
        LOGGER.removeHandler(log_handler)
        log_handler.close()


def run_collection(args, config, market, start, end, requested_end, client):
    meta = client.query("{ _meta { deployment hasIndexingErrors block { number timestamp } } }")["_meta"]
    if meta["hasIndexingErrors"]:
        raise RuntimeError("Subgraph reports indexing errors; refusing to cache incomplete results")
    block = int(meta["block"]["number"])
    # Never certify an unindexed interval. Exclude the tip second until the next run.
    end = min(end, int(meta["block"]["timestamp"]))
    if start >= end:
        raise ValueError("Requested start is beyond the available indexed data")
    namespace = hashlib.sha256(meta["deployment"].encode()).hexdigest()[:16]
    cache_dir = Path(config["COLLECTION_CACHE_DIR"]) / "data_collection" / "aave_v3" / market / namespace
    if not args.supplementary_only and not (cache_dir / "raw.sqlite3").exists() and not args.allow_new_source:
        if any(cache_dir.parent.glob("*/raw.sqlite3")):
            raise RuntimeError("Different source deployment detected; refusing to silently select an empty cache. Verify source identity and use --allow-new-source if intended.")
    tx_metadata = dataset_path(config, "transactions", market).with_suffix(".metadata.json")
    if not args.supplementary_only and tx_metadata.exists() and json.loads(tx_metadata.read_text()).get("deployment") != meta["deployment"]:
        raise RuntimeError("Output belongs to a different source deployment; choose separate output directories")
    if args.include_supplementary or args.supplementary_only:
        from .indexed_supplementary import collect_supplementary
        collect_supplementary(client, config, market, meta, start, end, requested_end, args.page_size)
    if args.supplementary_only:
        return
    cache = Cache(cache_dir / "raw.sqlite3")
    try:
        for entity in EVENTS:
            collect_range(cache, client, entity, start, end, block, args.page_size)
        # These are snapshots, not time series: show rows without a false day ETA.
        for entity in ("tokens", "accounts"):
            with tqdm(desc=entity, unit="row", dynamic_ncols=True) as progress:
                cache.collect(client, entity, block, block + 1, block, args.page_size,
                              on_page=lambda rows: progress.update(len(rows)))
        tx_path = dataset_path(config, "transactions", market)
        users_path = dataset_path(config, "users", market)
        write_csv(tx_path, COLUMNS, (transaction(row, entity, market) for entity in EVENTS for row in cache.rows(entity, start, end)))
        write_csv(users_path, ACCOUNT_FIELDS.split() + ["alias", "version", "deployment", "snapshotBlock"],
                  (dict(row, alias=alias(row["id"]), version="V3", deployment=market.title(), snapshotBlock=block) for row in cache.rows("accounts")))
        for entity in FIELDS:
            rows = cache.rows(entity, start, end) if entity in EVENTS else cache.rows(entity)
            # Nested raw fields are retained losslessly as JSON inside a CSV cell.
            write_csv(cache_dir / f"{entity}.csv", ["id", "payload"], ({"id": row["id"], "payload": json.dumps(row)} for row in rows))
        manifest = {"market": market, "deployment": meta["deployment"], "snapshot_block": block,
                    "requested_start_inclusive": start, "requested_end_exclusive": requested_end,
                    "start_inclusive": start, "end_exclusive": end,
                    "http_attempts": client.requests, "request_budget": client.max_requests,
                    "ordering": "timestamp,id collection order; not EVM execution order",
                    "snapshot_consistency": "Jobs may use different blocks after recovery; historical indexing revisions before cursor are not reconciled",
                    "jobs": [dict(zip(("entity", "start", "end", "block", "done"), r)) for r in cache.db.execute("SELECT entity,start,end,block,done FROM jobs")], "accounts": "snapshot at indexed block, not date-filtered"}
        tx_path.with_suffix(".metadata.json").write_text(json.dumps(manifest, indent=2) + "\n")
        tqdm.write(f"Saved {tx_path} and {users_path}; indexed coverage ends at {datetime.fromtimestamp(end, timezone.utc).isoformat()}")
    except BaseException as exc:
        LOGGER.error("Collection stopped: %s", client.error_detail(exc))
        raise
    finally:
        cache.db.close()


if __name__ == "__main__":
    main()
