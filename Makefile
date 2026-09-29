# hottyterm: the Ghostty fork is ../ghostty (scripts/fork.sh); hotty-blitz is
# HOTTY_BLITZ_DIR or next to this repository.
.PHONY: check fork apply brand build debug smoke canary export

check: apply build smoke   ## the gate

fork:
	@scripts/fork.sh

apply:   ## the patches apply cleanly to ghostty-ref
	@scripts/canary.sh $$(grep -v '^#' ghostty-ref | head -1)

brand:   ## regenerate the branding commit on top of the fork (brand/)
	@scripts/brand.py

build: fork
	@scripts/build.sh ReleaseFast

debug: fork
	@scripts/build.sh Debug

smoke:   ## a surface renders natively, on a private headless display
	@scripts/smoke.sh

canary:   ## do the patches still apply to upstream's latest main?
	@scripts/canary.sh

export:   ## the fork's commits back into patches/
	@scripts/export.sh
