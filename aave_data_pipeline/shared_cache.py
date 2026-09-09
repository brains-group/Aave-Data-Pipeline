"""Serialize writers from all consumers sharing an output folder (POSIX)."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
from .datasets import market_name

@contextmanager
def collection_lock(root, market):
    path = Path(root) / 'locks' / ('aave_v3_' + market_name(market) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'Another collector is using the shared {market} cache; no requests made') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
