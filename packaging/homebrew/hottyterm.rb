# Rendered by hottyterm's CI from packaging/homebrew/hottyterm.rb in
# github.com/neuroplastio/hottyterm; change it there.
#
# The macOS app of a hottyterm release, for Apple silicon. It is signed ad
# hoc, not notarized, so it arrives quarantined and macOS asks once before
# its first launch; the cask leaves that to macOS. No CLI, completions or
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

  # Its own, by its bundle id. Ghostty's config, which it reads too, stays.
  zap trash: [
    "~/Library/Application Support/io.github.neuroplastio.hottyterm",
    "~/Library/Caches/io.github.neuroplastio.hottyterm",
    "~/Library/HTTPStorages/io.github.neuroplastio.hottyterm",
    "~/Library/Preferences/io.github.neuroplastio.hottyterm.plist",
    "~/Library/Saved Application State/io.github.neuroplastio.hottyterm.savedState",
  ]

  caveats <<~EOS
    hottyterm is signed ad hoc, not notarized, so macOS blocks its first
    launch. Open it once, then allow it in System Settings, Privacy &
    Security ("Open Anyway").

    It reads Ghostty's config file, ~/.config/ghostty/config, as Ghostty does.
  EOS
end
