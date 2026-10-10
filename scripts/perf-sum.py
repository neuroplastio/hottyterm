#!/usr/bin/env python3
# Prints scripts/perf.sh's counts: a line per run, then each variant's range
# and mean. Threads are grouped as docs/performance.md describes them:
#   paint     the busiest io-reader, the IO thread that paints surfaces
#   workers   the other io-readers, vello_cpu's workers (they take its name)
#   gtk       the main thread, named after the executable
#   renderer  the renderer thread
#   other     everything else
# Counts are millions of user-space instructions / cycles over the window.
#
#   scripts/perf-sum.py out/perf/<name>.<round>...
import collections
import os
import sys

GROUPS = ("paint", "workers", "gtk", "renderer", "other")


def read(prefix):
    threads = collections.defaultdict(dict)
    for line in open(prefix + ".stat"):
        f = line.strip().split(",")
        if len(f) < 4 or not f[1] or f[1].startswith("<"):
            continue
        comm, tid = f[0].rsplit("-", 1)
        threads[(comm, tid)][f[3].split(":")[0]] = int(f[1])
    readers = [(v.get("cycles", 0), k) for k, v in threads.items() if k[0] == "io-reader"]
    painter = max(readers)[1] if readers else None
    groups = collections.defaultdict(collections.Counter)
    busy = 0
    for k, v in threads.items():
        if k == painter:
            g = "paint"
        elif k[0] == "io-reader":
            g = "workers"
            busy += v.get("cycles", 0) > 1e6
        elif k[0] == "renderer":
            g = "renderer"
        elif k[0] in ("hottyterm", "ghostty"):
            g = "gtk"
        else:
            g = "other"
        groups[g].update(v)
    cpu = open(prefix + ".cpu").read().split()
    cpu = dict(zip(cpu[::2], cpu[1::2]))
    total = sum(groups.values(), collections.Counter())
    return {
        "instructions": total["instructions"] / 1e6,
        "cycles": total["cycles"] / 1e6,
        "cpu": int(cpu["cpu_ticks"]) / int(cpu["tick_hz"]),
        "groups": groups,
        "busy": busy,
        "threads": cpu["threads"],
        "load": cpu["load"],
    }


runs = collections.defaultdict(list)
for prefix in sys.argv[1:]:
    run = read(prefix)
    name = os.path.basename(prefix)
    runs[name.rsplit(".", 1)[0]].append(run)
    parts = "  ".join(f"{g} {run['groups'][g]['instructions'] / 1e6:.0f}/{run['groups'][g]['cycles'] / 1e6:.0f}"
                      for g in GROUPS)
    print(f"{name:12s} instr {run['instructions']:5.0f}M  cycles {run['cycles']:5.0f}M  cpu {run['cpu']:.2f} s"
          f" | {parts} | busy workers {run['busy']}, threads {run['threads']}, load {run['load']}")

print()
for name, rs in runs.items():
    cols = []
    for key, unit, fmt in (("instructions", "M", ".0f"), ("cycles", "M", ".0f"), ("cpu", " s", ".2f")):
        v = [r[key] for r in rs]
        cols.append(f"{key} {min(v):{fmt}}–{max(v):{fmt}}{unit}, mean {sum(v) / len(v):{fmt}}{unit}")
    print(f"{name:12s} {len(rs)} run(s): " + "; ".join(cols))
