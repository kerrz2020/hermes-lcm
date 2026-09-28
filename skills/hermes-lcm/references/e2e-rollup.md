# End-to-end test: temporal rollups

Prove the whole chain, not just that the tables exist: **node published → invalidation
recorded → maintenance builds → `lcm_recent` serves the rollup instead of falling back to
leaf summaries.**

## Why you cannot just wait after enabling

Rollup rows are created by mutation triggers when a summary node is published. Nodes that
were published **before** the rollup tables existed leave no invalidation behind, so
enabling `LCM_TEMPORAL_ROLLUPS_ENABLED=true` never backfills history. After a fresh enable,
the tables legitimately stay empty until the next compaction publishes a node. Empty is not
a failure; check the trigger path, not the DB, before concluding anything.

## Forcing a build

Three routes, in increasing intrusiveness:

1. **Operator command (preferred).** `/lcm rollups rebuild <day|week|month|all> [YYYY-MM-DD]`.
   It seeds a durable `stale` row for every requested target *before* applying the
   per-pass budget, so targets beyond `rollup_builds_per_pass` stay `stale` rather than
   disappearing. Scope is the current session; a busy operator lease is reported as busy.
2. **Normal path.** Publish a summary node (let a compaction run), then let the scheduled
   maintenance pass drain the invalidation outbox.
3. **In-process harness on a copy** — for a DB that must not be written, or to build
   history the triggers never saw. Copy with `sqlite3.Connection.backup` from a `mode=ro`
   source (`cp` of a live DB + sidecars yields an inconsistent snapshot and false
   `malformed` reports), then drive the real code against the copy:
   `SummaryDAG(path)` → `dag.add_node(...)` → `run_rollup_maintenance(dag, config, scope)`
   → `lcm_recent({...}, engine=<shim>)`. The shim needs `_dag`, `_config`,
   `current_session_id`, `_summary_circuit_breaker`, `_summary_spend_guard`, plus
   `try_acquire_rollup_operator_lease` (the scheduler's in-process lease is not reachable
   from a bare script).

A small harness that runs all three against **copies of real databases** (backup-API snapshot, never
the live file) and prints `PASS n | FAIL n` is the fastest proof that the feature works on a given
host: copy a store that already has a `ready` rollup, replay the publish → maintenance → serve chain,
then drive the operator command on a copy of a store with none.

## What a passing run proves

- `lcm_rollups` has the `day` row at `status=ready` for the target period.
- `lcm_rollup_sources` has provenance rows; `lcm_rollup_invalidations` drained to zero.
- Aggregates cascade: building `day` marks `week`/`month` stale and a following pass
  promotes them to `ready`.
- `lcm_recent(period="date:<day>")` returns `mode: "rollup"` with
  `provenance.fallback: false` — a served rollup, not a leaf-summary fallback.
- `pragma quick_check` stays `ok` and the write path leaves zero deleted sidecar fds.

## Reading failures

- **`LCM background temporal rollup maintenance failed`** can be a *canary*, not a rollup
  bug: this worker opens its own `SummaryDAG` connection, so it is often the first caller
  to hit `run_versioned_migrations` on a sick DB and to report
  `database disk image is malformed` from `set_schema_version`. Fix the database.
- **Aux summarizer timeout** (60 s per attempt, no fallback chain) does not fail a build:
  the pass degrades to deterministic truncation and the row still reaches `ready`. Content
  can be shorter than the token target — inspect `token_count` before blaming the rollup.
- **`building` or `failed` left behind** means a maintenance pass died mid-flight — a
  graceful `/restart` landing during compaction is the usual cause. The lease is reclaimed
  only inside `run_rollup_maintenance()`, which the engine schedules on session **bind**,
  so the cure is a new session (`/new`), not time and not the operator lever:
  `upsert_stale_many` deliberately leaves an in-flight `building` row alone, so
  `/lcm rollups rebuild` cannot clear it. `lcm_recent` stays correct meanwhile (leaf
  fallback) and a later pass rebuilds and bumps `generation` unattended.
- **Operator command never runs** while the plugin's scheduler holds the lease: it is
  skipped in-process and reports busy rather than fighting the background worker.

## Limits

The harness exercises the plugin's own store/builder/DAG code paths on a copy; it does not
prove the live gateway's scheduler timing, nor that a *future* node will arrive. Confirm
production behaviour separately with a live `lcm_recent` call — the serve path is the one
that matters.
