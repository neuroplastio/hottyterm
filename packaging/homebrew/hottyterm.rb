# Rendered by hottyterm's CI from packaging/homebrew/hottyterm.rb in
# github.com/neuroplastio/hottyterm; change it there.
#
# The macOS app of a hottyterm release, for Apple silicon. It is signed ad
# hoc, not notarized: with the quarantine a download carries, macOS would
# refuse to open it until the user allowed it in System Settings, after
# every upgrade too. So the cask takes the quarantine off the app it has
# just installed (Homebrew 5 has no --no-quarantine). No CLI, completions or
# man pages: they are still Ghostty's and name `ghostty`. Its updates are
# off (Ghostty's feed would replace it with Ghostty), so `brew upgrade`
# updates it.
cask "hottyterm" do
  version "@VERSION@"
  sha256 "@SHA256@"

  url "https://github.com/neuroplastio/hottyterm/releases/download/#{version}/hottyterm-#{version}-macos-arm64.zip"
  name "hottyterm"
  desc "Fork of Ghostty with native HOTTY (HTML over the TTY)"
  homepage "https://github.com/neuroplastio/hottyterm"

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "hottyterm.app"

  postflight_steps do
    run "/usr/bin/xattr",
        args:           ["-dr", "com.apple.quarantine", "{{appdir}}/hottyterm.app"],
        writable_paths: ["hottyterm.app"],
        writable_base:  :appdir
  end

  # Its own, by its bundle id. Ghostty's config, which it reads too, stays.
  zap trash: [
    "~/Library/Application Support/io.github.neuroplastio.hottyterm",
    "~/Library/Caches/io.github.neuroplastio.hottyterm",
    "~/Library/HTTPStorages/io.github.neuroplastio.hottyterm",
    "~/Library/Preferences/io.github.neuroplastio.hottyterm.plist",
    "~/Library/Saved Application State/io.github.neuroplastio.hottyterm.savedState",
  ]

  caveats <<~EOS
    hottyterm is signed ad hoc, not notarized by Apple; this cask removes
    macOS's quarantine from it, so it opens without asking.

    It reads Ghostty's config file, ~/.config/ghostty/config, as Ghostty does.
  EOS
end
