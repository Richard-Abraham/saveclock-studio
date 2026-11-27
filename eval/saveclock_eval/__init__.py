"""The G2 evidence tooling (plan 009): metrics, per-render checks, results table, review sheets.

One script (`eval/run_eval.py`) drives it against a running API. Nothing here starts a stack or
touches a database; the only application import is `saveclock.config` / `saveclock.cli.waits`
(the time budgets), so a wait cannot give up before the server's own limit.
"""
