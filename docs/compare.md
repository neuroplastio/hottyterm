# pairs: before and after, judged side by side

`pairs` (`scripts/compare.py`) opens the before and the after of one
difference in two hottyterm windows, tiled left and right on an empty
Hyprland workspace, in a random order titled A and B. The maintainer
uses both, then gives a verdict; only then does `pairs` show which side
was which, and the rig's numbers (gov R-22, "The end: pairs to judge
side by side").

```
pairs                                    # the pairs and their briefs
pairs prepare [pair...] [--missing]      # build the sides ahead of time
pairs <pair> [--dry-run]                 # open it
pairs close [pair...]                    # kill what it started
pairs verdict <pair> A|B|same "<note>"   # record, then reveal the key
```

It is installed once, from this checkout, as a link on `PATH` named
`pairs` (`compare` is ImageMagick's):
`ln -s "$PWD/scripts/compare.py" ~/.local/bin/pairs`. The file, the
`COMPARE_*` variables and `~/.cache/compare` keep the older name.

## Adding a pair

A pair is one file, `compare/pairs/<name>.toml`, in the repository whose
code it builds: hottyterm's own, or another neuroplastio checkout's
`main/compare/pairs/` (plx's, or a framework track's), which `pairs` reads
too, so nobody copies another track's pairs. The name is `[a-z0-9-]`, at
most 24 characters (it goes into a socket path), and unique across them
all. Each side is one command that takes over its terminal and cleans up
after itself:

```toml
brief = "Does a key reach the screen sooner in A or in B?"  # neutral, one line
track = "R-22"            # R-22, R-23 or example
results = "docs/feel/e1.md"  # optional: shown after the verdict (relative to
                             # the pair's repository, absolute or ~); a list is fine
hottyterm = "$SIDE_DIR/bin/hottyterm"  # default: /usr/lib/hottyterm/bin/hottyterm
# hottyterm_args = []     # extra flags, the same for both sides
# home = "throwaway"      # the default: XDG config/state/data/cache are a
# seed = ["config/plx", "config/fish"]   # fresh dir per opening, seeded
#                                        # with copies of these; "real"
#                                        # uses the maintainer's own

[before]
label = "plx main at 1a2b3c4"   # shown only after the verdict
build = '''
git -C "$NEUROPLASTIO/plx/main" archive 1a2b3c4 | tar -x -C "$SIDE_WORK"
cd "$SIDE_WORK" && go build -o "$SIDE_DIR/bin/" ./cmd/plx ./cmd/plx-script
cp -a /usr/lib/hottyterm/. "$SIDE_DIR/"
'''
run = 'exec "$SIDE_WORK/scripts/perf/plx-run.sh" --bin "$SIDE_DIR/bin" -- fish'

[after]
label = "plx p/feel-fix at 5d6e7f8"
build = '''...the same, at 5d6e7f8...'''
run = 'exec "$SIDE_WORK/scripts/perf/plx-run.sh" --bin "$SIDE_DIR/bin" -- fish'
```

- **`build`** (optional) runs under `sh -e` in `pairs prepare`, with
  `SIDE_DIR` (empty it fills: the side's install prefix), `SIDE_WORK`
  (kept between builds: sources, caches), `SIDE` (`before` or `after`),
  `PAIR`, `PAIR_FILE`, `PAIR_REPO` (the repository the pair file is in,
  for its own scripts), `COMPARE_REPO` (hottyterm's checkout, which has
  `pairs` and `scripts/compare-build.sh`) and `NEUROPLASTIO` (the code
  root). Inherited `PLX_*`, `GHOSTTY_*` and `TERM_PROGRAM*` are gone. The
  log is `~/.cache/compare/<pair>/<side>.build.log`. Build from commits or
  branches of other repositories without touching their checkouts:
  `git archive` or `git clone --shared` into `$SIDE_WORK`, never a
  `git worktree add` in someone else's repository.
- **`run`** is a shell script run inside the side's window, in `$HOME`,
  with `SIDE_DIR` and a fresh `PLX_DIR` of its own
  (`/run/user/<uid>/pxd-cmp-<pair>-<A|B>-xxxx`). A bare `plx` there starts
  its own plxd. When `run` ends, the side kills whatever it left behind
  (any process carrying its `PLX_DIR` or its `COMPARE_RUN` mark, its plxd
  included) and the window closes. If it fails, the window waits for
  Enter so the error stays readable.
- **A side that runs plx starts it through the side's own launcher**,
  plx's `scripts/perf/plx-run.sh --bin "$SIDE_DIR/bin" [--setup FILE] --
  <program>`. plx trusts a plugin beside its binary only when that binary
  sits in a `builds/<commit>` directory, never in a checkout's `bin/`.
  Run bare, `plx-script` would come from `PATH`, which can be the
  installed one. The launcher copies the build into such a directory
  under a throwaway `PLX_DIR`, drops the `PATH` entries that hold a plx,
  keeps `COMPARE_RUN` (so close still finds the side's processes), and
  cleans up on exit and on SIGTERM. `--setup` registers and opens what the
  side needs once the session answers.
- **R-23's after side runs as a tool in that throwaway plx**, e.g.
  `-- my-tool`, so both sides sit in plx.

## Keeping it blind

At each opening, `pairs` mirrors `before/` and `after/` into
`~/.cache/compare/<pair>/open/A` and `/B` by hardlinks, so the windows'
exe, argv and env name only the slot. That holds only for what is inside
`$SIDE_DIR`:

- Point both sides' `hottyterm` at `$SIDE_DIR/...`, or both at the same
  installed path. `pairs` warns when the paths or `hottyterm_args`
  differ.
- Put the difference in what `build` makes, not in `run`: a process's
  argv is visible to `ps`. Config that differs goes in a file under
  `$SIDE_DIR`, named the same on both sides.
- `run` must never name the side: at run time `SIDE_DIR` is `open/A` or
  `open/B`, not `before/` or `after/`.

## Trying a pair without the maintainer's desktop

Never open a pair on the live Hyprland while building one. Instead:

- `pairs <pair> --dry-run` runs only `hyprctl version` and
  `hyprctl -j monitors|workspaces|clients`, and prints every dispatch it
  would send, in order, with the workspace it picked.
- `pairs --wm sway <pair>` runs the whole flow in a private headless
  sway: `scripts/compare-sway.sh start`, then
  `eval "$(scripts/compare-sway.sh env)"` (it sets `SWAYSOCK`,
  `COMPARE_SWAYMSG` and test dirs), `scripts/compare-sway.sh shot F.png`
  to see it, and `stop`. It runs in an `XDG_RUNTIME_DIR` of its own, short
  and under `/run/user/<uid>`, with `bus` and `systemd` linked from the
  user's, or `uwsm app` could not reach the user manager.
- Keep tests out of the real state: `COMPARE_CACHE` (default
  `~/.cache/compare`), `COMPARE_VERDICTS` (default
  `~/.cache/compare/verdicts/`), `COMPARE_PAIRS` (directories,
  `:` between them; default: every checkout's `compare/pairs/`). `COMPARE_NO_DISPATCH=1` makes any Hyprland
  dispatch fail.

## Where things go

- `~/.cache/compare/<pair>/`: `before/`, `after/` and `work/`; `key` (the
  current round) and `keys.jsonl` (every round); `session.json` and
  `open/` while it is open.
- `$COMPARE_VERDICTS/<pair>.md` (default `~/.cache/compare/verdicts/`): one
  entry per verdict, with its round, the time, A, B or same, and the note,
  never the key. Point `COMPARE_VERDICTS` at the research record's
  directory: whoever keeps the record commits it and unblinds it from
  `keys.jsonl`.
- `~/.cache/compare/verdicts.jsonl`: each verdict with its key, for the
  builders.

`pairs close` kills only processes whose environ holds one of the
pair's marks (`COMPARE_RUN=<token>` or `PLX_DIR=<its dir>`), never by
name, then removes the `PLX_DIR`s and `open/`. One verdict per round: to
judge again, open the pair again, which reshuffles it.
