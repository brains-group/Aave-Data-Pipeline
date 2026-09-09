# Supplementary source evidence

Availability below distinguishes local evidence from an advertised schema. No authenticated
endpoint or RPC calls were made. Historical coverage is unknown unless stated. No paid
access was enabled. Contract-version mapping is not yet sufficient for historical certification.

| Candidate | Availability / coverage evidence | State reconstructed / consumer | Relevance and validation | Collection cost |
|---|---|---|---|---|
| Core borrows/deposits/withdraws/repays/liquidates | All five in existing Polygon cache through exclusive 1788897090; chronological completed intervals. Avalanche ID configured, live schema unverified | Base positions; existing collector and simulator loaders | Historical ID comparisons; liquidation record may lack both debt and seized-collateral legs | Offline audit 0 requests; live 1000-row pages plus retries |
| Collateral enable/disable | Old R usageAsCollaterals disabled; V3 emits ReserveUsedAsCollateralEnabled/Disabled; no verified indexed history in current cache | Collateral eligibility per borrower/reserve; protocol currently treats all supply as collateral | Compare HF before/after toggles against independent state; do not add supply again | Existing decoded-log import free offline; live source budget unknown |
| aToken transfers | Not a core collector entity; no local coverage established | Transfers of supplied positions, distinct from Pool supply/withdraw; simulator lacks transfer handling | Reconcile scaled balances and avoid double counting mint/burn Pool events | Unknown live volume/access; no live collection |
| Flash loans | Old R flashLoans incompatible with updated schema naming; account flashloanCount is only mutable aggregate | Usually atomic temporary liquidity, not lasting borrower debt; no survival observations | Verify transaction-end debt changes and overlapping borrow events | Potentially high volume; no demonstrated benefit yet |
| Rate swaps | R queries swapBorrowRates but checks response$data$swaps, itself inconsistent | Stable/variable debt mode; simulator models only variable debt | Compare debt-mode changes to deployed Pool events for period | Unknown; historical source unresolved |
| Reserve parameter history | Old reserveParamsHistoryItems disabled; simulator on-chain fetcher is a placeholder/falls back to static defaults | Historical LTV/LT/bonus/caps/emode/isolation | Replay parameter-change boundary with independent historical values | No free indexed coverage established |
| User reserve snapshots | Old userReserves uses lastUpdateTimestamp; snapshots are mutable, not event history | Initial scaled supply/debt and collateral flags | Need block identity and whether snapshot precedes first replayed event | Archive historical lookup availability unknown |
| Reserve indices/rates | Not collected in core; simulator uses heuristic reserve rates and linear debt accrual | Accrual at checkpoint; affects HF and repay amount | Compare indices with historical ReserveDataUpdated and ray math | Unknown live source; offline importer available |
| Oracle history | Old priceHistoryItems disabled; simulator derives prices from transaction amountUSD/amount and cached price files | Time-correct valuation | No future backfill; distinguish transaction-derived prices from oracle rounds | Indexed/free history unverified |
| eMode / isolation | No verified complete local history | Borrowing constraints and collateral LT/price selection | Need user mode events plus historical reserve configurations | Unknown live access; not automatically enabled |

Official source checks:

- [Archived V3 ValidationLogic](https://github.com/aave/aave-v3-core/blob/master/contracts/protocol/libraries/logic/ValidationLogic.sol)
  requires HF below one and selected collateral enabled; no blanket high-HF dust exception.
- [Archived V3 LiquidationLogic](https://github.com/aave/aave-v3-core/blob/master/contracts/protocol/libraries/logic/LiquidationLogic.sol)
  selects 50% close factor above HF .95 and 100% otherwise, and uses separate debt/collateral legs.
- [Pool liquidationCall reference](https://aave.com/docs/aave-v3/smart-contracts/pool#liquidationcall)
  describes third-party execution; eligibility does not guarantee an observed liquidation.
- [Governance proposal 213](https://governance-v2.aave.com/governance/proposal/213/)
  identifies a Polygon V3.0.2 upgrade. This alone is not a block-to-implementation map for 2022–2026.
- [Graph Node sorting implementation](https://raw.githubusercontent.com/graphprotocol/graph-node/master/store/postgres/src/relational_queries.rs)
  is the basis for timestamp/ID ordering; indexer version remains unknown.

Do not use current V3 documentation or V4 dust claims as a historical Polygon specification.
A complete implementation/address/activation-block mapping, collateral bonus and protocol fee,
close-factor changes, eMode/isolation, token decimals and historical oracle values remain required.
The new offline supplementary importer preserves evidence independently; it is not a verified
live collector for these sources and does not yet enrich simulator state automatically.
