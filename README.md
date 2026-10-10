<div align="center">

# hottyterm

**A terminal that speaks [HOTTY](https://github.com/neuroplastio/hotty) natively.**

A fork of Ghostty with [hotty-blitz](https://github.com/neuroplastio/hotty-blitz)
built in. A program that prints HOTTY **surfaces** gets HTML and CSS laid out and
drawn into cells — no script, no network, no kitty graphics across the pty.
Everything else is Ghostty.

[![status: research](https://img.shields.io/badge/status-research-orange)](#research-on-the-bleeding-edge)
[![fork of Ghostty](https://img.shields.io/badge/fork%20of-Ghostty-lightgrey)](https://ghostty.org)
[![HOTTY: native](https://img.shields.io/badge/HOTTY-native-8a2be2)](https://github.com/neuroplastio/hotty)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

[Releases](https://github.com/neuroplastio/hottyterm/releases) ·
[Install](#install) ·
[Settings](#settings) ·
[Build](#build-and-run) ·
[Branding](#branding) ·
[hotty-blitz](https://github.com/neuroplastio/hotty-blitz)

</div>

hottyterm is not affiliated with Ghostty. "Ghostty" and its icon are trademarks
of Ghostty's non-profit; hottyterm uses neither. Its icon is the neuroplastio
mark.

## Why hottyterm

HOTTY is a protocol for putting HTML and CSS **surfaces** into terminal cells,
in-band, over a pty and SSH. It needs a host to prove it against. hottyterm is
that host in the shape of a real terminal: it shows what native support looks
like, keeps the protocol honest against a terminal people already run, and gives
programs a place to try surfaces without a polyfill.

It carries HOTTY and nothing else, keeps its changes to upstream files down to
hooks, and shares Ghostty's config file, `TERM` and resources, so anyone using
it can go back to Ghostty with nothing to migrate.

## Research, on the bleeding edge

hottyterm is a **research vehicle for HOTTY**. It exists to push the protocol,
not to settle it: it is where new HOTTY ideas land first, in a terminal people
actually use.

If the stars align and Ghostty gains official HOTTY support, hottyterm does not
stop — it stays on the bleeding edge. It keeps moving ahead of the official
implementation, and it may add experimental features that play well with the
neuroplastio software stack (plx, hotty-sdk, the hotty tools) but are too new,
too specialised or too tightly coupled to upstream yet.

That never becomes a lock-in. The base is deliberately boring: the config, the
`TERM` and the resources stay Ghostty's, and the experimental parts are additive
and namespaced, so going back to Ghostty means doing without them — never
undoing them.

## What the fork is

A soft fork: upstream Ghostty at the commit in [`ghostty-ref`](ghostty-ref),
plus the patches in [`patches/`](patches/). There is no copy of Ghostty's tree
here, and no GitHub fork.

| | |
| --- | --- |
| upstream | `ghostty-org/ghostty` at `0538f753` (2026-09-29, "1.3.2-dev") |
| patches | `0001` HOTTY surfaces over hotty-blitz; `0002` a relocatable rpath for packaged Linux builds; `0003` surface image ids never collide; `0004` the pointer passes through what a surface does not take; `0005` animated images play; `0006` fit reaches the program; `0007` surfaces fetch what `hotty-net` allows; `0008` hover reaches the program, and leaving the window leaves; `0009` a document that scrolls takes the wheel first; `0010` a key's release goes where its press went; `0011` a plain click opens a link (`hotty-link-click`); `0012` the click that focuses a terminal clicks too (`hotty-focus-click`); `0013` only the loop's thread sets the frame timer; `0014` a touch drag scrolls (GTK); `0015` a surface names a key from the bytes the program would read; `0016` a touch taps and scrolls where the finger touched (GTK); `0017` a touch drags what opts out of panning; `0018` a zoom is a browser's zoom; `0019` the pty learns a new size only after the grid has it (termio, generic); `0020` a kitty frame edit uploads only the rectangle it changed (renderer, generic; OpenGL) |
| new code | `src/termio/hotty.zig`, 1628 lines: all of the logic |
| upstream files touched | 10 files, 246 lines added and 4 changed — hooks, settings and the GTK touch gesture |
| branding | generated on top from [`brand/`](brand/) (below), never kept as a patch |

The hooks:

| file | hook |
| --- | --- |
| `src/termio/Termio.zig` | settings from the config; `osc_unknown_max_bytes`; flush once per read; re-render on resize; the IO thread's loop, for the timer that plays animated images and the wakeup for what surfaces fetch |
| `src/termio/stream_handler.zig` | the `osc_unknown` action (upstream #14452) goes to hotty.zig; full reset; a changed config |
| `src/config/Config.zig` | the `hotty-net` setting |
| `src/Surface.zig` | keys, clicks, hover and the wheel go to the surfaces first; the font size, for the CSS px |
| `src/build/GhosttyExe.zig` | links `libhotty_blitz` (`HOTTY_BLITZ_LIB`) |
| `src/apprt/gtk/class/surface.zig` | a touch drag scrolls, where the finger touched; a touch over a surface goes to the surface, taps included |

## How it works

- **Parsing is upstream's.** Ghostty passes every OSC it does not implement to
  the stream handler once `osc_unknown_max_bytes` is set; hotty.zig takes
  OSC 7279 and hands the body to hotty-blitz.
- **The protocol is hotty-blitz's,** at the commit in
  [`hotty-blitz-ref`](hotty-blitz-ref), which a release's notes name too. From hotty-blitz 0.0.3 (8330fbf), a
  program changes a document with `a=delta` (SPEC §6, hotty d2da455), and
  `a=patch`, its name before, is refused as an unknown action: a program
  needs hotty-go 57fdbb0 or later, or the same rename in its own SDK.
- **Native, not the polyfill.** A program sends hottyterm OSC 7279 and
  nothing else, and the linked hotty-blitz lays out and renders every
  surface. No kitty graphics crosses the pty: turning surfaces into kitty
  graphics is what the polyfill (`hotty run`) does for terminals that are
  not hosts.
- **Drawn through Ghostty's image layer.** Inside the process, a surface's
  pixels go into the active screen's image storage (the one Ghostty keeps
  for kitty graphics), placed at the cursor by a command built in memory. A
  placement therefore scrolls with its line, goes with an erase, and leaves
  with its screen, as SPEC §5.4 and SDK §4.3 expect of any host.
- **Updates replace only the damaged rectangles** of those pixels, as
  in-memory frame edits (`a=f`, `r=1`). After a font size change, surfaces
  re-render at the new cell size and replace their pixels in place.
- **Animated images play** (GIF, APNG, WebP): hotty-blitz says when the next
  frame is due, and a timer on the IO thread's loop renders it then, as a
  frame edit of the image's box. Nothing plays, no timer.
- **`fit`** (SPEC §5.2): hotty-blitz finds it as it renders a placement made
  with `f=1`; hotty.zig sends it to the program with the replies, from
  whichever path drew the frame.
- **`hover`** (SPEC §9.4): a placement made with `v=1` hears the nearest id
  under the pointer each time it changes, and out when the pointer leaves.
  hotty-blitz finds it from the moves and leaves it already gets for
  `:hover`; hotty.zig also leaves the surface when the pointer leaves the
  window (the apprts' move to -1, -1), unless a press holds the pointer.
- **Scrolling** (SPEC §5.3): a document that asks to scroll (`a=doc
  scroll=1`, `2` or `3`) takes the wheel, a touchpad's scroll or a touch drag
  while something in it can move that way; where nothing can, the gesture
  reaches the cells as if it were over them, unless `overscroll-behavior`
  stops it. hotty-blitz decides, through `hotty_host_wheel`.
- **Touch** (SPEC §9.1, GTK only): every phase of a touch that begins over a
  surface goes to hotty-blitz (`hotty_host_touch`), taps included, and none
  to the pointer. It drags when the touched element opts in to drags and its
  `touch-action` allows no pan along the first move past 8 CSS px; its moves
  wait until then. Otherwise it pans, and the terminal scrolls with it as
  with any touch, from where the finger touched (`hotty_host_wheel` first).
  A second finger cancels it. A touch over the cells is the terminal's, and
  taps and scrolls where the finger is, not where the mouse pointer was.
  hottyterm takes no long press. `scripts/touch-check.py` is the manual
  check, since the headless display cannot touch.
- **The network** (SPEC §7.2): surfaces fetch nothing until the user grants
  it with `hotty-net`, in CSP syntax (`hotty-net = img-src https:`), and then
  only what a document also asks for with `<meta name="hotty-network">`.
  The capabilities report the grant as `net`. hotty-blitz fetches on threads
  of its own (8 MiB and 10 s at most each, no referrer or cookies); what
  arrives wakes the IO thread through an `xev.Async`, which draws it as the
  animation timer does, and sends `fit` if it changed the height.
- **A CSS px is a logical pixel,** as in a browser: the scale (device px per
  CSS px) is the display's content scale, from the DPI Ghostty loads the
  font at (2 on a Retina Mac, 1.25 on a Linux display scaled to 125%). The
  host stylesheet's root font-size is the terminal's font in CSS px (14px
  for `font-size = 14` on macOS, 16px for 12 on Linux). `HOTTY_SCALE`
  overrides the scale.
- **Keys:** a surface that holds the keyboard gets keys first, as the
  bytes the program would read for them: Ghostty's own encoding, in the
  modes the program set, and what a binding writes (`text:`, `csi:`, `esc:`,
  `cursor_key`). A text field's keymap (SPEC §10.2, §10.4) reads those, so a
  field sees the key a TUI would, whatever the layout or a remap made of it:
  on macOS, Cmd+Left (Ghostty writes 0x01) is Control+a and Option+Left
  (ESC b) is Alt+b. What the surface does not use reaches the program as it
  came. Bindings that do something else (copy, paste, tabs) stay the
  terminal's.
- **Input:** clicks and
  hover on a surface go to it and are not reported to the program as mouse
  input, except where it takes no pointer (`pointer-events: none`, SPEC
  §9.3): there they pass through to the window below or to the cells, and
  the program hears them as over any cell. A program that placed the surface
  with `p=1` hears each press on it as a HOTTY `press` event instead (SPEC
  §9, from hotty-blitz). A press holds the pointer until its release: one on
  a surface keeps it for that surface, one on the cells keeps it for the
  program, so a drag that starts on cells is reported whole, even over a
  surface. A press with Alt held (Option on macOS, whatever
  `macos-option-as-alt` says) is the program's wherever it lands (SPEC
  §9.2): no surface gets it, it is reported as mouse input with Alt set, and
  it holds the pointer for the program, so an alt+drag that starts over a
  surface (plx moving a tool or a pane) works.

## Install

Every release is a [GitHub prerelease](https://github.com/neuroplastio/hottyterm/releases):

- **macOS**, Apple silicon: `brew install --cask neuroplastio/tap/hottyterm`,
  or the release's `hottyterm-<version>-macos-arm64.zip`. The app is signed ad
  hoc, not notarized. The cask takes macOS's quarantine off it, so it opens
  without asking; from the zip, macOS blocks its first launch until it is
  allowed in System Settings, Privacy & Security ("Open Anyway"). `brew
  upgrade` updates it; the app never looks for updates itself.
- **Arch Linux**, x86_64: the AUR package
  [`hottyterm-bin`](https://aur.archlinux.org/packages/hottyterm-bin)
  (`yay -S hottyterm-bin`, or any AUR helper). It installs the release's Linux
  build in `/usr/lib/hottyterm`, with `hottyterm` on the PATH, its desktop
  entry and its icons.
- **Other Linux**, x86_64: the release's
  `hottyterm-<version>-linux-x86_64.tar.gz`, unpacked anywhere
  (`bin/hottyterm` finds its library through a relative rpath). It needs GTK 4,
  libadwaita and gtk4-layer-shell, and is built on Arch Linux, so it needs a
  glibc as recent as Arch's.

## Settings

hottyterm reads Ghostty's config file (`~/.config/ghostty/config`) and adds three
settings to it.

### `hotty-net`: what surfaces may fetch

The terminal's half of the network policy (SPEC §7.2), in the syntax of a
Content Security Policy: directives separated by `;`, each followed by its
sources. **The default is empty: surfaces fetch nothing** and show only what the
program sent them. HOTTY leaves the network to the user: every fetch tells a
server that a document is being shown, and where from, so a terminal starts with
nothing granted (§7.2).

| `hotty-net =` | surfaces may fetch |
| --- | --- |
| (no line, or empty) | nothing: the default |
| `img-src https:` | images from any HTTPS origin |
| `img-src https://example.com` | images from that origin only |
| `img-src https:; font-src https:; style-src https:` | images, fonts and stylesheets over HTTPS |
| `img-src http://localhost:8080` | images from a local server, over plain HTTP |

- **Directives:** `img-src` (`<img>`, `srcset`, `<picture>`, images in SVG and
  in CSS), `style-src` (stylesheets, `@import`), `font-src` (`@font-face`);
  `media-src` is accepted, and nothing plays.
- **Sources:** an origin (`https://example.com`, `http://localhost:8080`) or
  `https:`, every HTTPS origin. Plain `http` only where an origin names it.
- **The document asks too:** a URL is fetched only when the document's `<meta
  name="hotty-network" content="img-src https:">` also allows it. A program
  that does not ask fetches nothing, whatever this grants.
- **Never:** files, documents (`<iframe>`), referrers, cookies or credentials.
  A redirect is followed only where the policy allows its target. At most 8 MiB
  and 10 seconds per fetch.
- **Turning it off or narrowing it:** delete the line, empty it, or list fewer
  sources, and reload the config (`reload_config`). Documents shown already are
  held to the new policy from their next request.
- Programs see the grant in the capabilities, as `net` (SPEC §4).
- Ghostty does not know the key: going back to Ghostty, delete the line.

### `hotty-link-click`: how a click opens a link

**A plain click opens a link,** as in a browser: a URL or a file path in the
cells, an OSC 8 hyperlink, or a hyperlink in a surface. The pointer over one
underlines it.

| `hotty-link-click =` | a link opens with |
| --- | --- |
| `plain` (the default) | a click, or Ctrl (Cmd on macOS) and click |
| `modifier` | Ctrl (Cmd on macOS) and click only, as in Ghostty |

- **A drag still selects:** a link opens on a release that did not drag.
- **A program that reports the mouse** (an editor, tmux) gets the click, as it
  does without this setting.
- A link that opens is handed to the desktop as Ghostty hands it: the same
  opener, and on macOS the same allowlist and confirmation for OSC 8 links.
- Ghostty does not know the key: going back to Ghostty, delete the line.

### `hotty-focus-click`: the click that focuses a terminal

**The click that focuses a terminal clicks too,** as in a browser: the first
click on a window in the background, or on a split without focus, also presses
the surface's button, opens the link, or reaches the program as a mouse event.

| `hotty-focus-click =` | the click that gives a terminal focus |
| --- | --- |
| `pass` (the default) | focuses it and clicks |
| `focus` | only focuses it, as in Ghostty |

- With `pass`, a click only meant to bring hottyterm forward lands on whatever
  is under the pointer: in vim it moves the cursor, in tmux it can switch the
  pane. That is why Ghostty drops it; set `focus` to have that back.
- Ghostty does not know the key: going back to Ghostty, delete the line.

## Branding

The fork is branded by a generated commit on top of the patches:
`scripts/brand.py` applies [`brand/brand.toml`](brand/brand.toml), the icons in
`brand/icons` and the files in `brand/overlay`, checks, and commits. It drops
the previous branding commit first, so the branding is regenerated, never
rebased, and pulling in upstream costs nothing here unless an anchor moved.

- **Anchored rules** replace exact strings (the application id, the About
  dialog, the executable name, desktop files), each with an expected count. If
  upstream moves one, brand.py names the file and the string.
- **Translatable strings** (`_("…")`, `i18n._("…")`, `i18n.N_("…")`) and the
  translations in `po/` have the name replaced wherever it appears, so new
  strings upstream adds are covered without a rule.
- **Overlays** replace whole files: the icons and the AppStream metadata.
- **The check** fails if a user-facing string in the GTK app, the CLI's version,
  or the desktop files still names Ghostty or uses its application id. Comments,
  logs, "a fork of Ghostty" and the translations' copyright holder are allowed.

What changes: the name, the icon, the application id
(`io.github.neuroplastio.hottyterm`: window class, D-Bus name, desktop entry,
notifications), the executable (`hottyterm`), the About dialog and user-facing
strings. What stays, because programs and configs rely on it to work with
Ghostty: `TERM=xterm-ghostty`, `TERM_PROGRAM`, the `GHOSTTY_*` variables, the
config file (`~/.config/ghostty/config`) and the resources directory
(`share/ghostty`). The man pages and shell completions are still Ghostty's and
name `ghostty`; they matter only for an install.

## Build and run

Needs a checkout of [hotty-blitz](https://github.com/neuroplastio/hotty-blitz)
next to this repository (or `HOTTY_BLITZ_DIR`), and
[hotty](https://github.com/neuroplastio/hotty) for the examples.

```sh
mise install
make build                    # sets up ../ghostty, builds hotty-blitz and the fork
scripts/run.sh -e python3 ../../hotty/main/examples/dash.py
make check                    # patches apply, build, smoke test
```

The binary is `../ghostty/zig-out/bin/hottyterm`. Its application id is its own,
so it runs next to an installed Ghostty.

A local build takes the hotty-blitz checkout as it is, and says so when that is
not the commit in `hotty-blitz-ref`, which CI and every release build.

`scripts/build.sh` carries two workarounds for this machine: Zig 0.16 needs
LLVM and LLD to link CachyOS's `crt1.o`, and a cached blueprint-compiler 0.16
whose warnings on upstream's UI files are hidden unless it fails.

### macOS

`scripts/build-macos.sh` builds `out/hottyterm.app` for Apple silicon on a Mac
with Xcode 26: GhosttyKit (the framework the app links) as upstream builds it,
then the app in Xcode's `ReleaseLocal` configuration, signed ad hoc, with
hotty-blitz's static library added to its link. macOS blocks the first launch
until it is allowed in System Settings, Privacy & Security. The branding covers
the macOS app too: bundle id `io.github.neuroplastio.hottyterm`, name, icon
(Icon Composer bundle and image sets), menus, AppleScript dictionary and Swift
strings. It never looks for updates: Ghostty's update feed would replace it with
Ghostty. Still Ghostty's: the executable inside the bundle
(`Contents/MacOS/ghostty`), and the parts the "custom icon" setting composes an
icon from.

## CI

One workflow, `.github/workflows/ci.yml`:

| job | when | what |
| --- | --- | --- |
| `linux` | every push and pull request | in an Arch Linux container: the patches apply, the branding finds its anchors, the fork builds; artifact `hottyterm-linux-x86_64` (`bin/`, `share/`, and `lib/libhotty_blitz.so`) |
| `macos` | a push to main that changes the fork's inputs (`ghostty-ref`, `hotty-blitz-ref`, `patches/`, `brand/`, `notices/`, the scripts, the workflow), or on demand | `macos-26`, Xcode 26.6, `scripts/build-macos.sh`; artifact `hottyterm-macos-arm64` |
| `canary` | daily, or on demand | the patches and the branding against upstream's latest main |
| `release` | on main, when both builds ran and passed | a GitHub prerelease with both artifacts and `SHA256SUMS` |
| `homebrew` | after a release | `packaging/homebrew/publish.sh`: the cask `hottyterm` in [neuroplastio/homebrew-tap](https://github.com/neuroplastio/homebrew-tap), rendered from `packaging/homebrew/hottyterm.rb` with the release's app; writes with the `HOMEBREW_TAP_DEPLOY_KEY` secret, the private half of a deploy key on the tap |
| `aur` | after a release | `packaging/aur/publish.sh`: [`hottyterm-bin`](https://aur.archlinux.org/packages/hottyterm-bin) on the AUR, rendered from `packaging/aur/PKGBUILD` with the release's Linux build and built with makepkg first; writes with the `AUR_SSH_PRIVATE_KEY` secret, a key of the AUR account |

Every build carries `LICENSE` and `THIRD-PARTY-NOTICES.txt` (the Linux archive's
top, the app's `Contents/Resources`), and each release attaches them as files of
their own. `scripts/notices.py` writes them from what the build contained: every
Zig package Ghostty's build used, every Rust crate linked into hotty-blitz, the
Zig and Rust standard libraries, and Sparkle in the macOS app, with their licence
texts. It fails on a component with no licence it can find;
`notices/overrides.toml` records, checked by hand, what upstream says for
packages that ship none. `make notices` writes this machine's.

Releases are versioned like the other neuroplastio projects: CalVer from the
commit's UTC date, then the short commit, e.g. `26.09.29-dev.1e81d70`. The tag is
the version; the notes name the Ghostty and hotty-blitz commits the build used. A
docs-only push builds on Linux but makes no release; run the workflow by hand for
one. A change in hotty-blitz reaches a release when `hotty-blitz-ref` moves to it,
a commit here like any other.

A small `changes` job decides whether a push touches the fork's inputs, so a Mac
is not started only to skip. `gh workflow run ci` runs everything by hand.
Artifacts are kept for 7 days. The smoke test needs a display and a GPU and stays
local.

## Changing the fork

1. `scripts/fork.sh` sets up `../ghostty` (branch `hottyterm`: the patches, then
   the branding) if missing.
2. Change it there and commit. Run `scripts/brand.py`, which moves the branding
   back to the top, then `scripts/export.sh`, which exports everything but the
   branding.
3. Commit `patches/` here.

To change the branding, edit `brand/` and run `scripts/brand.py`; never edit the
branding commit.

`scripts/canary.sh` applies the patches to upstream's latest `main` in a
throwaway worktree, dry-runs the branding on it, and reports conflicts and moved
anchors. Moving `ghostty-ref` is a deliberate step: canary; in the fork, `git
reset --hard HEAD~1` (the branding) and `git rebase <new ref>`; `scripts/brand.py`;
build, smoke test; export; then commit `ghostty-ref` and `patches/` together.

Moving `hotty-blitz-ref` is the same kind of step: `make pin-blitz` writes
hotty-blitz's main as pushed (or `scripts/pin-blitz.sh <commit>`, one on that
main); `make check` with that commit checked out; then commit `hotty-blitz-ref`,
with any patches that need it.

## Verified (2026-09-29)

On a private headless display (hotty-blitz's `scripts/headless.sh`):

- `dash.py`: 56 frames in 6 s, 55 of them partial; no kitty graphics failures.
- `form.py`: typing, Tab, a change event back to the program, the checkbox and
  the radio by click.
- Bub-n-Bros (`bubbros.py`): 383 sprites, about 7 changes a frame, 20 fps, keys
  through the kitty keyboard protocol.
- Cost: the terminal process uses 8–9% CPU on the 10 Hz dashboard. An earlier
  fork, which uploaded only the changed rectangles to the GPU, used 6–7%.
- Since `0020` (2026-10-10), a kitty frame edit uploads only its rectangle
  into the existing texture (OpenGL; Metal still uploads whole images). On
  `dash.py` at 3.5 Mpx, about 0.45 Mpx changing a frame, the terminal went
  from 14.6–16.1% CPU to 12.8–12.9%, alternating runs on a loaded machine
  (gov R-5). It is written as its own patch so it can go upstream.

Headless clicks need a keyboard: Ghostty takes a left click on an unfocused
surface as a focus click and does not report it, and the headless display has no
keyboard unless `wtype` is running.

## Licence

MIT ([LICENSE](LICENSE)), like Ghostty, whose source the patches change
([LICENSE.ghostty](LICENSE.ghostty)). hotty-blitz, which it links, is
Apache-2.0. Releases carry every third-party notice (`scripts/notices.py`).
