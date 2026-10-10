# For agents

hottyterm is a soft fork of Ghostty: upstream at a pinned commit
(`ghostty-ref`) plus the patches in `patches/`. It adds HOTTY (`SPEC.md` in
neuroplastio/hotty) through hotty-blitz's C ABI, and nothing else.

- **The patches are the source.** Work in the fork at `../ghostty` (branch
  `hottyterm`, set up by `scripts/fork.sh`), then run `scripts/export.sh`
  and commit `patches/`. Never commit a copy of Ghostty's tree here.
- **Logic goes in `src/termio/hotty.zig`; upstream files get hooks only.**
  A hook is a line or two that calls into hotty.zig. Reaching into Ghostty's
  internals from hotty.zig is fine: upstream changes then fail to compile
  there, which is easier to fix than a rebase conflict. Count the lines a
  change adds to upstream files, and say so in the commit message.
- **A research vehicle for HOTTY.** hottyterm exists to push the protocol in
  a real terminal: new HOTTY ideas land here first. If Ghostty gains official
  HOTTY support, hottyterm does not stop; it stays on the bleeding edge and
  may add experimental features that play well with the neuroplastio stack
  (plx, hotty-sdk, the hotty tools). Keep the base boring: the config, `TERM`
  and resources stay Ghostty's, and experimental parts are additive and
  namespaced, never something a user must migrate away from.
- **HOTTY first.** A generic feature (like partial texture uploads) is
  written as its own patch, in upstream's style, so the maintainer can offer
  it to Ghostty. A feature that is not HOTTY belongs upstream, in plexos, or,
  if it is experimental and tied to the neuroplastio stack, behind a
  namespace.
- **Never open issues, discussions or pull requests on ghostty-org.** Ghostty
  requires a vouch and discloses AI use; contributing there is the
  maintainer's own act.
- **Not Ghostty.** Ghostty's name and icon are its non-profit's trademarks.
  Say "a fork of Ghostty", never call hottyterm Ghostty, and do not publish a
  build under Ghostty's name or icon.
- **Branding is generated, not patched.** `scripts/brand.py` applies
  `brand/` as one commit on top of the patches and regenerates it every time.
  Never edit that commit or export it; change `brand/brand.toml` (or the
  icons and overlays) and rerun. When its check fails after an upstream
  change, add or fix a rule; do not widen the allowlist to make it pass.
- **Moving `ghostty-ref`** is one deliberate step: `scripts/canary.sh` first,
  then rebase the fork onto the new commit, fix, export, build, smoke test,
  and commit `ghostty-ref` and `patches/` together.
- **Moving `hotty-blitz-ref`** is how hotty-blitz reaches a release: CI
  builds that commit, never hotty-blitz's main as it is. `make pin-blitz`
  (a pushed commit only), `make check` with it checked out, then commit the
  ref, with any patches that need it, so each release names what it built.
- **Releases carry licence notices** (`scripts/notices.py`). When it fails
  on a new component, check the component's upstream licence and add it to
  `notices/overrides.toml` with the upstream file under `notices/upstream/`;
  never drop the check.
- **Measure performance as [docs/performance.md](docs/performance.md)
  says:** `scripts/perf.sh`, counting instructions per thread over
  alternating rounds with the load in view, not CPU time on a busy machine.
  Add what a change saves there.
- **The gate is `make check`:** the patches apply cleanly to `ghostty-ref`
  and the branding finds its anchors, the fork builds against hotty-blitz,
  and the smoke test renders a surface.
  `cargo` and `zig` come from mise (`mise x --`).
