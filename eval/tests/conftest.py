"""Put `eval/` on the path so `saveclock_eval` imports without being installed."""

import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
REPO = EVAL_DIR.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
