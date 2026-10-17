---
title: "A surface's text field cuts, pastes and undoes"
patch: 0027-hottyterm-a-text-field-cuts-pastes-and-undoes-SPEC-1.patch
upstream-fit: no
---

**What it changes:** a text field's cut puts its text on the clipboard, and
its paste reads the clipboard through `paste_from_clipboard` after the key,
once the renderer lock is released. While a field has the keyboard,
`completeClipboardPaste` types what is pasted into it, the terminal's own
paste keys included, instead of writing it to the pty. Undo is the field's
own, in hotty-blitz (hotty SPEC §10.2, §11).

**Why we carry it:** hotty text fields edit as a browser's do.

**For upstream:** no. It serves hotty text fields.
