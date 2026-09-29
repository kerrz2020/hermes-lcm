---
name: hermes-lcm
description: Use, configure, diagnose, and retrieve exact evidence with the Hermes-LCM lossless context plugin.
---

# Hermes-LCM

Use this skill when a task concerns Hermes-LCM setup, operation, compaction, diagnostics, session behavior, or recall from compacted and cross-conversation history.

Start here:

1. Confirm that the `hermes-lcm` plugin is enabled and `context.engine` is `lcm`.
2. For exact historical claims, use the recall workflow instead of trusting a compacted summary.
3. Use `lcm_status`, `lcm_inspect`, and `lcm_doctor` before changing configuration or attempting repair.
4. Treat slash-command apply paths as mutations: preview first, keep backups, and require the user's authorization.
5. Load the relevant reference rather than guessing arguments or lifecycle semantics.

Reference map:

- Configuration and activation: `references/configuration.md`
- Architecture and data ownership: `references/architecture.md`
- Diagnostics and safe operator workflow: `references/diagnostics.md`
- Recall tools and routing: `references/recall-tools.md`
- `/new`, session continuity, and `/lcm rotate`: `references/session-lifecycle.md`
- Canonical runtime recall policy: `references/recall-policy.md`
- Temporal rollups, forced builds, and end-to-end proof: `references/e2e-rollup.md`

Working rules:

- Raw stored messages are authoritative; summaries are bounded recall cues.
- Prefer newer source-backed evidence when it conflicts with an older summary.
- Start with the narrowest useful scope and expand only when exact detail is needed.
- Do not infer exact commands, paths, timestamps, values, counts, or causal chains from summaries alone.
- Keep current-session, cross-conversation, and Hermes history outside `lcm.db` distinct.
- Do not treat open-cardinality results as complete without product-verifiable enumeration or coverage.
- Use `lcm_compile_evidence` when a historical answer needs several named facets, exact operands, conflict handling, or latest-state selection; treat its semantic proposal as untrusted until the product returns validated evidence.
- Keep default-off assertion, query-view, adaptive-retrieval, and destructive operator paths default-off unless the user explicitly asks to enable them.
- Before acting on a corruption verdict, reproduce it on a fresh read-only connection and against a copy of `lcm.db`: a long-lived engine connection can answer `PRAGMA integrity_check` with `fts5: corruption found reading blob N` for an FTS5 segment that no longer exists on disk. Rebuildable FTS indexes never justify a restore; only a verdict that reproduces from a fresh connection does.
- Verified 2026-09-29 on this box: the doctor's file checks run on dedicated short-lived connections (plugin fork commit `ee5909f`), and the phantom verdict cleared on gateway restart.
- The plugin loads into the running gateway process: a code fix reaches the live engine only after a gateway restart, and the terminal tool refuses to restart the gateway from inside it — ask the user to run `hermes gateway restart` in a separate shell, then re-run `lcm_doctor` to confirm.
- Running the plugin's own test suite needs `umask 022` and a private `TMPDIR`; otherwise the private-artifact guard refuses the group-writable pytest sandbox and the benchmark/stress tests fail spuriously.
