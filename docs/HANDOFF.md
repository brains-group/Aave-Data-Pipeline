# Shared Aave pipeline and simulator revision work

Status: implemented local integration and targeted fixes; bounded offline diagnostic complete.
No authenticated collection requests. Full historical validation and parity remain incomplete.

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

## Implemented and installed

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

The initial installation passed 23 shared-package Python tests, six simulator tests and one consumer repayment test; updated checks are recorded below.
Installable-package smoke build/install used --no-index --no-deps --no-build-isolation
in /tmp. Journal formatter smoke created all 25 pair exports on a deterministic fixture.
A new corrected feature view fixes its schema to all five core types even in a short
prefix; R-parity retains the observed-type schema and optional original raw event fields.
Neither view joins mutable account totals. Unused model/ROSE helpers are not ported.
Source R preprocessing includes optional exogenous variants; those remain deferred.

## Installed work and bounded diagnostic (2026-09-09)

The shared repository is installed at `/home/spadef/Aave-Data-Pipeline`, with real gitlinks
in **both craft-soc and Aave-Action-Recommender**. Its source URL is local and absolute;
no remote was invented or published. See PIPELINE.md in either consumer for setup.
Initial source commits: pipeline e8a3e621e3ce55ab7e404c53e50510fb94e0a5fb;
simulator b9d402c1a74d17dfd3014553425626f99e9038d1. Later source updates are identified
by Git history and the consumers' gitlinks; use the revision commands below.
Original dirty files remain outside the integration commits. No cache was moved.

Additional fixes: profiles with unverified liquidation debt/collateral legs retain an
observed-only label instead of fabricated USDC collateral. Replay helpers explicitly
report failure for these incomplete events. The generic replay helper now attempts
past liquidation state updates instead of silently ignoring every liquidation, and
records execution success. Its execution still uses simulator rules, not an independently
reconstructed exact historical seizure. Existing old profiles are not silently repaired.
A separate enrichment adapter converts debt and seized collateral with their own decimals
and joins explicit log identities; supplementary data never enters survival observations.

Profile discovery now compares overlapping sources before deduplication and rejects
conflicting state/transactions. There are 13,998 files in liquidated_profiles and 189,655
in non_liquidated_profiles, with 13,990 overlapping filenames: 189,663 distinct filenames,
not 203,653 unique accounts. Five inspected overlaps differ only in description; the
remaining overlapping content has not all been compared. Folder membership is not an
outcome label: the nominally non-liquidated directory also contains liquidation events.

### Same-cohort replay

Ten unique accounts, 393 recorded transaction checkpoints, 11 observed liquidations,
382 other actions. Frozen source hashes and paths: docs/replay-cohort.json in the shared
repository or docs/revision-evidence/replay-cohort.json in the simulator. Selection:
deterministic filename-hash order, five from each source folder, 10–200 transactions,
positive-folder profiles required to contain liquidation. This is a bounded diagnostic,
not a representative sample of all borrowers or a tuned/held-out policy study.
The old/fixed comparison uses be8a6f7 versus b9d402c and identical input/capital assumptions.

| Funding | Logic | TP | FP | TN | FN | Precision | Recall | FPR | Failed actions | Zero-debt positive events |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Existing profile wallet | Old | 3 | 10 | 372 | 8 | 23.08% | 27.27% | 2.62% | 106 | 6 |
| Existing profile wallet | Fixed | 1 | 7 | 375 | 10 | 12.50% | 9.09% | 1.83% | 116 | 6 |
| Retrospective minimum wallet | Old | 1 | 7 | 375 | 10 | 12.50% | 9.09% | 1.83% | 34 | 0 |
| Retrospective minimum wallet | Fixed | 0 | 6 | 376 | 11 | 0% | 0% | 1.57% | 48 | 0 |

No detection improvement demonstrated. FNR is 1-recall. All failed histories retained;
no price exclusions in these runs. Negative cases are non-liquidation recorded actions,
not verified healthy states. This compares warnings with execution labels at transaction
time, not a future prediction horizon; warning lead time is not established.
Replay begins with empty positions, static synthetic reserve defaults, 1e9 reserve liquidity,
transaction-derived cached as-of prices and timestamp-only ordering. Liquidators receive
explicit synthetic funding in this diagnostic. Existing wallets and retrospective minimum
wallets both use future-derived capital information; neither establishes feasible earlier
recommendation capital. Funding eliminated the six zero-debt positives, demonstrating why
these cases must be investigated before exclusion. No direct RPC or supplementary enrichment
was used; old/enriched-data comparison remains blocked by missing historical evidence.

Portable summary includes static/dynamic margins and representative FP/FN traces with
prices, balances, prior failures and source hashes. Full 393-row traces and logs remain in
`/home/spadef/.codex/sessions/2026/09/08/aave-work/replay-*.json` outside source Git.
For one FN, a prior deposit failed because 4,499.090967 USDC was required and only
3,897.208532 was available. First divergence from independent on-chain state is unknown.
No threshold was tuned to match these labels. The later helper/coverage fixes do not enter
this direct-protocol harness; the measured logic version above is explicitly frozen.

### Additional manuscript lineage

The 69.11% claim traces to analyze_simulation_results.py's eventual-risk calculation,
not a standalone fixed-horizon Cox evaluation. Existing HF-only statistics give TP=157,
FP=533, FN=974, approximate TN=3,217; (157+3217)/4882=69.1110%. The matrix sums to
4,881 because one at-risk profile has no future transactions, while the accuracy denominator
includes all 4,882. TN assumes no recorded future liquidation means safe. Derived precision
is 22.75%, recall 13.88%; these are audit calculations, not newly trained predictive results.
The 25 journal pair CSVs total about 44.48 GiB; 21.8M record/90-feature lineage remains
unresolved and no full row count was substituted for it.
The HF-only result retains 1,470 rescues / 1,693 baseline cases, but filters based on either
arm's detection type. The unfiltered statistics report 75 worsened profiles. Zero worsening
therefore describes an outcome-conditioned subset. 8,400-to-5,078 initial reduction remains
unreconciled. Paired replay assumes later recorded actions remain feasible after intervention;
failures and funding sensitivity prevent a causal real-world interpretation.

### Checks and remaining work

Python validation only after the user's R steering. Shared suite: 24 tests; simulator:
9 distinct tests; consumer repayment: one test. Installed consumer imports and collection
help work from outside their roots. Full R/Python parity, optional exogenous feature variants,
full-scale formatting, deployment/activation-block mapping, historical indices/oracles and
close-factor/bonus/fees remain unfinished. No current account free quota is verified;
zero authenticated collection requests were made. The five historical missing borrow IDs
and one missing liquidation ID remain unresolved without mixing source provenance.

No paper, cover letter, figure or bibliography was edited. The requested archive was not
located; the local source remains provisional. `changes.sty` is unavailable in the local
TeX search path, and neither marked nor clean builds have been verified. Future manuscript
edits must reuse changes markup. Response notes: distinguish positive-event detection from
accuracy; explain duplicate profiles, funding failures, outcome-conditioned exclusions and
shared reconstruction truth; rerun before revising claims. No reviewer concern is resolved
by these fixtures or this small diagnostic. Broad policy/model comparisons remain later work.

### Reproduction commands

From either consumer, initialize the local source and install:
```bash
git -c protocol.file.allow=always submodule update --init --recursive
python -m pip install --no-deps --no-build-isolation -e ./Aave-Data-Pipeline
git submodule status
python collect_aave.py --help
python -m aave_data_pipeline.audit --help
python -m unittest discover -s Aave-Data-Pipeline/tests -v
```
The shared README documents the bounded collection and survival formatting commands;
collection defaults to zero HTTP requests. No writer should share the cache with an active
collector. To inspect recorded revisions: `git -C Aave-Data-Pipeline rev-parse HEAD` and,
in the journal consumer, `git -C Aave-Simulator rev-parse HEAD`.

From the simulator root, using a new output path:
```bash
PYTHONPATH=. python -m unittest discover -s tests -p test_revision.py -v
PYTHONPATH=. python tools/bounded_replay.py \
  --cohort docs/revision-evidence/replay-cohort.json \
  --prices data/reserves/price_history.json \
  --revision "$(git rev-parse HEAD)" --funding profile \
  --output /tmp/aave-diagnostic-new.json
```
Repeat with `--funding retrospective_minimum` and a different output path. The harness
checks frozen profile hashes and rejects duplicate accounts or existing outputs. To run
old logic, extract `git archive be8a6f7` to a separate temporary directory and run this same
harness with PYTHONPATH pointing at that directory and an absolute price/cohort path.
No original simulation cache or paper result should be overwritten.
