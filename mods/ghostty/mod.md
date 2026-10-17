---
upstream: Ghostty
url: https://github.com/ghostty-org/ghostty
license: MIT
base: 827d5c82944a5ec7cf3f5b7594a223f9648c94f3
builds: hottyterm
public: true
---

hottyterm is Ghostty with hotty, HTML over the TTY, built in: a program
that prints hotty surfaces gets HTML and CSS laid out by hotty-blitz and
drawn into the cells. Everything else stays Ghostty's: its config, its
`TERM`, its resources. We mod Ghostty rather than fork it so that hottyterm
stays upstream plus a short list of changes, most of them hooks into one new
file, `src/termio/hotty.zig`, and so that going back to Ghostty means doing
without hotty, never undoing it. A few of the patches are fixes any Ghostty
user would have: touch scrolling on GTK, a resize race, kitty image uploads.
hottyterm's name, icon and application id aren't in the set:
`scripts/brand.py` generates them from `brand/` as one commit on top.

In hottyterm, `make apply` sets up the fork at `../ghostty` (`base`, the
set, then the branding) and checks that the set applies on `base`. `make
canary` applies the set to Ghostty's latest `main` and dry-runs the branding
there. After a change in the fork, `make export` writes the set back here
and points each patch's `.md` at its new file name.
