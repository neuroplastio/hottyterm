---
title: "Keys are myelin key names 0.1"
patch: 0035-hottyterm-key-names-are-myelin-key-names-0.1-HOTTY-0.patch
upstream-fit: no
---

**What it changes:** hotty 0.4 names keys as myelin key names 0.1 does,
not as the W3C does (`Control+a`, `ArrowLeft`, `Meta`). A press seen as
pressed now has two names, its physical key from Ghostty's own key names
(`ctrl+key_w`) and the character it types (`ctrl+w`, `shift+g`, `?`), with
the modifiers in the order super, ctrl, alt, shift. Keys that type nothing
have only a physical name. A modifier tapped alone is named on its
release, sided and as a modifier key (`ctrl+shift_left`, `ctrl+shift`);
any other key pressed, or another modifier released, in between ends the
tap. Edit commands send the one name their bytes would carry. All in
`hotty.zig`, plus one comment line in `Config.zig`.

**Why we carry it:** hotty-blitz's 0.4 C ABI takes both names of a press.

**For upstream:** no. It names keys for hotty surfaces.
