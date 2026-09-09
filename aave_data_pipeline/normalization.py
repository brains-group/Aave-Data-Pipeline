"""Explicit simulator enrichment, separate from consumer/core survival tables."""
from decimal import Decimal,localcontext
import pandas as pd


def token_units(raw, decimals):
    if Decimal(str(decimals)) != int(decimals) or not 0 <= int(decimals) <= 255:
        raise ValueError('Invalid token decimals')
    with localcontext() as ctx:
        ctx.prec=100
        value=Decimal(str(raw))
        if not value.is_finite() or value<0 or value != value.to_integral_value():raise ValueError('Invalid raw token amount')
        return format(value/Decimal(10)**int(decimals),'f')


def simulator_view(core, liquidation_details, market, source_identity):
    """Join verified dual-leg logs by transaction hash/log index, never timestamp alone.

    Evidence must identify market, debt/collateral symbols, raw amounts and decimals.
    Caller supplies a provenance identity. Output does not replace the core CSV.
    Missing evidence is marked observed_only; no placeholder asset or amount is used.
    """
    if not source_identity:raise ValueError('Supplementary source identity required')
    if 'market' in core and not core['market'].eq(market).all():
        raise ValueError('Core market mismatch')
    keys=['transactionHash','logIndex']
    detail=liquidation_details.copy()
    if not detail['market'].eq(market).all():raise ValueError('Evidence market mismatch')
    if detail[keys].isna().any().any() or detail.duplicated(keys).any():
        raise ValueError('Ambiguous liquidation log identity')
    detail['debt_to_cover']=[token_units(v,d) for v,d in zip(detail.debt_amount_raw,detail.debt_decimals)]
    detail['collateral_seized']=[token_units(v,d) for v,d in zip(detail.collateral_amount_raw,detail.collateral_decimals)]
    columns=keys+['debt_symbol','collateral_symbol','debt_to_cover','collateral_seized']
    out=core.merge(detail[columns],on=keys,how='left',validate='many_to_one')
    liq=out.type.eq('liquidation')
    if out.loc[~liq,'debt_to_cover'].notna().any():raise ValueError('Liquidation evidence matched a non-liquidation core event')
    out['observed_only']=liq & out['debt_to_cover'].isna()
    out['supplementary_source']=source_identity
    return out
