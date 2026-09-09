"""Configuration and market-specific paths, shared without plotting dependencies."""
import json
import os
from pathlib import Path
import re
import sys


def market_name(value):
    value = value.lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("Market must contain only letters, digits and separating hyphens")
    return value


def read_config(path=None):
    path = Path(path or os.environ.get("AAVE_PIPELINE_CONFIG", "config.json")).expanduser().resolve()
    with path.open() as stream:
        config = json.load(stream)
    for key, default in (("CACHE_DIR", "./cache"), ("OUT_DIR", "../figures"),
                         ("TRANSACTIONS_PATH", "./data"), ("USERS_PATH", "./data"), ("LOG_DIR", "./log")):
        value = Path(config.get(key, default)).expanduser()
        config[key] = str(value if value.is_absolute() else path.parent / value)
    return config


def selected_market(config):
    # Consume the shared option before individual scripts parse their own flags.
    value = os.environ.get("AAVE_MARKET", config.get("AAVE_MARKET", "polygon"))
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--market":
            if i + 1 == len(sys.argv):
                raise ValueError("--market requires a value")
            value = sys.argv[i + 1]
            del sys.argv[i:i + 2]
            break
        if arg.startswith("--market="):
            value = arg.split("=", 1)[1]
            del sys.argv[i]
            break
    return market_name(value)


def dataset_path(config, kind, market):
    directory = Path(config[kind.upper() + "_PATH"])
    if directory.suffix.lower() in (".csv", ".rds"):
        raise ValueError(f"{kind.upper()}_PATH must be a directory, not a file")
    return directory / f"{kind}_aave_v3_{market_name(market)}.csv"
