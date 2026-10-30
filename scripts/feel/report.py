#!/usr/bin/env python3
"""report.py: where an input's time goes, in runs of the latency rig (gov R-22).

    scripts/feel/report.py <dir>... [--label k=v ...] [--md out.md]

Each <dir> is one run (host × scenario × scale × size × round), read with
merge.py's loader (docs/trace.md). Its labels come from the dir's meta.json:
host, sc, scale, size, round and plx when it has them, else all its scalars.
A --label k=v gives every run the keys its meta.json lacks. Runs whose labels
match get their dir's name too.

The markdown goes to stdout, or to --md out.md with out.json next to it: the
same numbers unrounded, and each input's own, for later comparisons.

Windows
- Input i's window runs from its rig.input to the next rig.input, or to the
  trace's end: everything in it belongs to i (docs/trace.md, Correlation).
- Its first rig.pixels (one naming another input in a.i is passed over)
  ends the input. Without one the input is a miss: rig.miss says the rig
  timed out ("timeout"); with neither, the trace stopped short ("lost").
- The stages and the waterfall come from the inputs with pixels.
- A trace without rig lines (a smoke run) gets windows from the host's own
  input stamps (SMOKE_STARTS: term.key, term.button, term.wheel), each to
  the next or to the trace's end, and stages alone.

Numbers
- End to end: rig.pixels − rig.input.
- Stages: for each (proc, name) in a window, but rig.input, rig.miss and
  counter samples, its first offset from the window's start (a span's
  start) and, for spans, their summed duration in the window (spans in
  parallel add up: it is CPU time, not wall time). With pixels, only what
  starts by rig.pixels counts, and spans are cut there: the input's path,
  not the work after it. n is the number of
  windows that have it. The rows go by p50 offset, so the table reads as
  the timeline.
- Percentiles are nearest rank: pP of n values is the ⌈P·n/100⌉-th
  smallest, always a value that was measured. Times are ms, one decimal.

Waterfall: input i's time from rig.input (T0) to rig.pixels (T1), split by
process. The parts add up to T1 − T0 exactly.
1. The stack's stamps count: not the rig's lines, no counter samples, and
   not term.key.up (IDLE: a key's release is no work towards the pixels).
   Spans are cut at T1.
2. "input" is T0 to the host's first input stamp (INPUT_STAMPS: term.key,
   term.pointer, term.button, term.wheel): the compositor delivering the
   event. The host is the pid of a proc in HOSTS (hottyterm). Without an
   input stamp, the host's first stamp stands in, and without that the
   first stamp of any process.
3. "present" is the host's last frame stamp by T1 (FRAMES: term.snapshot,
   GTK's main thread taking the frame) to T1: the compositor presenting
   it. Without one, the time after the last stamp lands here by 5.
4. In between, time that spans cover belongs to the proc of one of them:
   the latest started (then the shortest), so the innermost, on the
   critical path. A wait (WAITS: term.lock, the app's thread waiting for
   the terminal's lock) comes before every other span: the time it covers
   is "lock wait", whatever else runs then, since the input is waiting;
   what the lock's holder (io-reader) does meanwhile is not its work. So
   "lock wait" is carved out of what would be hottyterm's.
5. Time no span covers belongs to the proc of the next stamp (an instant
   or a span's start, a wait's being hottyterm's): that process was
   working towards it. With no stamp left before T1, it is "present".
   A window without any stamp of the stack is "unstamped".
6. Except after the hand-off: the write the host reads that the frame
   answers (HANDOFFS: plx's viewer.write, else the program's prog.write),
   the last one before the frame in the window. A write plx marks as
   changing nothing (its viewer.render's quiet) isn't one. From the
   hand-off on, the host has the input: only the host's spans count
   (rule 4), and time they don't cover goes to the host's next stamp, or
   to "present". Other processes' stamps there are off the path, such as
   plx reading the key's release after its last write.
Shares go by proc, so hotty-blitz stands apart from hottyterm, whose pid it
shares. A run's pP row is the input at pP of end to end, split: one real
input, so its row adds up. "mean" is every input's split averaged, which
adds up too. The markdown rounds each row to 0.1 ms so that it adds up to
its rounded total (largest remainder); the JSON has the exact values and
each proc's own percentiles.

Hosts without stamps (stock Ghostty, Chromium) have only the rig's lines:
they get end to end alone.
"""
import argparse
import bisect
import collections
import heapq
import json
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ in scripts/feel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge  # noqa: E402

PCTS = (50, 95, 99)
HOSTS = ("hottyterm",)
INPUT_STAMPS = ("term.key", "term.pointer", "term.button", "term.wheel")
SMOKE_STARTS = ("term.key", "term.button", "term.wheel")  # pointer moves come in floods
FRAMES = ("term.snapshot", "term.snapshot.cpu")
WAITS = {"term.lock": "lock wait"}
IDLE = ("term.key.up",)
HANDOFFS = ("viewer.write", "prog.write")  # rule 6, plx's first
DIMS = ("host", "sc", "scenario", "scale", "size", "round", "plx")
INPUT, PRESENT, UNSTAMPED = "input", "present", "unstamped"
# The waterfall's columns, left to right; other procs go before present.
SHARES = (INPUT, "hottyterm", *WAITS.values(), "plx", "plxd", "plx-script", "prog", "blitz")


def pct(values, p):
    """Nearest rank: the ⌈p·n/100⌉-th smallest of sorted values."""
    if not values:
        return None
    return values[max(1, -(-p * len(values) // 100)) - 1]


def share_rank(name):
    if name in SHARES:
        return (0, SHARES.index(name), "")
    return (1 if name not in (PRESENT, UNSTAMPED) else 2 + (name == UNSTAMPED), 0, name)


def windows(run, starts):
    """(start, its window's events) for each start, in order."""
    evs = run.events
    ts = [e["t"] for e in evs]
    for j, st in enumerate(starts):
        lo = bisect.bisect_left(ts, st["t"])
        hi = bisect.bisect_left(ts, starts[j + 1]["t"]) if j + 1 < len(starts) else len(evs)
        yield st, evs[lo:hi]


def handoff(stamps, last):
    """Rule 6: when the host got the write the frame answers, or None."""
    for name in HANDOFFS:
        ws, quiet = [], False
        for e in stamps:
            if e["t"] > last:
                break
            if e["n"] == "viewer.render":
                quiet = bool(e.get("a", {}).get("quiet"))
            elif e["n"] == name and not (name == "viewer.write" and quiet):
                ws.append(e["t"])
        if ws:
            return ws[-1]
    return None


def split(t0, t1, stamps, host):
    """{share: ns} for one input, by the rules at the top; adds up to t1 − t0."""
    spans, marks = [], []
    for e in stamps:
        s = e["t"]
        if s > t1 or e["n"] in IDLE:
            continue
        mine = e["pid"] == host
        marks.append((s, e["proc"], mine))
        if e.get("dur"):
            wait = WAITS.get(e["n"])
            spans.append((s, min(s + e["dur"], t1), wait or e["proc"], wait is not None, mine))
    if not marks:
        return {UNSTAMPED: t1 - t0}
    marks.sort(key=lambda m: m[0])  # stable: same-t marks keep the merge's order
    own = [e for e in stamps if e["pid"] == host and e["t"] <= t1 and e["n"] not in IDLE]
    given = [e["t"] for e in own if e["n"] in INPUT_STAMPS]
    first = min(given or [e["t"] for e in own] or [marks[0][0]])
    frames = [e["t"] + e.get("dur", 0) for e in own if e["n"] in FRAMES]
    frames = [t for t in frames if t <= t1]
    last = max(max(frames), first) if frames else t1
    shares = collections.Counter({INPUT: first - t0, PRESENT: t1 - last})
    h = handoff(stamps, last)
    h = last if h is None else max(h, first)
    at = [m[0] for m in marks]
    mine = [m for m in marks if m[2]]
    at_mine = [m[0] for m in mine]
    live = sorted((max(s, first), e, s, p, w, m) for s, e, p, w, m in spans if e > first and s < last)
    cuts = {first, last, h} - {None}
    cuts.update(t for t in at if first < t < last)
    for s, e, *_ in live:
        cuts.update(x for x in (s, e) if first < x < last)
    cuts = sorted(t for t in cuts if first <= t <= last)
    heap, k = [], 0
    for a, b in zip(cuts, cuts[1:]):
        while k < len(live) and live[k][0] <= a:
            _, e, s, p, w, m = live[k]
            # waits on top, then the latest started, then the shortest
            heapq.heappush(heap, (not w, -s, e, k, p, m))
            k += 1
        while heap and heap[0][2] <= a:
            heapq.heappop(heap)
        after = a >= h  # rule 6: the host has it
        top = min((x for x in heap if x[2] > a and (x[5] or not after)), default=None)
        if top:
            owner = top[4]
        else:
            ts, ms = (at_mine, mine) if after else (at, marks)
            j = bisect.bisect_left(ts, b)
            owner = ms[j][1] if j < len(ms) else PRESENT
        shares[owner] += b - a
    return {k: v for k, v in shares.items() if v}


def analyse(start, win, host, stamped):
    """One window: its stages and, from a rig.input, its end to end and
    split, or how it missed."""
    a = start.get("a", {}) if start["n"] == "rig.input" else {}
    i = a.get("i")
    t0 = start["t"]
    rec = {"i": i, "sc": a.get("sc"), "kind": a.get("kind")}
    px = None
    if start["n"] == "rig.input":
        px = next((e for e in win if e["n"] == "rig.pixels" and e["t"] >= t0
                   and e.get("a", {}).get("i", i) == i), None)
    # With pixels, the stages are the input's path: what starts after them
    # (a cursor's redraw, the next frame) is left out, and spans are cut there.
    limit = px["t"] if px else None
    stages = {}
    for e in win:
        if e["n"] in ("rig.input", "rig.miss") or "c" in e:
            continue
        if limit is not None and e["t"] > limit:
            continue
        s = stages.get((e["proc"], e["n"]))
        if s is None:
            s = stages[(e["proc"], e["n"])] = [e["t"] - t0, None]
        if "dur" in e:
            end = e["t"] + e["dur"] if limit is None else min(e["t"] + e["dur"], limit)
            s[1] = (s[1] or 0) + end - e["t"]
    rec["stages"] = stages
    if start["n"] != "rig.input":
        return rec
    if px is None:
        rec["miss"] = "timeout" if any(e["n"] == "rig.miss" for e in win) else "lost"
        return rec
    t1 = px["t"]
    rec["e2e"] = t1 - t0
    if stamped:
        rec["shares"] = split(t0, t1, [e for e in win if e["proc"] != "rig" and "c" not in e], host)
    return rec


def labels_of(path, given):
    labels = dict(given)
    meta = None
    try:
        with open(os.path.join(path, "meta.json")) as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    if isinstance(meta, dict):
        flat = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
        labels.update({k: flat[k] for k in DIMS if k in flat} or flat)
    ordered = {k: labels[k] for k in DIMS if k in labels}
    ordered.update(labels)
    return ordered


def label_text(labels):
    parts = []
    for k, v in labels.items():
        if k == "scale":
            parts.append(f"×{v}")
        elif k == "round":
            parts.append(f"r{v}")
        elif k == "plx":
            parts += ["plx"] if v else []
        elif k in DIMS:
            parts.append(str(v))
        else:
            parts.append(f"{k}={v}")
    return " ".join(parts)


def summarise(path, given):
    labels = labels_of(path, given)
    out = {"dir": path, "labels": labels, "label": label_text(labels) or os.path.basename(path.rstrip("/"))}
    try:
        run = merge.load(path)
    except merge.TraceError as e:
        out["error"] = str(e)
        return out
    host = next((f["pid"] for f in run.files if f["proc"] in HOSTS), None)
    stamped = any(e["proc"] != "rig" and "c" not in e for e in run.events)
    starts = [e for e in run.events if e["n"] == "rig.input"]
    out["from"] = "rig.input"
    if not starts:  # a smoke run: the host's own input stamps
        starts = [e for e in run.events if e["n"] in SMOKE_STARTS and e["pid"] == host]
        out["from"] = "host" if starts else "rig.input"
    recs = [analyse(st, win, host, stamped) for st, win in windows(run, starts)]
    hits = [r for r in recs if "e2e" in r]
    e2e = sorted(r["e2e"] for r in hits)
    out.update({
        "stamped": stamped,
        "inputs": len(recs),
        "hits": len(hits),
        "misses": sum("miss" in r for r in recs),
        "timeouts": sum(r.get("miss") == "timeout" for r in recs),
        "e2e": {p: pct(e2e, p) for p in PCTS},
        "per_input": recs,
    })
    by = {}
    for r in (hits if out["from"] == "rig.input" else recs):
        for key, (off, dur) in r["stages"].items():
            offs, durs = by.setdefault(key, ([], []))
            offs.append(off)
            if dur is not None:
                durs.append(dur)
    stages = []
    for (proc, name), (offs, durs) in by.items():
        offs.sort()
        durs.sort()
        stages.append({"proc": proc, "name": name, "n": len(offs), "span": bool(durs),
                       "at": {p: pct(offs, p) for p in PCTS},
                       "dur": {p: pct(durs, p) for p in PCTS} if durs else None})
    stages.sort(key=lambda s: (s["at"][50], s["at"][95], s["name"], s["proc"]))
    out["stages"] = stages
    if stamped and hits:
        names = sorted({k for r in hits for k in r["shares"]}, key=share_rank)
        ranked = sorted(hits, key=lambda r: r["e2e"])
        wf = {}
        for p in PCTS:
            r = ranked[max(1, -(-p * len(ranked) // 100)) - 1]
            wf[p] = {"i": r["i"], "e2e": r["e2e"], "shares": r["shares"]}
        wf["mean"] = {"i": None, "e2e": sum(e2e) / len(e2e),
                      "shares": {k: sum(r["shares"].get(k, 0) for r in hits) / len(hits) for k in names}}
        out["waterfall"] = wf
        out["shares"] = names
        out["share_pcts"] = {k: {p: pct(sorted(r["shares"].get(k, 0) for r in hits), p) for p in PCTS}
                             for k in names}
    return out


# Output.

def tenth(ns):
    return round(ns / 1e5)


def ms1(ns):
    return "–" if ns is None else f"{tenth(ns) / 10:.1f}"


def adding_up(total, parts):
    """The total and parts in 0.1 ms, the parts adding up to the total."""
    want = tenth(total)
    low = {k: int(v // 1e5) for k, v in parts.items()}
    rest = want - sum(low.values())
    for k in sorted(parts, key=lambda k: parts[k] / 1e5 - low[k], reverse=True)[:max(rest, 0)]:
        low[k] += 1
    return want, low


def cell(s):
    return str(s).replace("|", "\\|")


def table(head, rows, right):
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join("---:" if i >= right else "---" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


def at_name(p):
    return p if p == "mean" else f"p{p}"


def sentence(w, p):
    total, parts = adding_up(w["e2e"], w["shares"])
    which = f" (input {w['i']})" if w["i"] is not None else ""
    body = ", ".join(f"{k} {parts[k] / 10:.1f}" for k in sorted(parts, key=share_rank))
    return f"- of {total / 10:.1f} ms at {at_name(p)}{which}: {body}"


def markdown(runs):
    md = ["# Feel report", "",
          "Times in ms. Percentiles are nearest rank: pP of n values is the ⌈P·n/100⌉-th smallest. "
          "End to end is rig.pixels − rig.input; a miss is an input without pixels. "
          "The top of scripts/feel/report.py says how the waterfall splits an input.", ""]
    ok = [r for r in runs if "error" not in r and r["from"] == "rig.input"]
    md += ["## End to end", ""]
    md += table(["run", "inputs", "misses", "p50", "p95", "p99"],
                [[r["label"], r["inputs"], r["misses"], *(ms1(r["e2e"][p]) for p in PCTS)] for r in ok], 1)
    names = sorted({k for r in ok for k in r.get("shares", ())}, key=share_rank)
    md += ["", "## Waterfall", "",
           "Each pP row is the input at pP of end to end, split by process; mean is every input's "
           "split averaged. Each row adds up to its end to end.", ""]
    rows = []
    for r in ok:
        if not r["hits"]:
            continue
        if "waterfall" not in r:
            rows += [[r["label"], f"p{p}", ms1(r["e2e"][p]), *("–" for _ in names)] for p in PCTS]
            continue
        for p, w in r["waterfall"].items():
            total, parts = adding_up(w["e2e"], w["shares"])
            at = at_name(p) + (f" (#{w['i']})" if w["i"] is not None else "")
            rows.append([r["label"], at, f"{total / 10:.1f}",
                         *(f"{parts[k] / 10:.1f}" if k in parts else ("0.0" if k in r["shares"] else "–")
                           for k in names)])
    md += table(["run", "at", "end to end", *names], rows, 2)
    for r in runs:
        md += ["", f"## {r['label']}", "", f"`{r['dir']}`"]
        if "error" in r:
            md += ["", f"No trace: {r['error']}"]
            continue
        if r["from"] == "host":
            md[-1] += (f": no rig lines, so {r['inputs']} window(s) from the host's own input stamps "
                       f"({', '.join(SMOKE_STARTS)}), each to the next or to the trace's end: "
                       "stages alone, offsets from that stamp.")
        else:
            md[-1] += (f": {r['inputs']} inputs, {r['hits']} with pixels, {r['misses']} misses"
                       + (f" ({r['timeouts']} timed out)" if r["misses"] else "") + ".")
        if not r["inputs"]:
            md += ["", "No rig.input in the trace, nor an input stamp of the host: nothing to split it by."]
            continue
        if not r["stamped"]:
            md += ["", "Only the rig's stamps: end to end alone."]
            continue
        if "waterfall" in r:
            md += [""] + [sentence(w, p) for p, w in r["waterfall"].items()]
        md += [""]
        md += table(["stage", "proc", "n", "at p50", "at p95", "at p99", "span p50", "span p95", "span p99"],
                    [[s["name"], s["proc"], s["n"], *(ms1(s["at"][p]) for p in PCTS),
                      *(ms1(s["dur"][p]) if s["dur"] else "" for p in PCTS)] for s in r["stages"]], 2)
    return "\n".join(md) + "\n"


def ms(ns):
    return None if ns is None else round(ns / 1e6, 4)


def as_json(runs):
    def pcts(d):
        return {f"p{p}": ms(v) for p, v in d.items()}

    out = []
    for r in runs:
        j = {k: r[k] for k in ("dir", "label", "labels") if k in r}
        if "error" in r:
            j["error"] = r["error"]
            out.append(j)
            continue
        j.update({k: r[k] for k in ("from", "stamped", "inputs", "hits", "misses", "timeouts")})
        j["e2e_ms"] = pcts(r["e2e"])
        j["stages"] = [{"name": s["name"], "proc": s["proc"], "n": s["n"], "at_ms": pcts(s["at"]),
                        "span_ms": pcts(s["dur"]) if s["dur"] else None} for s in r["stages"]]
        if "waterfall" in r:
            j["waterfall_ms"] = {at_name(p): {"input": w["i"], "e2e": ms(w["e2e"]),
                                              "shares": {k: ms(v) for k, v in w["shares"].items()}}
                                 for p, w in r["waterfall"].items()}
            j["share_pcts_ms"] = {k: pcts(v) for k, v in r["share_pcts"].items()}
        j["inputs_ms"] = [{"i": x["i"], "sc": x["sc"], "kind": x["kind"], "e2e": ms(x.get("e2e")),
                           "miss": x.get("miss"),
                           "shares": {k: ms(v) for k, v in x["shares"].items()} if "shares" in x else None}
                          for x in r["per_input"]]
        out.append(j)
    return {"report": "feel", "percentiles": "nearest rank", "units": "ms", "runs": out}


def main(argv):
    ap = argparse.ArgumentParser(prog="report.py", description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+", metavar="dir")
    ap.add_argument("--label", action="append", default=[], metavar="k=v")
    ap.add_argument("--md", metavar="out.md")
    args = ap.parse_intermixed_args(argv)
    given = {}
    for kv in args.label:
        k, eq, v = kv.partition("=")
        if not eq or not k:
            ap.error(f"--label {kv!r}: not k=v")
        given[k] = v
    runs = [summarise(d, given) for d in args.dirs]
    seen = collections.Counter(r["label"] for r in runs)
    for r in runs:
        if seen[r["label"]] > 1:
            r["label"] += f" ({os.path.basename(r['dir'].rstrip('/'))})"
    for r in runs:
        if "error" in r:
            print(f"report: {r['error']}", file=sys.stderr)
    text = markdown(runs)
    if not args.md:
        sys.stdout.write(text)
        return 0
    with open(args.md, "w") as fh:
        fh.write(text)
    side = os.path.splitext(args.md)[0] + ".json"
    with open(side, "w") as fh:
        json.dump(as_json(runs), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"report: {len(runs)} run(s) -> {args.md}, {side}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
