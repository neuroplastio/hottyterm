#!/usr/bin/env python3
"""Writes the third-party notices for one hottyterm build.

    scripts/notices.py --platform linux-x86_64 --target x86_64-unknown-linux-gnu \\
        [--fork ../ghostty] [--blitz DIR] [--extra NAME URL DIR ...] -o FILE

What a build contains, and so what the file lists with its licence texts:

- hottyterm (MIT) and Ghostty (MIT), from this repository and the fork;
- every Zig package the fork's build used: found by following Ghostty's
  build.zig.zon files, and each package's own, into the fork's zig-pkg/,
  where Zig unpacks what a build fetches. A lazy dependency the build did
  not use is not there, and is not listed;
- every Rust crate linked into hotty-blitz for --target (cargo metadata,
  normal dependencies only), hotty-blitz itself included;
- the Zig and Rust standard libraries, which are compiled in;
- anything else bundled (--extra: the macOS app's Sparkle framework).

System libraries (GTK and the rest on Linux, the frameworks on macOS) are the
user's own and are not listed. Identical licence texts are printed once, with
the components that use them.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tomllib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTICES = os.path.join(HERE, "notices")

# Licence files: LICENSE, COPYING, NOTICE, OFL.txt and their variants.
LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|copyright|notice|ofl|unlicense|patents|ftl)([-._].*)?$", re.I)
# Subdirectories where projects keep them (freetype: docs/FTL.TXT).
LICENSE_DIRS = {"docs", "doc", "license", "licenses", "licences", "legal"}


def license_files(root):
    """Licence files at `root` and one level down in the usual directories."""
    found = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return found
    for name in entries:
        path = os.path.join(root, name)
        if os.path.isfile(path) and LICENSE_NAME.match(name):
            found.append(path)
        elif os.path.isdir(path) and name.lower() in LICENSE_DIRS:
            for sub in sorted(os.listdir(path)):
                p = os.path.join(path, sub)
                if os.path.isfile(p) and LICENSE_NAME.match(sub):
                    found.append(p)
    return found


def license_files_up(path):
    """For a crate without its own: the nearest enclosing repository's."""
    while True:
        files = license_files(path)
        if files or os.path.exists(os.path.join(path, ".git")):
            return files
        parent = os.path.dirname(path)
        if parent == path:
            return []
        path = parent


# --- Zig -----------------------------------------------------------------------

DEP = re.compile(r'\.(@"[^"]+"|[A-Za-z_]\w*)\s*=\s*\.\{([^{}]*)\}', re.S)


def zon_deps(zon):
    text = re.sub(r"(?m)^\s*//[^\n]*", "", open(zon, encoding="utf-8").read())
    i = text.find(".dependencies")
    if i < 0:
        return []
    j = text.index(".{", i) + 2
    depth, k = 1, j
    while depth:
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        k += 1
    deps = []
    for m in DEP.finditer(text[j:k - 1]):
        def get(key, body=m.group(2)):
            v = re.search(r"\.%s\s*=\s*\"([^\"]*)\"" % key, body)
            return v.group(1) if v else None
        deps.append({"name": m.group(1).strip('@"'), "url": get("url"), "hash": get("hash"), "path": get("path")})
    return deps


def zig_components(fork):
    pkgs = os.path.join(fork, "zig-pkg")
    seen, comps = set(), []

    def visit(root):
        zon = os.path.join(root, "build.zig.zon")
        if not os.path.exists(zon):
            return
        for d in zon_deps(zon):
            if d["path"]:
                p = os.path.normpath(os.path.join(root, d["path"]))
                if p in seen:
                    continue
                seen.add(p)
                # Ghostty's pkg/* directories are its own build glue (its
                # licence); one that vendors code carries a licence file.
                files = license_files(p)
                if files and p != fork:
                    comps.append({"kind": "zig", "name": d["name"], "version": "", "license": "",
                                  "source": os.path.relpath(p, fork), "files": files})
                visit(p)
            elif d["hash"]:
                p = os.path.join(pkgs, d["hash"])
                if p in seen or not os.path.isdir(p):
                    continue  # a lazy dependency this build did not fetch
                seen.add(p)
                comps.append({"kind": "zig", "name": d["name"], "version": "", "license": "",
                              "source": d["url"] or "", "files": license_files(p)})
                visit(p)

    visit(fork)
    return comps


# --- Rust ----------------------------------------------------------------------

def rust_components(blitz, target):
    meta = json.loads(subprocess.check_output(
        ["mise", "x", "--", "cargo", "metadata", "--format-version", "1", "--locked",
         "--filter-platform", target], cwd=blitz))
    pkgs = {p["id"]: p for p in meta["packages"]}
    nodes = {n["id"]: n for n in meta["resolve"]["nodes"]}
    root = next(p["id"] for p in meta["packages"] if p["name"] == "hotty-blitz")
    stack, linked = [root], set()
    while stack:
        i = stack.pop()
        if i in linked:
            continue
        linked.add(i)
        for d in nodes[i]["deps"]:
            if any(k["kind"] is None for k in d["dep_kinds"]):
                stack.append(d["pkg"])
    comps = []
    for i in linked:
        p = pkgs[i]
        mdir = os.path.dirname(p["manifest_path"])
        files = license_files(mdir) or license_files_up(os.path.dirname(mdir))
        comps.append({"kind": "rust", "name": p["name"], "version": p["version"],
                      "license": p.get("license") or "", "source": p.get("repository") or "",
                      "files": files})
    return comps


# --- toolchains ----------------------------------------------------------------

def toolchain_components(blitz):
    comps = []
    zig = subprocess.check_output(["mise", "which", "zig"], cwd=HERE, text=True).strip()
    zig_license = os.path.join(os.path.dirname(os.path.realpath(zig)), "LICENSE")
    comps.append({"kind": "runtime", "name": "Zig standard library and compiler-rt", "version": "",
                  "license": "MIT", "source": "https://ziglang.org",
                  "files": [zig_license] if os.path.exists(zig_license) else []})
    sysroot = subprocess.check_output(["mise", "x", "--", "rustc", "--print", "sysroot"], cwd=blitz, text=True).strip()
    lic = os.path.join(sysroot, "share", "doc", "rust", "licenses")
    files = [os.path.join(lic, f) for f in ("MIT.txt", "Apache-2.0.txt") if os.path.exists(os.path.join(lic, f))]
    comps.append({"kind": "runtime", "name": "Rust standard library", "version": "",
                  "license": "MIT OR Apache-2.0", "source": "https://www.rust-lang.org", "files": files})
    return comps


# --- output --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True)
    ap.add_argument("--target", required=True, help="Rust target triple of the build")
    ap.add_argument("--fork", default=os.environ.get("HOTTYTERM_GHOSTTY", os.path.join(os.path.dirname(HERE), "ghostty")))
    ap.add_argument("--blitz", default=os.environ.get("HOTTY_BLITZ_DIR", os.path.join(os.path.dirname(HERE), "..", "hotty-blitz", "main")))
    ap.add_argument("--extra", nargs=3, action="append", default=[], metavar=("NAME", "URL", "DIR"))
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    fork, blitz = os.path.abspath(a.fork), os.path.abspath(a.blitz)

    own = [
        {"kind": "", "name": "hottyterm", "version": "", "license": "MIT",
         "source": "https://github.com/neuroplastio/hottyterm", "files": [os.path.join(HERE, "LICENSE")]},
        {"kind": "", "name": "Ghostty", "version": "", "license": "MIT",
         "source": "https://github.com/ghostty-org/ghostty", "files": [os.path.join(fork, "LICENSE")]},
    ]
    comps = own + zig_components(fork) + rust_components(blitz, a.target) + toolchain_components(blitz)
    for name, url, d in a.extra:
        comps.append({"kind": "bundled", "name": name, "version": "", "license": "", "source": url,
                      "files": license_files(d)})

    # A component that ships no licence file: what notices/overrides.toml
    # says upstream has, else the standard texts for its SPDX ids.
    overrides = tomllib.load(open(os.path.join(NOTICES, "overrides.toml"), "rb"))
    rust_texts = os.path.join(subprocess.check_output(
        ["mise", "x", "--", "rustc", "--print", "sysroot"], cwd=blitz, text=True).strip(), "share", "doc", "rust", "licenses")
    missing = []
    for c in comps:
        if c["files"]:
            continue
        o = overrides.get(c["kind"], {}).get(c["name"])
        if o:
            c["files"] = [os.path.join(NOTICES, f) for f in o["files"]]
            c["license"], c["source"] = c["license"] or o.get("license", ""), c["source"] or o.get("source", "")
            continue
        ids = [t for t in re.findall(r"[A-Za-z0-9.+-]+", c["license"]) if t not in ("OR", "AND", "WITH")]
        texts_for = [next((p for p in (os.path.join(NOTICES, "texts", f"{i}.txt"), os.path.join(rust_texts, f"{i}.txt"))
                           if os.path.exists(p)), None) for i in ids]
        if ids and all(texts_for):
            c["files"], c["standard"] = texts_for, True
        else:
            missing.append(c)
    for c in missing:
        print(f"notices: no licence for {c['kind']} {c['name']} {c['version']} ({c['license'] or 'no licence field'}): "
              "add it to notices/overrides.toml", file=sys.stderr)

    # One entry per distinct text, with the components that use it.
    texts = {}
    for c in comps:
        label = " ".join(x for x in (c["name"], c["version"]) if x)
        for f in c["files"]:
            t = open(f, encoding="utf-8", errors="replace").read().strip()
            key = re.sub(r"\s+", " ", t)
            texts.setdefault(key, {"text": t, "users": []})["users"].append(label)

    zig_n = sum(c["kind"] == "zig" for c in comps)
    rust_n = sum(c["kind"] == "rust" for c in comps)
    with open(a.output, "w", encoding="utf-8") as out:
        out.write(f"hottyterm: third-party notices ({a.platform})\n\n")
        out.write("hottyterm is MIT licensed. It is a fork of Ghostty, also MIT, and links\n"
                  "hotty-blitz (Apache-2.0). This build contains the components below, and\n"
                  "they are distributed under the licence texts that follow the list.\n"
                  "System libraries (GTK on Linux, the system frameworks on macOS) are not\n"
                  "part of it and are not listed.\n\n")
        out.write(f"Components: {len(comps)} ({zig_n} Zig packages, {rust_n} Rust crates)\n")
        out.write("=" * 72 + "\n\n")
        for kind, title in (("", "hottyterm and Ghostty"), ("zig", "Zig packages (Ghostty's build)"),
                            ("rust", "Rust crates (hotty-blitz)"), ("runtime", "Standard libraries compiled in"),
                            ("bundled", "Bundled")):
            group = sorted((c for c in comps if c["kind"] == kind), key=lambda c: (c["name"].lower(), c["version"]))
            if not group:
                continue
            out.write(f"{title}\n")
            for c in group:
                label = " ".join(x for x in (c["name"], c["version"]) if x)
                extra = "  ".join(x for x in (c["license"], c["source"]) if x)
                out.write(f"  {label}{'  ' + extra if extra else ''}\n")
                if c.get("standard"):
                    out.write("    (ships no licence file: the standard text of its licence, below; copyright its authors)\n")
            out.write("\n")
        out.write("Licence texts\n" + "=" * 72 + "\n")
        for entry in sorted(texts.values(), key=lambda e: sorted(e["users"])[0].lower()):
            users = sorted(set(entry["users"]), key=str.lower)
            out.write(f"\n---- {', '.join(users)}\n\n{entry['text']}\n")
    print(f"notices: {a.output}: {len(comps)} components, {len(texts)} distinct licence texts", file=sys.stderr)
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
