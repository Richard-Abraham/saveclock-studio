"""Fail when `.claude/skills/saveclock/SKILL.md` drifts from the code it describes (plan 009).

Checked against their owners, never against retyped lists:
  (a) every command of `saveclock --help` is a row of the skill's command table, and the reverse;
  (b) every flag of a command appears in that command's row, and no other flag does;
  (c) the keyword pattern is `domain.keywords.KEYWORD_RE.pattern` character for character, and the
      count 8 is `MAX_KEYWORDS`;
  (d) every `ErrorCode` and every `ConflictReason` value appears in the error tables;
  (d2) every code in `CLI_ONLY_CODES` appears in the skill's "CLI-only codes" paragraph;
  (e) the words "never audio" and "never calls `claude`" appear;
  (f) the front matter parses and names the skill.

Prints `SKILL OK` or one line per problem and exits 1. Run through `make skill-check`.
"""

import re
import sys
from pathlib import Path

from saveclock.cli.client import CLI_ONLY_CODES
from saveclock.cli.commands import COMMANDS
from saveclock.domain.keywords import KEYWORD_RE, MAX_KEYWORDS
from saveclock.errors import ConflictReason, ErrorCode

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "saveclock" / "SKILL.md"
ROW = re.compile(r"^\|\s*`([a-z]+)(?:\s[^`]*)?`\s*\|(.*)$")


def problems(text: str) -> list[str]:
    out: list[str] = []
    front = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", front.group(1), re.MULTILINE)) if front else {}
    if meta.get("name") != "saveclock" or not meta.get("description"):
        out.append("front matter: needs `name: saveclock` and a `description`")

    rows: dict[str, str] = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m and m.group(1) in {c.name for c in COMMANDS}:
            rows[m.group(1)] = line
    for cmd in COMMANDS:
        row = rows.get(cmd.name)
        if row is None:
            out.append(f"command `{cmd.name}` is not a row of the command table")
            continue
        own = {n for names, _ in cmd.args for n in names if n.startswith("--")}
        flags_cell = row.split("|")[2] if row.count("|") >= 3 else ""  # noqa: PLR2004
        listed = set(re.findall(r"`(--[a-z][a-z-]*)`", flags_cell))
        for flag in sorted(own - listed):
            out.append(f"`{cmd.name}`: flag {flag} is missing from its row")
        for flag in sorted(listed - own):
            out.append(f"`{cmd.name}`: the row lists {flag}, which the command does not have")
    table_names = set(re.findall(r"^\|\s*`([a-z]+)[^`]*`\s*\|\s*(?:`--|none)", text, re.MULTILINE))
    for name in sorted(table_names - {c.name for c in COMMANDS}):
        out.append(f"the command table has `{name}`, which the CLI does not")

    if KEYWORD_RE.pattern not in text:
        out.append(f"keyword pattern `{KEYWORD_RE.pattern}` is not in the skill (exactly)")
    for found in re.findall(r"`(\^\[a-z\][^`]*)`", text):
        if found != KEYWORD_RE.pattern:
            out.append(f"the skill quotes a keyword pattern that differs from the code: {found}")
    if f"at most {MAX_KEYWORDS}" not in text:
        out.append(f"the skill must say `at most {MAX_KEYWORDS}` (MAX_KEYWORDS)")

    for code in ErrorCode:
        if f"| `{code.value}` |" not in text:
            out.append(f"error code `{code.value}` has no row in the error table")
    for reason in ConflictReason:
        if f"| `{reason.value}` |" not in text:
            out.append(f"conflict reason `{reason.value}` has no row in the reason table")

    para = re.search(r"^CLI-only codes:.*?(?:\n\n|\Z)", text, re.DOTALL | re.MULTILINE)
    for code in CLI_ONLY_CODES:
        if f"`{code}`" not in (para.group(0) if para else ""):
            out.append(f"CLI-only code `{code}` is not in the skill's CLI-only codes paragraph")

    for phrase in ("never audio", "never calls `claude`"):
        if not re.search(re.escape(phrase), text, re.IGNORECASE):
            out.append(f"the skill must say {phrase!r}")
    return out


def main() -> int:
    if not SKILL.is_file():
        print(f"SKILL CHECK FAILED: {SKILL} does not exist")
        return 1
    found = problems(SKILL.read_text())
    for line in found:
        print(f"SKILL CHECK FAILED: {line}")
    if found:
        return 1
    print("SKILL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
