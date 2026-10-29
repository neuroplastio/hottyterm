package main

import (
	"time"

	hotty "github.com/neuroplastio/hotty-go"
)

// dash is --paint's surface: a dash of cards from row top to the bottom,
// which repaints on its own timer at --hz: each tick a delta changes six
// cards' numbers and bars spread across it (prog.tick). It keeps the
// terminal's pty thread busy with hotty work while the rig times
// something else: e1's echo, or e2's and e3's input, which the host
// handles under the lock that thread holds while it paints.
type dash struct {
	name    string
	top     int
	srows   int
	cards   int
	tick    int
	ticking bool
}

// draw places the dash from row top down, for the terminal's size, and
// returns what to write. The caller holds a.out and starts the ticker.
func (d *dash) draw(a *app, top int) string {
	if d.name == "" {
		d.name = surfaceName(a.name + "-dash")
		a.surfaces = append(a.surfaces, d.name)
	}
	d.top = top
	size := a.size
	if a.name != "e1" {
		size = "full" // below e2's or e3's surface: the rest of the window
	}
	d.srows = heightRows(size, a.rows, top)
	w, h := a.surfaceCSS(a.cols, d.srows)
	doc, n := paintDoc(size, w, h)
	d.cards = n
	// Detached: the dash reports nothing and never takes the keyboard,
	// so every key reaches what is timed; deltas still apply (SPEC §5.5).
	return hotty.Doc(d.name, doc, hotty.Detached()) +
		hotty.PlaceAt(d.name, 0, top, hotty.Placement{Cols: a.cols, Rows: d.srows})
}

// start runs the ticker, once.
func (d *dash) start(a *app) {
	if !d.ticking {
		d.ticking = true
		go d.ticker(a)
	}
}

// ticker repaints the dash at --hz until the program cleans up.
func (d *dash) ticker(a *app) {
	hz := a.hz
	if hz <= 0 {
		hz = 10
	}
	t := time.NewTicker(time.Duration(float64(time.Second) / hz))
	defer t.Stop()
	for range t.C {
		a.out.Lock()
		if a.closed {
			a.out.Unlock()
			return
		}
		d.tick++
		cmd := paintTick(d.name, d.cards, d.tick)
		a.answer("prog.tick", "tick", cmd, num("i", d.tick))
		a.out.Unlock()
		if tr != nil {
			tr.flush()
		}
	}
}

// layout is where the dash is.
func (d *dash) layout(a *app) *dashLayout {
	if d.name == "" {
		return nil
	}
	w, h := a.surfaceCSS(a.cols, d.srows)
	return &dashLayout{Surface: d.name, Cell: [2]int{0, d.top}, Cells: [2]int{a.cols, d.srows}, CSS: [2]float64{w, h}, Hz: a.hz}
}

type dashLayout struct {
	Surface string     `json:"surface"`
	Cell    [2]int     `json:"cell"`
	Cells   [2]int     `json:"cells"`
	CSS     [2]float64 `json:"css"`
	Hz      float64    `json:"hz"`
}
