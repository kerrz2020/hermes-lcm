# Diagnostics

Use read-only product tools before changing configuration or running an apply path.

## Fast path

1. `hermes plugins`: confirm `hermes-lcm` is enabled and the selected context engine is `lcm`.
2. Send one normal message if the session has not been bound since restart.
3. `lcm_status`: inspect runtime identity, database path, context pressure, summary/store counts, filters, and lifecycle state.
4. `lcm_inspect`: inspect current-session lineage, frontiers, fresh tail, externalized-ref readability, and skip/no-op reasons without retrieving content.
5. `lcm_doctor`: run database, FTS, lifecycle, configuration, and context-pressure diagnostics.

If optional slash commands are enabled, `/lcm status` and `/lcm doctor` expose the corresponding operator views.

## Running the test suite locally

The suite builds SQLite stores under `TMPDIR`, and the private-artifact guard refuses any database whose parent directory is group- or world-writable. On a box with a permissive umask the benchmark, stress and ingest tests therefore fail with `PermissionError: refusing SQLite artifact 'lcm.db': parent directory is writable by another user` — that is the guard doing its job, not a regression:

    umask 022; TMPDIR=$(mktemp -d) python -m pytest tests/ -q

Two ingest tests (`test_import_lossless_claw_externalizes_legacy_data_uri_content`, `test_import_lossless_claw_respects_externalization_path_env`) fail on unmodified `v1.0.0-rc.1` as well.

## Reading integrity verdicts

`database_integrity` and `sqlite_storage` answer for the database FILE, from a dedicated short-lived connection. A long-lived engine connection can hold an FTS5 segment view from before an index merge and answer `PRAGMA integrity_check` with `fts5: corruption found reading blob N`, naming a segment that no longer exists on disk. In that case the file checks stay healthy and `engine_connection_integrity_view` reports the drift instead: restart Hermes to rebind, do not restore from backup.

Before acting on any corruption claim, reproduce it: run `pragma quick_check` on a fresh read-only connection and against a copy of `lcm.db*`. FTS indexes are rebuildable (`/lcm doctor repair`); only a verdict that reproduces on a fresh connection justifies restore.

## Empty lifecycle rows

`lifecycle_fragmentation` warns about rows whose both referenced session IDs hold zero messages and zero summary nodes — nothing was lost, the row is residue from a gateway restart, ephemeral cron tick, or crash-loop.

Two gated paths clean them, and both must run inside the gateway (a second process opening `lcm.db` just re-creates the multi-writer problem):

- Automatic: `empty_lifecycle_gc_enabled` (default true) prunes on session bind, but only when the table exceeds `empty_lifecycle_gc_threshold` (default **200**) and the row is older than `empty_lifecycle_gc_max_age_hours` (default 24). A table of a few dozen rows therefore never gets collected; `LCM_EMPTY_LIFECYCLE_GC_THRESHOLD` is the knob to lower.
- One-shot: `/lcm doctor clean lifecycle apply` takes its own backup and deletes every eligible row regardless of age. Gated by `LCM_DOCTOR_CLEAN_APPLY_ENABLED`; enable it for the cleanup, then remove it.

Measured on a 48-row table with 31 empty rows: bind-time GC took 17, leaving 14 too young for the age floor. Read-only preview (`/lcm doctor clean lifecycle`) prints the counts first.

## Safe mutation order

For cleanup, repair, source normalization, or rotate:

1. run the read-only preview;
2. inspect exact candidates and paths;
3. create/confirm a backup;
4. obtain user authorization for the specific apply operation;
5. run one bounded apply and verify integrity afterward.

Cleanup apply is separately feature-gated. Never infer permission to enable it from a diagnosis request.

## Purging `.corrupt*` archives

`~/.hermes/lcm.db.corrupt*` / `.bak-*` are the recovery path from past corruption events, so they must stay out of routine cleanup. Before deleting any on user request:

1. Skip deletion if a process holds the files (`fuser -v ~/.hermes/lcm.db.corrupt*`).
2. Open each readable archive read-only and compare `select distinct session_id from messages` against the live DB; a corrupt archive may still hold one session the live DB never reingested.
3. Salvage any unique session to `~/.hermes/lcm-archive-salvage/<session_id>.jsonl` (rows as JSON per line).
4. `rm -f ~/.hermes/lcm.db.corrupt*`, then re-check the live DB (`pragma quick_check`, message count) is untouched.

In the incident this runbook came from, readable archives held fewer messages than the live DB; unreadable ones (`file is not a database`, malformed) are unsalvageable.

## Common states

- `/lcm` answers `Unknown command /lcm`: the plugin registers the slash surface only when `LCM_ENABLE_SLASH_COMMAND` is truthy, and it is **default off**. Confirm from `gateway.log` — the plugin logs `LCM slash command registration disabled (set LCM_ENABLE_SLASH_COMMAND=1 to enable /lcm)` at load, or `... registration unavailable on this Hermes host` when `ctx.register_command` is missing. The env var is read once at plugin load, so the flag needs a gateway restart.
- Unbound status after restart: send a normal message, then check again.
- Database exists but stays empty: verify plugin enablement, `context.engine`, profile, database path, and ignore/stateless patterns.
- Weak exact recall: verify source rows exist, query construction/scope is correct, summary health is sound, and embedding coverage/provenance matches the requested mode.
- Conflicting summary and raw evidence: prefer the newer exact raw evidence and inspect lineage.
- Path B/context-engine schema log: expected on hosts where plugin-registry handlers do not receive active messages; context-engine schemas and dispatch remain the healthy route.
