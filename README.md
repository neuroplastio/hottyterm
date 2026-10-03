# hottyterm

**A fork of Ghostty with native HOTTY.** Programs that speak
[HOTTY](https://github.com/neuroplastio/hotty) (HTML Over The TTY) show
HTML/CSS surfaces in the terminal, and hottyterm renders them itself through
[hotty-blitz](https://github.com/neuroplastio/hotty-blitz). Everything else is
Ghostty.

hottyterm is not affiliated with Ghostty. "Ghostty" and its icon are
trademarks of Ghostty's non-profit; hottyterm uses neither. Its icon for now
is the neuroplastio mark.

## A proof of concept, meant to end

hottyterm is a proof of concept of the HOTTY protocol: it shows what native
support looks like in a real terminal, and keeps the protocol honest against
one. It is not meant to be a terminal of its own. If the stars align and
Ghostty gains HOTTY support, hottyterm has done its job and stops existing.

That is why it carries HOTTY and nothing else, keeps its changes to upstream
files down to hooks, and shares Ghostty's config file, `TERM` and resources:
anyone using it can go back to Ghostty with nothing to migrate.

## What the fork is

A soft fork: upstream Ghostty at the commit in [`ghostty-ref`](ghostty-ref),
plus the patches in [`patches/`](patches/). There is no copy of Ghostty's
tree here, and no GitHub fork.

| | |
| --- | --- |
| upstream | `ghostty-org/ghostty` at `0538f753` (2026-09-29, "1.3.2-dev") |
| patches | `0001` HOTTY surfaces over hotty-blitz; `0002` a relocatable rpath for packaged Linux builds; `0003` surface image ids never collide; `0004` the pointer passes through what a surface does not take; `0005` animated images play; `0006` fit reaches the program; `0007` surfaces fetch what `hotty-net` allows; `0008` hover reaches the program, and leaving the window leaves |
| new code | `src/termio/hotty.zig`, 1376 lines: all of the logic |
| upstream files touched | 5 files, 65 lines, hooks and one setting |
| branding | generated on top from [`brand/`](brand/) (below), never kept as a patch |

The hooks:

| file | hook |
| --- | --- |
| `src/termio/Termio.zig` | settings from the config; `osc_unknown_max_bytes`; flush once per read; re-render on resize; the IO thread's loop, for the timer that plays animated images and the wakeup for what surfaces fetch |
| `src/termio/stream_handler.zig` | the `osc_unknown` action (upstream #14452) goes to hotty.zig; full reset; a changed config |
| `src/config/Config.zig` | the `hotty-net` setting |
| `src/Surface.zig` | keys, clicks and hover go to the surfaces first; the font size, for the CSS px |
| `src/build/GhosttyExe.zig` | links `libhotty_blitz` (`HOTTY_BLITZ_LIB`) |

How it works:

- **Parsing is upstream's.** Ghostty passes every OSC it does not implement to
  the stream handler once `osc_unknown_max_bytes` is set; hotty.zig takes
  OSC 7279 and hands the body to hotty-blitz.
- **The protocol is hotty-blitz's,** at the commit a release's notes name:
  CI builds against hotty-blitz's main. From hotty-blitz 0.0.3 (8330fbf), a
  program changes a document with `a=delta` (SPEC §6, hotty d2da455), and
  `a=patch`, its name before, is refused as an unknown action: a program
  needs hotty-go 57fdbb0 or later, or the same rename in its own SDK.
- **Surfaces are kitty images** in the active screen's image storage, placed
  at the cursor with a command built in memory. They scroll, clear and die
  with their screen like any kitty image.
- **Updates are kitty frame edits** (`a=f`, `r=1`) of the damaged rectangles,
  the same edits the polyfill sends to a terminal. After a font size change,
  surfaces re-render at the new cell size and replace their pixels in place.
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
- **Input:** a surface that holds the keyboard gets keys first; clicks and
  hover on a surface go to it and are not reported to the program as mouse
  input, except where it takes no pointer (`pointer-events: none`, SPEC
  §9.3): there they pass through to the window below or to the cells, and
  the program hears them as over any cell. A program that placed the surface with `p=1` hears each press on
  it as a HOTTY `press` event instead (SPEC §9, from hotty-blitz). A press
  holds the pointer until its release: one on a surface keeps it for that
  surface, one on the cells keeps it for the program, so a drag that starts
  on cells is reported whole, even over a surface. A press with Alt held
  (Option on macOS, whatever `macos-option-as-alt` says) is the program's
  wherever it lands (SPEC §9.2): no surface gets it, it is reported as mouse
  input with Alt set, and it holds the pointer for the program, so an
  alt+drag that starts over a surface (plx moving a tool or a pane) works.

## Settings

hottyterm reads Ghostty's config file (`~/.config/ghostty/config`) and adds
one setting to it.

### `hotty-net`: what surfaces may fetch

The terminal's half of the network policy (SPEC §7.2), in the syntax of a
Content Security Policy: directives separated by `;`, each followed by its
sources. **The default is empty: surfaces fetch nothing** and show only what
the program sent them. HOTTY leaves the network to the user: every fetch
tells a server that a document is being shown, and where from, so a
terminal starts with nothing granted (§7.2).

| `hotty-net =` | surfaces may fetch |
| --- | --- |
| (no line, or empty) | nothing: the default |
| `img-src https:` | images from any HTTPS origin |
| `img-src https://example.com` | images from that origin only |
| `img-src https:; font-src https:; style-src https:` | images, fonts and stylesheets over HTTPS |
| `img-src http://localhost:8080` | images from a local server, over plain HTTP |

- **Directives:** `img-src` (`<img>`, `srcset`, `<picture>`, images in SVG
  and in CSS), `style-src` (stylesheets, `@import`), `font-src`
  (`@font-face`); `media-src` is accepted, and nothing plays.
- **Sources:** an origin (`https://example.com`, `http://localhost:8080`)
  or `https:`, every HTTPS origin. Plain `http` only where an origin names
  it.
- **The document asks too:** a URL is fetched only when the document's
  `<meta name="hotty-network" content="img-src https:">` also allows it.
  A program that does not ask fetches nothing, whatever this grants.
- **Never:** files, documents (`<iframe>`), referrers, cookies or
  credentials. A redirect is followed only where the policy allows its
  target. At most 8 MiB and 10 seconds per fetch.
- **Turning it off or narrowing it:** delete the line, empty it, or list
  fewer sources, and reload the config (`reload_config`). Documents shown
  already are held to the new policy from their next request.
- Programs see the grant in the capabilities, as `net` (SPEC §4).
- Ghostty does not know the key: going back to Ghostty, delete the line.

## Branding

The fork is branded by a generated commit on top of the patches:
`scripts/brand.py` applies [`brand/brand.toml`](brand/brand.toml), the icons in
`brand/icons` and the files in `brand/overlay`, checks, and commits. It
drops the previous branding commit first, so the branding is regenerated,
never rebased, and pulling in upstream costs nothing here unless an anchor
moved.

- **Anchored rules** replace exact strings (the application id, the About
  dialog, the executable name, desktop files), each with an expected count.
  If upstream moves one, brand.py names the file and the string.
- **Translatable strings** (`_("…")`, `i18n._("…")`, `i18n.N_("…")`) and the
  translations in `po/` have the name replaced wherever it appears, so new
  strings upstream adds are covered without a rule.
- **Overlays** replace whole files: the icons and the AppStream metadata.
- **The check** fails if a user-facing string in the GTK app, the CLI's
  version, or the desktop files still names Ghostty or uses its application
  id. Comments, logs, "a fork of Ghostty" and the translations' copyright
  holder are allowed.

What changes: the name, the icon, the application id
(`io.github.neuroplastio.hottyterm`: window class, D-Bus name, desktop
entry, notifications), the executable (`hottyterm`), the About dialog and
user-facing strings. What stays, because programs and configs rely on it to
work with Ghostty: `TERM=xterm-ghostty`, `TERM_PROGRAM`, the `GHOSTTY_*`
variables, the config file (`~/.config/ghostty/config`) and the resources
directory (`share/ghostty`). The man pages and shell completions are still
Ghostty's and name `ghostty`; they matter only for an install.

## Build and run

Needs a checkout of [hotty-blitz](https://github.com/neuroplastio/hotty-blitz)
next to this repository (or `HOTTY_BLITZ_DIR`), and
[hotty](https://github.com/neuroplastio/hotty) for the examples.

```
mise install
make build                    # sets up ../ghostty, builds hotty-blitz and the fork
scripts/run.sh -e python3 ../../hotty/main/examples/dash.py
make check                    # patches apply, build, smoke test
```

The binary is `../ghostty/zig-out/bin/hottyterm`. Its application id is its
own, so it runs next to an installed Ghostty.
`scripts/build.sh` carries two workarounds for this machine: Zig
0.16 needs LLVM and LLD to link CachyOS's `crt1.o`, and a cached
blueprint-compiler 0.16 whose warnings on upstream's UI files are hidden unless
it fails.

### macOS

`scripts/build-macos.sh` builds `out/hottyterm.app` for Apple silicon on a
Mac with Xcode 26: GhosttyKit (the framework the app links) as upstream
builds it, then the app in Xcode's `ReleaseLocal` configuration, signed ad
hoc, with hotty-blitz's static library added to its link. macOS asks to confirm the first launch
(right-click, Open). The branding covers the macOS app too: bundle id
`io.github.neuroplastio.hottyterm`, name, icon (Icon Composer bundle and
image sets), menus, AppleScript dictionary and Swift strings. It never looks
for updates: Ghostty's update feed would replace it with Ghostty. Still
Ghostty's: the executable inside the bundle (`Contents/MacOS/ghostty`), and
the parts the "custom icon" setting composes an icon from.

## CI

One workflow, `.github/workflows/ci.yml`:

| job | when | what |
| --- | --- | --- |
| `linux` | every push and pull request | in an Arch Linux container: the patches apply, the branding finds its anchors, the fork builds; artifact `hottyterm-linux-x86_64` (`bin/`, `share/`, and `lib/libhotty_blitz.so`) |
| `macos` | a push to main that changes the fork's inputs (`ghostty-ref`, `patches/`, `brand/`, `notices/`, the scripts, the workflow), or on demand | `macos-26`, Xcode 26.6, `scripts/build-macos.sh`; artifact `hottyterm-macos-arm64` |
| `canary` | daily, or on demand | the patches and the branding against upstream's latest main |
| `release` | on main, when both builds ran and passed | a GitHub prerelease with both artifacts and `SHA256SUMS` |

Every build carries `LICENSE` and `THIRD-PARTY-NOTICES.txt` (the Linux
archive's top, the app's `Contents/Resources`), and each release attaches
them as files of their own. `scripts/notices.py` writes them from what the
build contained: every Zig package Ghostty's build used, every Rust crate
linked into hotty-blitz, the Zig and Rust standard libraries, and Sparkle in
the macOS app, with their licence texts. It fails on a component with no
licence it can find; `notices/overrides.toml` records, checked by hand, what
upstream says for packages that ship none. `make notices` writes this
machine's.

Releases are versioned like the other neuroplastio projects: CalVer from the
commit's UTC date, then the short commit, e.g. `26.09.29-dev.1e81d70`. The
tag is the version; the notes name the Ghostty and hotty-blitz commits the
build used. A docs-only push builds on Linux but makes no release; run the
workflow by hand for one.

A small `changes` job decides whether a push touches the fork's inputs, so
a Mac is not started only to skip. `gh workflow run ci` runs everything by
hand. Artifacts are kept for 7 days. The smoke test
needs a display and a GPU and stays local.

## Changing the fork

1. `scripts/fork.sh` sets up `../ghostty` (branch `hottyterm`: the patches,
   then the branding) if missing.
2. Change it there and commit. Run `scripts/brand.py`, which moves the
   branding back to the top, then `scripts/export.sh`, which exports
   everything but the branding.
3. Commit `patches/` here.

To change the branding, edit `brand/` and run `scripts/brand.py`; never edit
the branding commit.

`scripts/canary.sh` applies the patches to upstream's latest `main` in a
throwaway worktree, dry-runs the branding on it, and reports conflicts and
moved anchors. Moving `ghostty-ref` is a deliberate step: canary; in the
fork, `git reset --hard HEAD~1` (the branding) and `git rebase <new ref>`;
`scripts/brand.py`; build, smoke test; export; then commit `ghostty-ref` and
`patches/` together.

## Verified (2026-09-29)

On a private headless display (hotty-blitz's `scripts/headless.sh`):

- `dash.py`: 56 frames in 6 s, 55 of them partial; no kitty graphics failures.
- `form.py`: typing, Tab, a change event back to the program, the checkbox and
  the radio by click.
- Bub-n-Bros (`bubbros.py`): 383 sprites, about 7 changes a frame, 20 fps,
  keys through the kitty keyboard protocol.
- Cost: the terminal process uses 8–9% CPU on the 10 Hz dashboard. An earlier
  fork, which uploaded only the changed rectangles to the GPU, used
  6–7%. Partial texture uploads for kitty frame edits would help any kitty
  graphics user, so they are a candidate for upstream rather than for this
  patch queue.

Headless clicks need a keyboard: Ghostty takes a left click on an unfocused
surface as a focus click and does not report it, and the headless display
has no keyboard unless `wtype` is running.

## Licence

MIT ([LICENSE](LICENSE)), like Ghostty, whose source the patches change
([LICENSE.ghostty](LICENSE.ghostty)). hotty-blitz, which it links, is
Apache-2.0. Releases carry every third-party notice (`scripts/notices.py`).
