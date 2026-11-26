"""Assert the UX-SPEC §3.5 budgets on Lighthouse JSON reports (plan 002 Step 12). Stdlib only.

Usage: python3 scripts/check_lighthouse.py <dir-with-*.json>
Never loosen a threshold: a budget that is exceeded is reported with its numbers and fails the run.
"""

import json
import sys
from pathlib import Path

KB = 1000  # decimal, the stricter reading of "KB"
BUDGETS = {  # name: (audit reader, comparison, limit, unit)
    "accessibility score": (lambda r: r["categories"]["accessibility"]["score"], ">=", 0.95, ""),
    "LCP": (lambda r: r["audits"]["largest-contentful-paint"]["numericValue"] / 1000, "<=", 2.0, " s"),
    "CLS": (lambda r: r["audits"]["cumulative-layout-shift"]["numericValue"], "<=", 0.05, ""),
}
# Light-screen first-load JS is 200 KB since UX-SPEC's "Rev 3.6 budget note" (local-only edition; the
# Next 16 + React chunks alone are about 187 KB). Fonts and CSS are unchanged. Never raise without a measurement.
LIGHT_SCREEN_JS_KB = 200
TRANSFER = {"script": LIGHT_SCREEN_JS_KB, "stylesheet": 20, "font": 70}  # KB


def transfer_kb(report: dict, resource_type: str) -> float:
    items = report["audits"]["resource-summary"]["details"]["items"]
    size = next((i["transferSize"] for i in items if i["resourceType"] == resource_type), 0)
    return size / KB


def main() -> int:
    reports = sorted(Path(sys.argv[1]).glob("*.json"))
    if not reports:
        print(f"no Lighthouse reports in {sys.argv[1]}")
        return 1
    failed = False
    for path in reports:
        report = json.loads(path.read_text())
        print(f"{report['requestedUrl']}  (Lighthouse {report['lighthouseVersion']}, {report['configSettings']['formFactor']})")
        for name, (read, op, limit, unit) in BUDGETS.items():
            value = read(report)
            ok = value >= limit if op == ">=" else value <= limit
            failed |= not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: {value:.3f}{unit} (want {op} {limit}{unit})")
        for resource_type, limit_kb in TRANSFER.items():
            value = transfer_kb(report, resource_type)
            ok = value <= limit_kb
            failed |= not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {resource_type} transfer: {value:.1f} KB (want <= {limit_kb} KB)")
    print("WEB AUDIT FAILED" if failed else "WEB AUDIT OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
