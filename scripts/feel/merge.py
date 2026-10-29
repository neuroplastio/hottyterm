#!/usr/bin/env python3
"""merge.py: one run's hotty/1 trace files as one timeline (docs/trace.md).

    scripts/feel/merge.py <dir>

Reads every <proc>-<pid>.jsonl in <dir> and writes:
- <dir>/merged.jsonl: every event with proc and pid added, sorted by t;
- <dir>/trace.json: the Chrome trace-event format, for ui.perfetto.dev.

Reading:
- A file is a trace when it is named <proc>-<pid>.jsonl or its first line
  has a "trace" key. Other .jsonl files (the rig's steps.jsonl and
  blackbox.jsonl, our own merged.jsonl) are not traces and are left alone.
- A header with a version other than hotty/1, or a clock other than
  monotonic or uptime-raw, stops the merge, and so does a mix of clocks.
- A malformed line is skipped and counted on stderr: a process killed
  mid-write can leave a partial last line. An empty trace file, or one
  whose header was cut off, is skipped with a warning.

trace.json:
- ts and dur are µs as floats, relative to the first event. Each value is
  the double whose ×1000 is at least the ns (ns are integers), so Perfetto,
  which truncates ts×1000 to ns, gets back the exact ns and the spans nest
  as written.
- A pid is one process, named after its main proc ("hottyterm 4242", with
  hotty-blitz's tracks under it). Its tracks: an int tr is the OS thread
  id; a str tr (a role such as "input") is a synthetic tid per (pid, tr),
  named after it; a line without tr goes on a track named after its proc.
- Spans are X, instants are i with s:"t", counters (lines with c) are C.
  Each rig.input is also a global instant "input <i>", a line across all
  tracks.
- Spans on a track must nest. A span that overlaps another without nesting
  goes on an extra track ("<track> +1"), with a count on stderr.

Other scripts import load() and use Run.
"""
import json
import math
import os
import re
import sys

VERSION = "hotty/1"
CLOCKS = ("monotonic", "uptime-raw")
# Where each proc goes in the timeline, top to bottom; others go after.
ORDER = ("rig", "hottyterm", "plx", "plxd", "plx-script", "prog", "blitz")
# Procs that are libraries inside another process: never a process's name
# while another proc shares their pid.
LIBRARIES = ("blitz",)
TRACE_NAME = re.compile(r"^([a-z0-9-]+)-([0-9]+)\.jsonl$")
PROC = re.compile(r"^[a-z0-9-]+$")
OUTPUTS = ("merged.jsonl",)


class TraceError(Exception):
    """A run that can't be merged."""


class Run:
    """One run's events, sorted by (t, longest first)."""

    def __init__(self, path, clock, files, events):
        self.dir = path
        self.clock = clock
        # [{"name", "proc", "pid", "events", "skipped"}], one per trace file
        self.files = files
        # each a hotty/1 event dict with "proc" and "pid" added
        self.events = events

    def procs(self):
        """{pid: [proc, ...]} with each pid's procs in ORDER."""
        out = {}
        for f in self.files:
            ps = out.setdefault(f["pid"], [])
            if f["proc"] not in ps:
                ps.append(f["proc"])
        for ps in out.values():
            ps.sort(key=rank)
        return out


def rank(proc):
    return (ORDER.index(proc) if proc in ORDER else len(ORDER), proc)


def main_proc(procs):
    """The proc a pid is named after."""
    own = [p for p in procs if p not in LIBRARIES]
    return (own or procs)[0]


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def event(e):
    """The event, its numbers made ints, or None when it is malformed."""
    if not isinstance(e, dict):
        return None
    t, n = e.get("t"), e.get("n")
    if not number(t) or t < 0 or not isinstance(n, str) or not n:
        return None
    e["t"] = int(round(t))
    if "dur" in e:
        d = e["dur"]
        if not number(d) or d < 0:
            return None
        e["dur"] = int(round(d))
    if "tr" in e and (isinstance(e["tr"], bool) or not isinstance(e["tr"], (int, str))):
        return None
    if "a" in e and not isinstance(e["a"], dict):
        return None
    if "c" in e and (not isinstance(e["c"], dict) or not all(number(v) for v in e["c"].values())):
        return None
    return e


def header(path, line, cut):
    """The header's (proc, pid, clock); None for a header cut off."""
    try:
        h = json.loads(line)
    except ValueError:
        if cut:
            return None
        raise TraceError(f"{path}: the first line is not a hotty/1 header")
    if not isinstance(h, dict) or "trace" not in h:
        raise TraceError(f"{path}: the first line is not a hotty/1 header")
    if h["trace"] != VERSION:
        raise TraceError(f"{path}: trace version {h['trace']!r}, not {VERSION!r}")
    proc, pid, clock = h.get("proc"), h.get("pid"), h.get("clock")
    if not isinstance(proc, str) or not PROC.match(proc):
        raise TraceError(f"{path}: header proc {proc!r} is not in [a-z0-9-]")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
        raise TraceError(f"{path}: header pid {pid!r} is not a number")
    if clock not in CLOCKS:
        raise TraceError(f"{path}: clock {clock!r}, not one of {', '.join(CLOCKS)}")
    return proc, pid, clock


def is_trace(path, name):
    """Named <proc>-<pid>.jsonl, or headed like a trace."""
    if TRACE_NAME.match(name):
        return True
    if name in OUTPUTS:
        return False
    with open(path, "rb") as fh:
        first = fh.readline()
    try:
        h = json.loads(first)
    except ValueError:
        return False
    return isinstance(h, dict) and "trace" in h


def read(path, log):
    """One trace file: (proc, pid, clock, events, skipped lines) or None."""
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.strip():
        print(f"merge: {name}: empty, skipped", file=log)
        return None
    lines = data.split(b"\n")
    h = header(path, lines[0], cut=len(lines) == 1)
    if h is None:
        print(f"merge: {name}: its header was cut off, skipped", file=log)
        return None
    proc, pid, clock = h
    m = TRACE_NAME.match(name)
    if m and (m.group(1), int(m.group(2))) != (proc, pid):
        print(f"merge: {name}: its header says {proc}-{pid}; going by the header", file=log)
    events, skipped = [], []
    for no, raw in enumerate(lines[1:], 2):
        if not raw.strip():
            continue
        try:
            e = event(json.loads(raw))
        except ValueError:  # UnicodeDecodeError is one
            e = None
        if e is None:
            skipped.append(no)
            continue
        e["proc"], e["pid"] = proc, pid
        events.append(e)
    if skipped:
        where = ", ".join(map(str, skipped[:5])) + (", …" if len(skipped) > 5 else "")
        print(f"merge: {name}: skipped {len(skipped)} malformed line(s) (line {where})", file=log)
    return proc, pid, clock, events, len(skipped)


def sort_key(e):
    return (e["t"], -e.get("dur", 0))


def load(path, log=sys.stderr):
    """Reads a run directory's trace files into a Run; raises TraceError."""
    if not os.path.isdir(path):
        raise TraceError(f"{path}: not a directory")
    names = sorted(n for n in os.listdir(path) if n.endswith(".jsonl"))
    files, events, clocks = [], [], {}
    for name in names:
        p = os.path.join(path, name)
        if not os.path.isfile(p) or not is_trace(p, name):
            continue
        r = read(p, log)
        if r is None:
            continue
        proc, pid, clock, evs, skipped = r
        clocks.setdefault(clock, []).append(name)
        files.append({"name": name, "proc": proc, "pid": pid, "events": len(evs), "skipped": skipped})
        events.extend(evs)
    if not files:
        raise TraceError(f"{path}: no hotty/1 trace files")
    if len(clocks) > 1:
        mix = "; ".join(f"{c}: {', '.join(ns)}" for c, ns in sorted(clocks.items()))
        raise TraceError(f"{path}: the files use different clocks ({mix})")
    events.sort(key=sort_key)
    return Run(path, next(iter(clocks)), files, events)


def us(ns):
    """ns as µs: the double whose ×1000 is ns or just above (see the top)."""
    f = ns / 1000
    while f * 1000 < ns:
        f = math.nextafter(f, math.inf)
    return f


class Tracks:
    """Chrome tids for a run's tracks, and their names."""

    def __init__(self, run):
        self.procs = run.procs()
        owners = {}  # int tr -> pids that use it
        self.users = {}  # (pid, int tr) -> procs on it
        for e in run.events:
            tr = e.get("tr")
            if isinstance(tr, int) and "c" not in e:
                owners.setdefault(tr, set()).add(e["pid"])
                on = self.users.setdefault((e["pid"], tr), [])
                if e["proc"] not in on:
                    on.append(e["proc"])
        reserved = {tr for tr in owners} | set(self.procs)
        self.next = max([1 << 30, *[t + 1 for t in reserved]])
        # An int tr used under two pids is not an OS tid: the later pids get
        # a synthetic one, so Perfetto doesn't join the threads.
        self.shared = {tr: sorted(pids)[0] for tr, pids in owners.items() if len(pids) > 1}
        self.tids = {}  # key -> tid
        self.meta = {}  # tid -> (pid, name, sort)

    def new(self, pid, name, sort):
        tid = self.next
        self.next += 1
        self.meta[tid] = (pid, name, sort)
        return tid

    def tid(self, e):
        pid, proc, tr = e["pid"], e["proc"], e.get("tr")
        if isinstance(tr, int):
            key = (pid, "tid", tr)
        elif isinstance(tr, str):
            key = (pid, "role", tr)
        else:
            key = (pid, "proc", proc)
        tid = self.tids.get(key)
        if tid is not None:
            return tid
        sort = (rank(proc), len(self.tids))
        if isinstance(tr, int):
            name = f"{'+'.join(sorted(self.users[(pid, tr)], key=rank))} {tr}"
            if tr in self.shared and self.shared[tr] != pid:
                tid = self.new(pid, name, sort)
            else:
                tid = tr
                self.meta[tid] = (pid, name, sort)
        else:
            tid = self.new(pid, tr if isinstance(tr, str) else proc, sort)
        self.tids[key] = tid
        return tid


def chrome(run, log=sys.stderr):
    """The run as a Chrome trace-event object."""
    evs = run.events
    t0 = evs[0]["t"] if evs else 0
    tracks = Tracks(run)
    out = []
    lanes = {}  # tid -> [[open span ends], ...]; lane 0 is the track itself
    extra = {}  # (tid, lane) -> tid of the extra track
    overlaps = 0
    for e in evs:
        n = e["n"]
        pid = e["pid"]
        ts = us(e["t"] - t0)
        ce = {"name": n, "cat": n.split(".", 1)[0], "ph": "i", "ts": ts, "pid": pid}
        if "c" in e:  # a counter belongs to the process, not a track
            ce["ph"] = "C"
            ce["args"] = e["c"]
            out.append(ce)
            continue
        tid = ce["tid"] = tracks.tid(e)
        if "dur" in e:
            start, end = e["t"], e["t"] + e["dur"]
            stacks = lanes.setdefault(tid, [])
            lane = 0
            while True:
                if lane == len(stacks):
                    stacks.append([])
                st = stacks[lane]
                while st and st[-1] <= start:
                    st.pop()
                if not st or end <= st[-1]:
                    st.append(end)
                    break
                lane += 1
            if lane:
                overlaps += 1
                if (tid, lane) not in extra:
                    p, name, sort = tracks.meta[tid]
                    extra[(tid, lane)] = tracks.new(p, f"{name} +{lane}", (sort[0], sort[1], lane))
                ce["tid"] = extra[(tid, lane)]
            ce["ph"] = "X"
            ce["dur"] = us(e["dur"])
            ce["args"] = e.get("a", {})
        else:
            ce["s"] = "t"
            ce["args"] = e.get("a", {})
        out.append(ce)
        if n == "rig.input":
            a = e.get("a", {})
            label = f"input {a['i']}" if "i" in a else "input"
            out.append({"name": label, "cat": "rig", "ph": "i", "s": "g", "ts": ts,
                        "pid": pid, "tid": tid, "args": a})
    if overlaps:
        print(f"merge: {overlaps} span(s) overlap another on their track without nesting; "
              f"put on extra tracks", file=log)
    meta = []
    for pid, procs in sorted(tracks.procs.items(), key=lambda kv: (rank(main_proc(kv[1])), kv[0])):
        meta.append({"name": "process_name", "ph": "M", "pid": pid, "tid": 0,
                     "args": {"name": f"{main_proc(procs)} {pid}"}})
        meta.append({"name": "process_sort_index", "ph": "M", "pid": pid, "tid": 0,
                     "args": {"sort_index": len(meta) // 2}})
    for i, (tid, (pid, name, sort)) in enumerate(sorted(tracks.meta.items(), key=lambda kv: kv[1][2])):
        meta.append({"name": "thread_name", "ph": "M", "pid": pid, "tid": tid, "args": {"name": name}})
        meta.append({"name": "thread_sort_index", "ph": "M", "pid": pid, "tid": tid,
                     "args": {"sort_index": i}})
    return {
        "traceEvents": meta + out,
        "displayTimeUnit": "ms",
        "otherData": {"trace": VERSION, "clock": run.clock, "t0_ns": t0,
                      "files": [f["name"] for f in run.files]},
    }


def write_lines(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        for line in lines:
            fh.write(line)
    os.replace(tmp, path)


def write(run, log=sys.stderr):
    """Writes merged.jsonl and trace.json into the run's directory."""
    dumps = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False).encode
    write_lines(os.path.join(run.dir, "merged.jsonl"), (dumps(e) + "\n" for e in run.events))
    tr = chrome(run, log)
    evs = tr.pop("traceEvents")
    head = dumps(tr)[:-1]  # the object without its closing brace
    body = (",\n".join(dumps(e) for e in evs))
    write_lines(os.path.join(run.dir, "trace.json"),
                [head + ',"traceEvents":[\n', body, "\n]}\n"])


def main(argv):
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        run = load(argv[0])
    except TraceError as e:
        print(f"merge: {e}", file=sys.stderr)
        return 1
    write(run)
    skipped = sum(f["skipped"] for f in run.files)
    print(f"merge: {len(run.files)} file(s), {len(run.events)} event(s)"
          + (f", {skipped} malformed line(s) skipped" if skipped else "")
          + f" -> {os.path.join(run.dir, 'merged.jsonl')}, trace.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
