---
title: "A key's release goes where its press went"
patch: 0010-hottyterm-a-key-s-release-goes-where-its-press-went.patch
upstream-fit: no
---

**What it changes:** while a surface held the keyboard, every key release
was swallowed, and while none did, every release was passed on. A program
that asks the kitty keyboard protocol for event types could hear a press
without its release, or a release without its press, when a surface took
or gave back the keyboard between them. `hotty.zig` now keeps the keys
whose press a surface took, and sends each release the same way. No
upstream lines.

**Why we carry it:** programs that use the kitty keyboard protocol and
hotty surfaces together.

**For upstream:** no. Only `hotty.zig` changes.
