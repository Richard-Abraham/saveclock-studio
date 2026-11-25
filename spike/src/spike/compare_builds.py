"""Compare two ``g0-render/1`` result sets (Step 6 screen; G0-20, G0-21, G0-23, G0-24).

``python -I -m spike.compare_builds --a render-8.1.3.json --b render-9.0.x.json [--c same-encoder.json]``

Encoder-independent rows (frame count + per-frame PTS/duration hash, cut positions, 20/20 with
output sanity, remux A/V offsets) are PASS/FAIL. Encoder-dependent rows (video packet hash, render
p95 speed) are PASS/FAIL only when both builds used the same ``vcodec``; otherwise they print
``N/A`` (never PASS). ``--c`` adds a same-encoder comparison of ``--a`` against a third result set.
Exit 1 if any row is FAIL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "g0-render/1"
SPEED_LIMIT = 1.10
Row = tuple[str, str, str]  # (gate, status, detail)


def load(path: Path) -> dict[str, Any]:
    d: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema {d.get('schema')!r} != {SCHEMA!r}")
    return d


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows}


def _checks_ok(rec: dict[str, Any], prefix: str) -> bool:
    cs = [c for c in rec["verify"]["checks"] if c["name"].startswith(prefix)]
    return bool(cs) and all(c["ok"] for c in cs)


def _p95(d: dict[str, Any]) -> float | None:
    try:
        return float(d["bench"]["render"]["render_s"]["p95_s"])
    except (KeyError, TypeError):
        return None


def _na(a: dict[str, Any], b: dict[str, Any]) -> str:
    return (
        f"different encoders ({a['ffmpeg']['vcodec']} vs {b['ffmpeg']['vcodec']}), "
        "deferred to Step 12 identical-configure source builds"
    )


def compare(a: dict[str, Any], b: dict[str, Any]) -> list[Row]:
    ra, rb = _by_id(a["renders"]), _by_id(b["renders"])
    ids = sorted(set(ra) | set(rb))
    same_enc = a["ffmpeg"]["vcodec"] == b["ffmpeg"]["vcodec"]
    rows: list[Row] = []
    if set(ra) != set(rb) or not ids:
        rows.append(("G0-21", "FAIL", f"case sets differ: {sorted(set(ra) ^ set(rb))}"))
        return rows
    both = [(ra[i], rb[i]) for i in ids]

    # G0-20: 20/20 + QM-077 sanity on both builds
    def g20(d: dict[str, Any], rs: dict[str, dict[str, Any]]) -> bool:
        s = d["summary"]
        return (
            s["render_pass"] == s["render_total"] == len(rs)
            and s["mezz_pass"] == s["mezz_total"]
            and all(_checks_ok(r, "QM-077") and r["verify"]["pass"] for r in rs.values())
        )

    n = len(ids)
    ok20 = g20(a, ra) and g20(b, rb)
    rows.append(
        (
            "G0-20",
            "PASS" if ok20 else "FAIL",
            f"{n}/{n} renders, QM-077 (1 video/0 audio) both builds",
        )
    )

    # G0-21 (encoder-independent): frame count, per-frame pts+duration hash, cut positions
    bad_cnt = [
        x["id"]
        for x, y in both
        if x["verify"]["n_decoded_frames"] != y["verify"]["n_decoded_frames"]
        or x["verify"]["n_decoded_frames"] != x["plan"]["total_frames"]
    ]
    rows.append(
        (
            "G0-21 frame count",
            "FAIL" if bad_cnt else "PASS",
            f"mismatch {bad_cnt}" if bad_cnt else f"{n}/{n} identical and equal to plan",
        )
    )
    bad_pts = [
        x["id"] for x, y in both if x["verify"]["frame_pts_hash"] != y["verify"]["frame_pts_hash"]
    ]
    rows.append(
        (
            "G0-21 per-frame PTS+duration hash",
            "FAIL" if bad_pts else "PASS",
            f"mismatch {bad_pts}" if bad_pts else f"{n}/{n} identical",
        )
    )
    bad_cut = [
        x["id"]
        for x, y in both
        if not (
            x["verify"]["detected_cut_frames"]
            == x["verify"]["expected_cut_frames"]
            == y["verify"]["detected_cut_frames"]
            == y["verify"]["expected_cut_frames"]
            and x["plan"]["frames"] == y["plan"]["frames"]
        )
    ]
    rows.append(
        (
            "G0-21 cut positions",
            "FAIL" if bad_cut else "PASS",
            f"mismatch {bad_cut}" if bad_cut else f"{n}/{n} detected == plan, both builds",
        )
    )

    # G0-24 offset part (encoder-independent): remux A/V offsets within spec on both builds
    def remux_ok(d: dict[str, Any]) -> bool:
        rs = d["remuxes"]
        return bool(rs) and all(
            r["verify"]["pass"] and _checks_ok(r, "QM-067") and _checks_ok(r, "QM-068") for r in rs
        )

    ok24 = remux_ok(a) and remux_ok(b)
    worst = max(
        (
            abs(r["verify"][k])
            for d in (a, b)
            for r in d["remuxes"]
            for k in ("offset_start_ms", "offset_end_ms")
        ),
        default=0.0,
    )
    rows.append(
        (
            "G0-24 remux A/V offset",
            "PASS" if ok24 else "FAIL",
            f"worst |offset| {worst:.3f} ms (limit 33.3)",
        )
    )

    # encoder-dependent rows
    if same_enc:
        bad_pk = [
            x["id"]
            for x, y in both
            if x["verify"]["video_packet_hash"] != y["verify"]["video_packet_hash"]
        ]
        rem_a, rem_b = _by_id(a["remuxes"]), _by_id(b["remuxes"])
        bad_rp = [
            i
            for i in rem_a
            if rem_a[i]["verify"]["video_packet_hash"] != rem_b[i]["verify"]["video_packet_hash"]
        ]
        rows.append(
            (
                "G0-21 video packet hash (render)",
                "FAIL" if bad_pk else "PASS",
                f"mismatch {bad_pk}" if bad_pk else f"{n}/{n} bit-identical",
            )
        )
        rows.append(
            (
                "G0-24 remux video packet hash",
                "FAIL" if bad_rp else "PASS",
                f"mismatch {bad_rp}" if bad_rp else f"{len(rem_a)}/{len(rem_a)} bit-identical",
            )
        )
    else:
        rows.append(("G0-21 video packet hash (render)", "N/A", _na(a, b)))
        rows.append(("G0-24 remux video packet hash", "N/A", _na(a, b)))
    pa, pb = _p95(a), _p95(b)
    if pa and pb:
        ratio = pb / pa
        meas = f"bench render p95 {pb:.2f}s / {pa:.2f}s = {ratio:.3f} (limit {SPEED_LIMIT})"
        if same_enc:
            rows.append(
                ("G0-23 render p95 ratio", "PASS" if ratio <= SPEED_LIMIT else "FAIL", meas)
            )
        else:
            rows.append(
                ("G0-23 render p95 ratio", "N/A", f"{_na(a, b)}; measured, NON-COMPARABLE: {meas}")
            )
    else:
        rows.append(("G0-23 render p95 ratio", "FAIL", "bench timings missing"))
    return rows


def _timings(d: dict[str, Any]) -> str:
    r30 = sorted(r["render_s"] for r in d["renders"] if r["params"]["seconds"] == 30)
    rm = [r["remux_s"] for r in d["remuxes"]]
    bp = _p95(d)
    return (
        f"{d['ffmpeg']['version'].split(' Copyright')[0]} [{d['ffmpeg']['vcodec']}]: "
        f"render30s max {r30[-1] if r30 else 0:.2f}s, bench p95 {bp if bp else 0:.2f}s, "
        f"remux mean {sum(rm) / len(rm) if rm else 0:.3f}s"
    )


def _print(title: str, rows: list[Row]) -> bool:
    print(f"== {title}")
    for gate, status, detail in rows:
        print(f"{gate} {status}: {detail}")
    return any(s == "FAIL" for _, s, _ in rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--a", type=Path, required=True, help="baseline (8.1.3)")
    ap.add_argument("--b", type=Path, required=True, help="candidate (9.0.x)")
    ap.add_argument("--c", type=Path, default=None, help="candidate forced to a's encoder (bonus)")
    ns = ap.parse_args(argv)
    a, b = load(ns.a), load(ns.b)
    failed = _print("A vs B", compare(a, b))
    print("timings (non-comparable when encoders differ):")
    print("  A " + _timings(a))
    print("  B " + _timings(b))
    if ns.c:
        c = load(ns.c)
        failed |= _print("A vs C (same-encoder bonus)", compare(a, c))
        print("  C " + _timings(c))
    print("RESULT: " + ("FAIL" if failed else "no FAIL rows (N/A rows are not PASS)"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
