#!/usr/bin/env python3
"""Sums up the trace in a diag-macos.sh bundle (or any HOTTY_TRACE dir):
what hottyterm and hotty-blitz did per second, and per surface why frames
were painted rather than played from the loops kept (docs/trace.md).

    scripts/diag-summary.py hottyterm-diag-<time>/trace
"""
import collections
import json
import pathlib
import sys

LOOP = {0: "played from memory", 1: "something else changed", 2: "delivered again whole",
        3: "viewport changed", 4: "damage pending", 5: "watching a period", 6: "backing off"}


def lines(path):
    with open(path) as f:
        next(f, None)
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                pass


def main(d):
    events = []
    for f in sorted(pathlib.Path(d).glob("*.jsonl")):
        events.extend(lines(f))
    if not events:
        sys.exit(f"no stamps in {d}")
    t0 = min(e["t"] for e in events)
    t1 = max(e["t"] + e.get("dur", 0) for e in events)
    secs = max((t1 - t0) / 1e9, 1e-9)
    print(f"{len(events)} stamps over {secs:.1f} s\n")

    count = collections.Counter()
    busy = collections.Counter()
    for e in events:
        count[e["n"]] += 1
        busy[e["n"]] += e.get("dur", 0)
    print(f"{'stage':<22}{'per s':>9}{'ms/s':>9}{'mean µs':>10}")
    for n, c in count.most_common():
        b = busy[n]
        mean = f"{b / c / 1e3:.0f}" if b else ""
        ms = f"{b / 1e6 / secs:.1f}" if b else ""
        print(f"{n:<22}{c / secs:>9.1f}{ms:>9}{mean:>10}")

    pty = sum(e.get("a", {}).get("n", 0) for e in events if e["n"] == "term.pty.read")
    print(f"\npty output: {pty / secs:.0f} bytes/s")

    handled = collections.Counter()
    for e in events:
        if e["n"] == "blitz.handle":
            a = e.get("a", {})
            handled[(a.get("s", "?"), a.get("a", "?"))] += 1
    if handled:
        print("\ncommands per surface (per s):")
        for (s, a), c in handled.most_common(20):
            print(f"  {s:<30} a={a:<8}{c / secs:>8.1f}")

    per = collections.defaultdict(collections.Counter)
    for e in events:
        if e["n"] == "blitz.deliver":
            a = e.get("a", {})
            per[a.get("s", "?")][a.get("loop", -1)] += 1
    if per:
        print("\nframes per surface (per s), and why they were painted:")
        for s, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
            why = ", ".join(f"{LOOP.get(k, 'unknown')} {v / secs:.1f}" for k, v in c.most_common())
            print(f"  {s:<30}{sum(c.values()) / secs:>8.1f}  {why}")

    stops = collections.Counter(e.get("a", {}).get("why", "?") for e in events if e["n"] == "blitz.loops.stop")
    if stops:
        print("\nloops given up: " + ", ".join(f"{k} {v}" for k, v in stops.most_common()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
