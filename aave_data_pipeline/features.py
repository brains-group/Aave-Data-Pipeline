"""Port of the active feature_creation.R chain (not its unused PCA helpers)."""
from collections import Counter
import numpy as np
import pandas as pd

CORE = ('borrow', 'deposit', 'withdraw', 'repay', 'liquidation')


def core_view(frame):
    """Core borrower view; supplementary simulator rows cannot enter tasks."""
    df = frame.loc[frame['type'].str.lower().isin(CORE)].copy()
    df['type'] = df['type'].str.lower()
    if 'user' not in df:
        df['user'] = pd.NA
    liq = df['type'].eq('liquidation')
    if liq.any():
        if 'liquidatee' not in df or df.loc[liq, 'liquidatee'].isna().any():
            raise ValueError('Liquidations require explicit liquidatee identity')
        df.loc[liq, 'user'] = df.loc[liq, 'liquidatee']
    if df['user'].isna().any():
        raise ValueError('Core event lacks borrower/account identity')
    if df['id'].isna().any() or df.duplicated(['type', 'id']).any():
        raise ValueError('Missing or duplicate core event identity')
    return df


def engineer(frame, stable_symbols=(), semantics='r-parity', timezone='UTC'):
    """Features include the index action; stable input order breaks timestamp ties.

    r-parity preserves R's quarter-day formula; corrected uses calendar quarters.
    No mutable accounts snapshot is accepted or joined.
    """
    if semantics not in ('r-parity', 'corrected'):
        raise ValueError('Unknown feature semantics')
    df = core_view(frame).loc[lambda d: d.reserve.notna()].copy()
    # Whitelist raw predictors. Present-day account totals must never pass through.
    raw = ['id','type','timestamp','user','pool','reserve','amount','amountUSD']
    if semantics == 'r-parity':
        raw += ['liquidatee','liquidateeAlias','liquidator','profitUSD','deployment']
    df = df[[c for c in raw if c in df]].sort_values('timestamp', kind='stable').reset_index(drop=True)
    for c in ('timestamp','amount','amountUSD'):
        df[c] = pd.to_numeric(df[c], errors='raise')
    df['priceInUSD'] = df.amountUSD / df.amount
    df['coinType'] = np.where(df.reserve.isin(stable_symbols), 'Stable', 'Non-Stable')
    for source, target in [('reserve','userReserveMode'), ('coinType','userCoinTypeMode')]:
        def modes(values):
            counts = Counter()
            result = []
            for value in values:
                counts[value] += 1
                result.append(max(counts, key=counts.get))  # first-seen mode wins ties, as R
            return pd.Series(result, index=values.index)
        df[target] = df.groupby('user', sort=False)[source].transform(modes)
    g = df.groupby('user', sort=False)
    df['userIsNew'] = g.cumcount().eq(0)
    df['userSecondsSinceFirstTransaction'] = df.timestamp - g.timestamp.transform('first')
    df['userSecondsSincePreviousTransaction'] = g.timestamp.diff().fillna(0)
    types = list(CORE) if semantics == 'corrected' else list(df.type.unique())
    for event in types:
        prefix = 'user' + event.capitalize()
        mask = df.type.eq(event)
        count = mask.groupby(df.user, sort=False).cumsum()
        df[prefix+'Count'] = count
        for value, suffix in [('amount',''), ('amountUSD','USD')]:
            total = df[value].where(mask, 0).fillna(0).groupby(df.user, sort=False).cumsum()
            df[prefix+'Sum'+suffix] = total
            df[prefix+'AvgAmount'+suffix] = (total / count).fillna(0)
    dates = pd.to_datetime(df.timestamp, unit='s', utc=True).dt.tz_convert(timezone)
    days = dates.dt.date.map(lambda x: x.toordinal())
    for width, label in [(7,'Weekly'),(30,'Monthly'),(365,'Yearly')]:
        result = np.zeros(len(df), dtype=int)
        for indexes in g.indices.values():
            day = days.iloc[indexes].to_numpy()
            unique = np.unique(day)
            result[indexes] = np.searchsorted(unique, day, side='right') - np.searchsorted(unique, day-width, side='right')
        df['userActiveDays'+label] = result
    # R sorts by user/date for active-days then by timestamp for market features.
    # Preserve that stable tie order for exact historical parity.
    df = df.sort_values(['user','timestamp'], kind='stable').sort_values('timestamp', kind='stable').reset_index(drop=True)
    times = df.timestamp.to_numpy()
    left = np.searchsorted(times, times - 30*86400, side='left')
    for event in types:
        prefix = 'market' + event.capitalize()
        mask = df.type.eq(event).to_numpy()
        cumulative = np.r_[0, np.cumsum(mask)]
        count = cumulative[1:] - cumulative[left]
        df[prefix+'Count'] = count
        for value, suffix in [('amount',''),('amountUSD','USD')]:
            values = np.where(mask, df[value].to_numpy(), 0)
            # Active R sums propagate NA. Reject these instead of silently inventing sums.
            if not np.isfinite(values).all():
                raise ValueError('Nonfinite market amounts require explicit preprocessing')
            cumulative = np.r_[0, np.cumsum(values)]
            total = cumulative[1:] - cumulative[left]
            df[prefix+'Sum'+suffix] = total
            df[prefix+'AvgAmount'+suffix] = total / np.maximum(count, 1)
    dt = pd.to_datetime(df.timestamp, unit='s', utc=True).dt.tz_convert(timezone)
    df['timeOfDay'] = dt.dt.hour + dt.dt.minute / 60 + dt.dt.second / 3600
    df['dayOfWeek'] = dt.dt.dayofweek + 1
    df['dayOfMonth'] = dt.dt.day
    df['dayOfYear'] = dt.dt.dayofyear
    df['quarter'] = dt.dt.quarter
    if semantics == 'r-parity':
        df['dayOfQuarter'] = df.dayOfYear - np.array([0,90,181,273])[df.quarter-1] + 1
    else:
        start = dt.dt.tz_localize(None).dt.to_period('Q').dt.start_time
        df['dayOfQuarter'] = (dt.dt.tz_localize(None).dt.normalize()-start).dt.days+1
    for field, period in [('timeOfDay',24),('dayOfWeek',7),('dayOfMonth',30),('dayOfQuarter',91),('dayOfYear',365),('quarter',4)]:
        for name, fn in [('sin',np.sin),('cos',np.cos)]:
            df[name+field[0].upper()+field[1:]] = fn(2*np.pi*df[field]/period)
    df['isWeekend'] = df.dayOfWeek.isin([6,7])
    df['logAmount'] = np.log1p(df.amount)
    df['logAmountUSD'] = np.log1p(df.amountUSD)
    return df
