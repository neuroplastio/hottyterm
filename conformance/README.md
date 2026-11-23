The unchanged hotty conformance vectors from `neuroplastio/hotty` tag
`v0.8.0`, commit `ed985a74af914a0c4af46cce137184d03b67301a`.
They are licensed under [Apache-2.0](LICENSE-APACHE), as the spec states.
The format is described by that tag's `conformance/README.md`.

The protocol, layout, input and wire conformance suite runs in hotty-blitz,
which hottyterm embeds through its C ABI. `scripts/hit-check.sh` additionally
runs both hit vectors from this snapshot through a real hottyterm PTY,
including quiet suppression, request numbers and replies. It needs HOTTY_DIR
for the Python wire client. With an output directory and `versions` as
its second argument, it runs the three query negotiation vectors instead,
including 0.7 compatibility and EVERSION.

`scripts/reduced-motion-check.sh` tests the GTK preference and idle repaint; `probe-macos.yml`'s `reduced_motion` mode tests
the macOS preference on its disposable runner.

`scripts/button-chord-check.py` uses `HOTTY_DIR` and `HOTTY_BLITZ_DIR` to
run GTK input probes on a private Wayland display. It checks primary and
same-DOM button chords, as well as keyboard focus after Alt+middle on the
cells. The headless helper installs Sway in the temporary directory.
Set `SWAY_ROOT` to reuse an unpacked distribution containing `usr/bin/sway`.

Do not edit the vectors here. Update this copy from a released spec tag.
