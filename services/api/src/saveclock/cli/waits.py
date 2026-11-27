"""How long each waiting command waits, derived from the budgets in `saveclock.config`.

A wait must outlast the server's own limit, or the CLI would give up on a normal job: the
numbers are never copied here (a test asserts each is strictly greater than its limit).
"""

import time

from saveclock.config import ANALYZE_LIMIT_S, DRAFT_LIMIT_S, REMUX_LIMIT_S, RENDER_LIMIT_S

WAIT_DRAFT_S = ANALYZE_LIMIT_S + DRAFT_LIMIT_S + 120  # upload accepted -> draft
WAIT_REPLAN_S = DRAFT_LIMIT_S + 60  # keywords set -> draft again
WAIT_RENDER_S = RENDER_LIMIT_S + 60
WAIT_MODE_A_S = REMUX_LIMIT_S + 60
WAIT_WATCH_S = max(WAIT_DRAFT_S, WAIT_RENDER_S)  # `status --watch` follows any of them
POLL_S = 1.0

# Indirection so tests can run a whole wait without sleeping.
sleep = time.sleep
now = time.monotonic
