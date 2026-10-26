---
title: "Closing a window over plx asks nothing"
patch: 0040-hottyterm-closing-a-window-over-plx-asks-nothing.patch
upstream-fit: maybe
---

**What it changes:** with `confirm-close-surface` at its default, a window,
split or app whose pty has plx in the foreground closes without the "All
terminal sessions in this window will be terminated" dialog, as a shell at
its prompt already does. The foreground process group's leader is found by
name: `/proc/<pid>/comm` on Linux, libproc's `proc_name` on macOS. `always`
still asks. Upstream lines: a check in `needsConfirmQuit` and two small
functions after it in `src/Surface.zig`, and four lines of the option's
docs.

**Why we carry it:** the dialog was false over plx. plx keeps its panes,
tabs and running jobs when its terminal closes, and plain `plx` brings
them back. In plx's usability runs, newcomers who believed the dialog kept
the window open and searched for a way to detach. Over ssh, ssh is in the
foreground, so the dialog still shows.

**For upstream:** maybe, as an option rather than a name. Upstream's
dialog says the same over tmux, zellij and screen, which keep their
sessions too. WezTerm has `skip_close_confirmation_for_processes_named`
for this, with tmux in its default list. Our check names plx only.
