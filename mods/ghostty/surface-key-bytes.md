---
title: "A surface's text field reads keys as the program would"
patch: 0015-hottyterm-a-surface-names-a-key-from-the-bytes-the-p.patch
upstream-fit: no
---

**What it changes:** the surface holding the keyboard gets each key as
Ghostty encodes it for the program, in the modes the program set
(`hotty_host_key_bytes`), rather than as a key code and the text the layout
composed, so a text field's keymap is its program's (hotty SPEC §10.2,
§10.4). What a binding writes (`text:`, `csi:`, `esc:`, `cursor_key`) goes
to the surface first too: on macOS, Cmd+Left writes 0x01, which a field
reads as Ctrl+a. Keys a field doesn't use reach the program as they came.
Upstream lines: `encodeKeyOpts` is made public, and three one-line hooks
go into `performBindingAction`.

**Why we carry it:** hotty text fields.

**For upstream:** no. It routes keys to hotty surfaces.
