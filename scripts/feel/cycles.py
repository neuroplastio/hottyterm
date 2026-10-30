#!/usr/bin/env python3
"""cycles.py: each timed input of a run, and the terminal's lock around it (gov R-22).

    scripts/feel/cycles.py <dir>... [--json out.json]

For scenarios whose timed input comes while other input is still being
drawn (E7W, E7T: blackbox.py's "settle": false and "quiet": false), one
row per timed input of each run <dir> (run.py's), read with merge.py's
loader (docs/trace.md) and the run's blackbox.jsonl:
- e2e: rig.pixels − rig.input, the first frame that changed the input's
  ROI; last: blackbox's last_ms, the last frame that changed it before the
  screen settled, which is when the screen showed all of the input's
  effect (E7T's filtered list);
- after <mark>: from each step marked since the timed input before
  (blackbox.py's mark: E7W's and E7T's "open", the ':' that opens plx's
  palette; E7W's "focus", B's) to the input;
- the cycle runs from the first of those marks (without one, from the
  input) to the input's last change. lock: the longest term.lock wait on the host's main
  thread (GTK's: the thread whose id is the host's pid, tr == pid) that
  overlaps the cycle, and where it waited (a.fn); held: how much of it lay
  between the input and its pixels, the part of the wait that input sat
  behind;
- parse: the longest term.parse in the cycle, on any of the host's
  threads: io-reader holds the lock while it parses a batch and renders
  its hotty surfaces (an opening palette's documents).
Then p50 and p95 of each column over the run's inputs (nearest rank, as
report.py takes them), and how many inputs a wait held back by HELD_MS
(1 ms) or more. Times are ms.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ in scripts/feel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge  # noqa: E402

HOSTS = ("hottyterm",)
COLS = ("e2e", "last", "lock", "held", "parse")
HELD_MS = 1.0  # less is a brush with a wait, not a wait


def pct(xs, p):
    """Nearest rank: the ⌈p·n/100⌉-th smallest."""
    s = sorted(x for x in xs if x is not None)
    return s[max(1, -(-p * len(s) // 100)) - 1] if s else None


def ms(ns):
    return None if ns is None else round(ns / 1e6, 2)


def records(run_dir):
    """blackbox.jsonl's timed records, by their input's time."""
    out = {}
    try:
        with open(os.path.join(run_dir, "blackbox.jsonl")) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and "t_input" in r:
                    out[r["t_input"]] = r
    except OSError:
        pass
    return out


def longest(spans, a, b):
    """The longest span of spans overlapping [a, b]."""
    hit = [e for e in spans if e["t"] < b and e["t"] + e["dur"] > a]
    return max(hit, key=lambda e: e["dur"]) if hit else None


def cycles(run_dir):
    run = merge.load(run_dir)
    evs = run.events
    host = next((f["pid"] for f in run.files if f["proc"] in HOSTS), None)
    mine = [e for e in evs if e["pid"] == host and e.get("dur")] if host is not None else []
    waits = [e for e in mine if e["n"] == "term.lock" and e.get("tr") == host]
    parses = [e for e in mine if e["n"] == "term.parse"]
    bb = records(run_dir)
    inputs = [e for e in evs if e["n"] == "rig.input"]
    all_marks = [e for e in evs if e["n"] == "rig.mark"]
    pixels = [e for e in evs if e["n"] == "rig.pixels"]
    rows = []
    for k, e in enumerate(inputs):
        t0, i = e["t"], e.get("a", {}).get("i")
        prev = inputs[k - 1]["t"] if k else -1
        nxt = inputs[k + 1]["t"] if k + 1 < len(inputs) else None
        marks = [m for m in all_marks if prev < m["t"] <= t0]
        px = next((p for p in pixels if p["t"] >= t0 and (nxt is None or p["t"] < nxt)
                   and p.get("a", {}).get("i", i) == i), None)
        rec = bb.get(t0, {})
        t1 = px["t"] if px else None
        last = t0 + int(rec["last_ms"] * 1e6) if rec.get("last_ms") is not None else t1
        c0 = marks[0]["t"] if marks else t0
        c1 = last if last is not None else (nxt if nxt is not None else evs[-1]["t"])
        w = longest(waits, c0, c1)
        held = None
        if w is not None and t1 is not None:
            held = max(0, min(w["t"] + w["dur"], t1) - max(w["t"], t0))
        p = longest(parses, c0, c1)
        after = {}
        for m in marks:  # the latest of each name
            after[m.get("a", {}).get("mark")] = ms(t0 - m["t"])
        rows.append({"i": i, "after": after,
                     "e2e": ms(t1 - t0) if t1 is not None else None,
                     "last": ms(last - t0) if last is not None else None,
                     "lock": ms(w["dur"]) if w else None, "fn": w["a"].get("fn") if w else None,
                     "held": ms(held), "parse": ms(p["dur"]) if p else None,
                     "miss": t1 is None})
    return host, rows


def meta(run_dir):
    try:
        with open(os.path.join(run_dir, "meta.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def cell(v):
    return "–" if v is None else f"{v:.1f}" if isinstance(v, float) else str(v)


def main(argv):
    ap = argparse.ArgumentParser(prog="cycles.py", description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+", metavar="dir")
    ap.add_argument("--json", metavar="out.json")
    args = ap.parse_args(argv)
    out, summary = [], []
    for d in args.dirs:
        try:
            host, rows = cycles(d)
        except merge.TraceError as e:
            print(f"cycles: {e}", file=sys.stderr)
            continue
        m = meta(d)
        name = os.path.basename(d.rstrip("/"))
        params = m.get("params") or {}
        names = list(dict.fromkeys(k for r in rows for k in r["after"]))
        for r in rows:
            r.update({f"after {k}": r["after"].get(k) for k in names})
        cols = [f"after {k}" for k in names] + list(COLS)
        print(f"## {name}\n")
        print(f"host pid {host}, main thread tr {host}" + (f"; {params}" if params else "")
              + f"; load {m.get('load_before', '?')}→{m.get('load_after', '?')}\n")
        head = [f"after {k}" for k in names] + ["e2e", "last", "lock", "fn", "held", "parse"]
        print("| i | " + " | ".join(head) + " |")
        print("|---:|" + "---:|" * (len(names) + 3) + "---|" + "---:|" * 2)
        for r in rows:
            print(f"| {cell(r['i'])} | " + " | ".join(cell(r[k]) for k in head)
                  + (" (miss)" if r["miss"] else "") + " |")
        stats = {c: {"p50": pct([r[c] for r in rows], 50), "p95": pct([r[c] for r in rows], 95)} for c in cols}
        held = sum(1 for r in rows if (r["held"] or 0) >= HELD_MS)
        n = len(rows)
        print(f"\nn {n}, misses {sum(r['miss'] for r in rows)}; p50 / p95: "
              + ", ".join(f"{c} {cell(stats[c]['p50'])} / {cell(stats[c]['p95'])}" for c in cols)
              + f"; a main-thread wait held the input back {HELD_MS:g} ms or more in {held} of {n}\n")
        out.append({"dir": d, "host": host, "params": params, "load": [m.get("load_before"), m.get("load_after")],
                    "rows": rows, "stats": stats, "held": held})
        summary.append((name, n, stats, held))
    if len(summary) > 1:
        print("## All\n")
        print("| run | n | " + " | ".join(f"{c} p50 / p95" for c in COLS) + " | held |")
        print("|---|---:|" + "---:|" * (len(COLS) + 1))
        for name, n, stats, held in summary:
            print(f"| {name} | {n} | " + " | ".join(f"{cell(stats[c]['p50'])} / {cell(stats[c]['p95'])}"
                                                   for c in COLS) + f" | {held} |")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"cycles": out, "units": "ms", "percentiles": "nearest rank"}, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
