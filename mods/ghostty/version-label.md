---
title: "The version names the release, hotty and hotty-blitz"
patch: 0037-hottyterm-the-version-names-the-release-hotty-and-ho.patch
upstream-fit: no
---

**What it changes:** `--version` and the GTK About window show the name a
person reads hottyterm's version by: the release's, then the hotty version
it speaks and hotty-blitz's, as in `hottyterm 26.10.21-dev.1e81d70 · hotty
0.4 (hotty-blitz 0.4.0)`. hottyterm's build scripts compute the label and
pass it as `HOTTYTERM_LABEL`, a build option carries it to
`hotty.version_label`, and a build without it shows Ghostty's version, as
before. Ghostty's own version is untouched: `--version` still lists it under
Version, and the release channel it decides stays the same. The macOS About
window reads the label from the app's Info.plist, which
`scripts/build-macos.sh` sets. Upstream lines: two added in
`src/build/Config.zig`, one changed in each of `src/cli/version.zig` and
`src/apprt/gtk/class/window.zig`.

**Why we carry it:** gov P-5 rule 6. A product that speaks hotty keeps its
own name for its version and shows the spec beside it wherever a person
reads the version, so the label says what the terminal speaks.

**For upstream:** no. It names hottyterm's releases.
