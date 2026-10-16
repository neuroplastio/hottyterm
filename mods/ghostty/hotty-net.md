---
title: "A setting, hotty-net, says what a surface may fetch"
patch: 0007-hottyterm-surfaces-fetch-what-hotty-net-allows.patch
upstream-fit: no
---

**What it changes:** a new setting, `hotty-net`, in CSP syntax (`img-src
https:`), empty by default, so nothing is fetched until the user allows it.
A surface fetches only what both this and the document's own policy allow
(HOTTY SPEC §7.2), and the capabilities report it. Fetches run on
hotty-blitz's threads and wake the IO loop through an `xev.Async` when
something arrives, which then draws as the animation timer does. Upstream
lines: the field in `Config.zig`, and a call that applies it when the
configuration changes.

**Why we carry it:** HOTTY documents may show remote images, and the user
decides from where.

**For upstream:** no. It configures HOTTY only.
