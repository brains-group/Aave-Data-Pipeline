# Shared Aave pipeline and simulator revision work

Status: in progress. No collection HTTP requests made. No historical result reproduced yet.

## Baseline

Source/asset snapshots and SHA256 manifest: `baseline/manifest.json` (492 files).
Original repos: craft-soc 04f5043510ae0ea4d735aab33f9ea671be3b886e;
recommender 68b51b921b45b4c80e7c8cc81c4c6854e85f29f4;
simulator submodule be8a6f7bf66153ecc03b8c1f048fdcafb66a60e1;
benchmark c0500e7092b3343106b9a706634e3f9a7b275c02;
R collector e74d8cc8c2641262f69c430ade2c0de464a40c2a.
Collector and datasets.py were untracked; other craft-soc changes preexist.
R reference feature/split/creation scripts contain preexisting edits.
No applicable AGENTS.md found in targeted trees/ancestor locations.
Correct journal ZIP not found in workspace, /tmp, or journal repo; local paper,
all reviews, cover letter and PDF exist. Local source is provisional baseline;
archive identity remains unverified. No manuscript changes so far.

## Plan

1. Extract existing collector, preserve cache namespace/config and wrappers; request budgets and offline audit.
2. Port active feature, label, split and preprocessing chain, with explicit parity/corrected semantics and tasks.
3. Target simulator accounting and warning/execution separation; fixtures and bounded historical evaluation.
4. Install sibling repository and actual local submodules in both consumers; commit only task files.
5. Document evidence, reviewer status, exact commands and unresolved historical/deployment provenance.

## Findings

- Existing 14 offline collector tests passed with approved log writes; extracted copy passes all 14.
- Actual cache: craft-soc/codes/cache/data_collection/aave_v3/polygon/5a19507ddc6a0f4b/raw.sqlite3.
  Config resolves CACHE_DIR relative to codes/config.json. Outputs go to /home/spadef/data/craft-soc/data.
  Cache is ~3.85GB at initial inspection, contains completed borrow intervals and unfinished deposits.
  Original cache never opened writable by this work. Process visibility inside sandbox is restricted.
- Historical borrow comparison files remain untouched. Five missing IDs unresolved; live absence is historical evidence only.
- The Graph advertises 100k monthly free queries (https://thegraph.com/studio-pricing/).
  Account remaining allowance and disabled paid overage unknown: no live collection authorized by capacity evidence.
- R self-transitions subtract one second; comment claims forward. Split helper ignores subjects argument.
  Account-liquidated alias rows constructed in basicTransactions but labels built from transactions.
- Simulator liquidate defaults to permitting HF up to 1.10, lacks close-factor/debt cap and liquidator funding checks.
- Wallet inference tracks maximum post-action balance, not cumulative funding deficits; liquidation incorrectly debits external wallet.
- Recommender data symlinks to ../actionAgent/data, profiles to /data/.../Polygon/aave-simulator.
- Local active cohort code differs from paper's commented 300-per-pair sampling implementation.

## Reviews

Revision invitation: major revision/re-review due 18-Oct-2026, Create a Revision; no submission/contact authorized.
R1 assumptions/sensitivity: under investigation; R1 representative cohort: pending bounded validation.
R2 assumptions/validation: under investigation. Neither concern resolved.
Later phase: HF-buffer/repay-only/deposit-only/automation baselines; broader agent evaluation;
precision/recall/AUC/calibration/survival metrics; costs; novelty/risk metrics; figures/references/claims.
Return period two-day example violates seven-day horizon lower bound; inspect implemented horizon.
Distance-group binary search needs monotonicity verification before minimum-perturbation claims.

## Measured results and updated findings

- User steering: prioritize Python; do not spend time setting up/debugging R tests. No R parity
  experiments run. Existing RDS labels read with pyreadr: Borrow/Account Liquidated/y_test.rds,
  102,710 rows, five columns; IDs are 66-character hashes unlike current extended event IDs.
  Original output lineage must be resolved before asserting representative parity.
- Fresh read-only cache audit: borrows 1,429,516; deposits 3,603,688; withdraws 3,480,814;
  repays 1,332,588; liquidates 50,627. 1,692 jobs. All five core event intervals complete
  through exclusive 1788897090; old redundant unfinished borrow job remains preserved.
- Resume check copied real job metadata and one payload per entity into a temporary cache:
  all five completed ranges reused with zero client calls. This is not a full export test.
- Historical transaction CSV totals freshly counted: 8,837,439 = 1,281,755 borrow +
  3,224,319 deposit + 3,108,933 withdraw + 1,183,409 repay + 39,023 liquidation.
  Historical liquidation unique IDs: 39,023; cache matches 39,022; one missing at
  1754168802 (ID in liquidation-comparison-missing.csv). Cause unresolved; no rows inserted.
  Five missing borrow IDs remain historical evidence; no new authenticated lookup attempted.
- Actual recommender data is the ../actionAgent/data symlink; transaction CSV is 2,239,447,906
  bytes, consistent with historical source size, but content equality has not been hashed.
- Journal pair CSV has 92 columns including task/label fields, no event ID. The phrase
  "90 engineered features" is not reconciled with model inputs and dropped identifiers.
- Historical statistics files reproduce manuscript headline counts ONLY in the HF-only filter:
  cache/statistics/simulation_statistics_hf_only_20260306_120247.json:
  4,882 processed, 1,693 baseline detections, 1,470 improvements, 223 intervention detections,
  zero worsening. Corresponding unfiltered 20260306_120246: 5,078 processed, 1,814 baseline,
  1,559 improvements, 75 worsening; no-dust: 5,021 processed, 1,517 improvements, 64 worsening.
  performSimulations.py around 1648 excludes based on detected reason in EITHER arm.
  Thus the zero-worsening statement is conditional on outcome-dependent filtering.
  86 delayed detections / 223 remaining = 38.57%; (1470+86)/1693 = 91.91%.
- The exact path from 8,400 checkpoints to 5,078 processed cases still needs an ID-based
  exclusion ledger. Current get_train_set implementation differs from commented paper-era
  300-per-pair sampling code. It targets 500-per-pair but does not update event_pair_counts.
- Validation "actual" states are state_after_heldout from the SAME simulator execution,
  tools/validate_simulator.py around 2154–2165. This is not independent on-chain ground truth.
- Liquidation-focused split includes first liquidation in both sets in baseline. Fixed boundary.
  Zero-prefix state extraction now refuses to substitute future end state.
- simulator/utils.py execute_transaction treats Liquidated as no-op, whereas
  tools/run_single_simulation.py calls liquidate and grants liquidator funding.
  These are materially different replay paths. Historical replay fidelity is not established.
- Representative inspected liquidated profile has an initial collateral value matching its
  first deposit and an initial-state timestamp equal to that deposit. Whether state is pre/post
  is unclear; do not replay it as independently verified pre-state.
- run_single_simulation ignores profile initial_collateral/debt and starts from funded wallets.
  get_limited_user_profile truncates at recommendation timestamp minus 600 seconds and sets
  lookahead to twice the remaining recorded span. This differs from a fixed seven-day horizon.
- Sensitivity code explicitly assumes distance-group monotonicity and returns no-change if
  the most distant group does not flip. No proof supplied; minimum-distance claim unverified.

## Implemented (staged before installation)

Shared installable package extracted from collector. Preserves chronological/cache fixes and
adds explicit HTTP attempt budget (zero by default), caller config/env/log paths, requested
vs indexed manifest coverage, and normalized block/log/transaction/asset metadata.
Pure read-only cache audit; offline supplementary importer with independent chain/source
provenance and conflict checks; no live supplementary adapters yet.
Active core feature/label/split primitives ported; explicit benchmark/journal matrices,
R-parity vs corrected semantics, CSV/RDS input and CSV outputs, training-only preprocessing.
Original full R output parity, optional exogenous variants and full-scale memory/performance
validation are unfinished. No model redesign or new model results.

Simulator: strict HF default in liquidate, positive finite action amounts, debt cap and
liquidator funding checks, borrow LTV capacity, withdrawal amount/liquidity rejection,
corrected funding-deficit inference with as_of cutoff and no seized-collateral wallet debit,
no USD-as-token fallback. Close factor/bonus/fee/version mapping remains unfinished.
Common checkpoint evaluation interface separates observed labels from warnings and provides
negative cases/confusion counts, precision/recall/FPR/FNR and lead time, plus absolute/relative
state errors. No historical accuracy improvement is claimed.
Recommender: same-asset repayment cap using newly captured pre-projection checkpoint;
old cache results cannot fund recommendations; new simulation caches isolated; new survival
manifest isolates model/data caches; stable observation/outcome/split metadata dropped from
predictors. Profile initial-wallet inference can still use full future history: old profiles
are not silently regenerated and explicit funding ablations remain required.

## Reviewer evidence/action/status

| Request | Evidence/action | Status |
|---|---|---|
| R1 simulator assumptions/sensitivity; R2 limitations | Accounting/split fixes + fixtures; documented unverified rates, prices, histories and funding | Partial; historical ablations pending |
| R1 representative cohort; R2 diverse validation | Existing cohort and outcome-dependent filtering audited | Unresolved; representative evaluation pending |
| R1 simple HF/repay/deposit/automation baselines; R2 comparisons | Common evaluation config and checkpoint metrics added | Later policy phase |
| R1 predictive metrics | Keep simulator detection, Cox prediction and paired outcomes separate | AUC/calibration/survival metrics and target/horizon reconciliation pending |
| R1 costs | Existing replay assumes inferred capital; conversion bug corrected | Historical gas/latency/cost evaluation pending |
| R2 novelty/risk justification | Return-period horizon bound and nonmonotone sensitivity search identified | Later methodological phase |
| Both presentation/claims | Exact source counts and outcome-dependent HF-only filtering documented | No paper text edited; tracked revision and builds pending evidence |

## Manuscript

No manuscript or cover-letter edits, no figures replaced, no result numbers changed.
Untouched baseline paper/figures/bibliography/reviews/cover letter are in baseline snapshot.
Correct ZIP still unavailable in inspected locations; local source chosen provisionally.
Later edits must use existing changes package, preserve originals, build draft and final.
Response notes should explain detection fractions among positives, shared reconstruction
"ground truth", outcome-conditioned filtering, unresolved cohort lineage and required reruns.
No reviewer concern is marked resolved based solely on unit tests.

## Current checks

23 shared-package Python tests, six simulator tests and one consumer repayment test pass.
Installable-package smoke build/install used --no-index --no-deps --no-build-isolation
in /tmp. Journal formatter smoke created all 25 pair exports on a deterministic fixture.
A new corrected feature view fixes its schema to all five core types even in a short
prefix; R-parity retains the observed-type schema and optional original raw event fields.
Neither view joins mutable account totals. Unused model/ROSE helpers are not ported.
Source R preprocessing includes optional exogenous variants; those remain deferred.
