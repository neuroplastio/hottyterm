# hottyterm: the Ghostty fork is ../ghostty (scripts/fork.sh); hotty-blitz is
# HOTTY_BLITZ_DIR or next to this repository.
.PHONY: check fork apply brand build debug smoke notices canary export

check: apply build smoke   ## the gate

fork:
	@scripts/fork.sh

apply: fork   ## the patches apply cleanly to ghostty-ref
	@scripts/canary.sh $$(grep -v '^#' ghostty-ref | head -1)

brand:   ## regenerate the branding commit on top of the fork (brand/)
	@scripts/brand.py

# ZIG_ARGS go to zig build: CI's release builds pass -Dcpu=baseline, so the
# binary runs on any x86-64, not only on CPUs like the runner's.
build: fork
	@scripts/build.sh ReleaseFast $(ZIG_ARGS)

debug: fork
	@scripts/build.sh Debug

notices:   ## the third-party notices of this machine's build, to out/
	@mkdir -p out && scripts/notices.py --platform linux-x86_64 --target x86_64-unknown-linux-gnu -o out/THIRD-PARTY-NOTICES-linux.txt

smoke:   ## a surface renders natively, on a private headless display
	@scripts/smoke.sh

canary: fork   ## do the patches still apply to upstream's latest main?
	@scripts/canary.sh

export:   ## the fork's commits back into patches/
	@scripts/export.sh
