"""quiet.py: the rig's load gate and its record of what else ran (gov R-22,
docs/feel.md).

Before a run, the CPUs the rig runs on must be under a share busy over a
few seconds; `gate` waits up to a limit for that, then lets the run start
anyway, and returns the figures for meta.json either way. A desktop job
that starts during the run is what the gate can't see, so `During`
measures the same CPUs over the run, less the rig's own CPU time (its
cgroup's): when the rig is pinned to them, the rest is other work.
"""
import os
import time


def parse_cpus(text):
    """'0-3,12-15' -> [0, 1, 2, 3, 12, 13, 14, 15]."""
    cpus = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        cpus.extend(range(int(lo), int(hi or lo) + 1))
    return cpus


def busy_s(cpus):
    """The CPUs' busy time so far, in seconds (/proc/stat, idle and iowait
    left out)."""
    want, total = set(cpus), 0
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("cpu") and line[3].isdigit():
                p = line.split()
                if int(p[0][3:]) in want:
                    v = [int(x) for x in p[1:9]]  # user..steal; guest is inside user
                    total += sum(v) - v[3] - v[4]
    return total / os.sysconf("SC_CLK_TCK")


def load1():
    with open("/proc/loadavg") as f:
        return float(f.read().split()[0])


def gate(cpus, under=10.0, window=5.0, wait=300.0):
    """Wait until `cpus` are under `under` percent busy over `window` s, at
    most `wait` s; the figures, whether it passed or timed out."""
    t0 = time.monotonic()
    while True:
        a, ta = busy_s(cpus), time.monotonic()
        time.sleep(window)
        b, tb = busy_s(cpus), time.monotonic()
        pct = 100 * (b - a) / ((tb - ta) * len(cpus))
        waited = tb - t0 - window
        if pct < under or waited + window > wait:
            return {"cpus": len(cpus), "under_pct": under, "window_s": window,
                    "busy_pct": round(pct, 1), "load1": load1(), "waited_s": round(max(waited, 0.0)),
                    "passed": pct < under}


def own_cpu_s():
    """This process's cgroup's CPU time so far, in seconds, or None."""
    try:
        with open("/proc/self/cgroup") as f:
            cg = f.read().strip().split(":", 2)[2]
        with open(f"/sys/fs/cgroup{cg}/cpu.stat") as f:
            for line in f:
                k, v = line.split()
                if k == "usage_usec":
                    return int(v) / 1e6
    except (OSError, IndexError, ValueError):
        pass
    return None


def pinned_within(cpus):
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("Cpus_allowed_list:"):
                return set(parse_cpus(line.split(":", 1)[1])) <= set(cpus)
    return False


class During:
    """Started before a run and ended after it: the CPUs' busy share over
    the run and, when the rig is pinned within them, the share other work
    took (foreign_pct; 100 / len(cpus) is one CPU busy throughout)."""

    def __init__(self, cpus):
        self.cpus = cpus
        self.t, self.busy, self.own = time.monotonic(), busy_s(cpus), own_cpu_s()

    def end(self):
        wall = time.monotonic() - self.t
        busy = busy_s(self.cpus) - self.busy
        own = own_cpu_s()
        out = {"wall_s": round(wall, 1), "busy_pct": round(100 * busy / (wall * len(self.cpus)), 1)}
        if own is not None and self.own is not None:
            mine = own - self.own
            out["rig_cpu_s"] = round(mine, 2)
            if pinned_within(self.cpus):
                out["foreign_pct"] = round(100 * max(busy - mine, 0.0) / (wall * len(self.cpus)), 1)
        return out
