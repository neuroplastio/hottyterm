// ctxprog: the program of scripts/feel/ctxmenu.sh. hotty-go is the
// neighbouring checkout's (the SDK of the hotty version the build speaks),
// not a downloaded one.
module github.com/neuroplastio/hottyterm/scripts/feel/ctxprog

go 1.26.0

require (
	github.com/charmbracelet/ultraviolet v0.0.0-20261023060817-a45b7c86333f
	neuroplast.io/hotty-go v0.8.0
	neuroplast.io/hotty-go/hottyterm v0.8.0
)

require (
	github.com/charmbracelet/colorprofile v0.4.3 // indirect
	github.com/charmbracelet/x/ansi v0.11.9 // indirect
	github.com/charmbracelet/x/term v0.2.2 // indirect
	github.com/charmbracelet/x/termios v0.1.1 // indirect
	github.com/charmbracelet/x/windows v0.2.2 // indirect
	github.com/clipperhouse/displaywidth v0.11.0 // indirect
	github.com/clipperhouse/uax29/v2 v2.7.0 // indirect
	github.com/lucasb-eyer/go-colorful v1.4.1 // indirect
	github.com/mattn/go-runewidth v0.0.30 // indirect
	github.com/muesli/cancelreader v0.2.2 // indirect
	github.com/philhofer/fwd v1.2.0 // indirect
	github.com/rivo/uniseg v0.4.7 // indirect
	github.com/tinylib/msgp v1.6.5 // indirect
	github.com/xo/terminfo v1.0.0 // indirect
	golang.org/x/sync v0.22.0 // indirect
	golang.org/x/sys v0.47.0 // indirect
	neuroplast.io/myelin/myelinkey v0.2.0 // indirect
)

replace neuroplast.io/hotty-go => ../../../../../hotty-go/main
replace neuroplast.io/hotty-go/hottyterm => ../../../../../hotty-go/main/hottyterm
