# Shared cache and optional indexed simulator data

Both consumers use /home/spadef/data/craft-soc/data. The old collection subtree
will be moved to its .cache/data_collection directory, with a compatibility symlink
back from craft-soc/codes/cache/data_collection. Migration checks every file hash
and SQLite quick_check, refusing active collectors/cache handles. Other model caches
are not moved. The migration receipt records the exact verified files and revisions.

The serving Polygon deployment QmZvndp7kSUaMZo3W21bLyggU8wpcYG5LXBbGvu21t4cvD
was checked with one authenticated request after the user confirmed unused free capacity.
Block 93512896, indexed timestamp 1788974377, no reported indexing errors.
Supported optional sources: transfers, flashloans, positionSnapshots. The other
candidate histories are unavailable on this deployment; no empty-complete history
is substituted. The schema response is cached for reuse.

27 offline tests pass, including source-schema validation, shared-lock exclusion,
output-derived cache paths and supplementary resume with zero repeated queries.
Existing collector tie-pagination, retries, interval and restart tests remain intact.

Bulk download awaits a numeric free-request allowance. No paid access was enabled.
Use --supplementary-only to avoid refreshing core/account snapshots; use
--include-supplementary to collect extras alongside core exports. Both require the
existing bounded request budget and free-access confirmation. See README.md.
