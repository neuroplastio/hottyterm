// Command feelprog is the fixed programs that neuroplastio's latency rig
// (gov R-22, scripts/feel) runs inside a terminal, one per scenario. Each
// answers its input the same way every run, and, when HOTTY_TRACE is set,
// stamps when input bytes reach it (prog.read: a.n, a.k for a single key,
// a.e for the hotty events in them) and the write of its answer (prog.write,
// a span: a.n bytes), in trace format hotty/1 (docs/trace.md).
//
//	feelprog e1 [--paint [--size S] [--hz 10]]   shell echo; --paint adds a dash below it
//	feelprog e2 [--size S] [--paint]             typing in a host text field; --paint: a dash below
//	feelprog e3 [--size S] [--row-px 40] [--paint] the pointer across rows with :hover
//	feelprog e6 [--size S]                       a ~60 KB whole-document swap per key
//	feelprog html <e1p|e2|e3|e6a|e6b> [--cols N] [--rows N] [--cell WxH] [...]
//	                                             a scenario's document, for `hotty render`
//
// --size row|half|full (default full) is the surface's height: one terminal
// row, half the window's rows, or all of them (e1 --paint: all below the
// echo). --layout FILE writes where things are, as one JSON object,
// rewritten whenever the terminal's size or a cell's size changes; without
// it the layout goes to stderr as a JSON line, unless stderr is the
// terminal. q or Ctrl-C quits (e1: Ctrl-C or Ctrl-D, since it echoes q
// as a shell does; e2: Ctrl-C or Escape, since its field types q), and so
// do SIGTERM and SIGHUP: surfaces deleted, the alternate screen left, the
// trace flushed.
//
// # CSS px and the output's pixels
//
// The layout gives e3's rows in CSS px from the surface's top-left, and
// the surface's top-left as a cell (surface_cell, from 0). The host tells
// the program a cell's size in CSS px (caps cellcss) and device px per CSS
// px (caps scale); hotty-blitz has cellcss = the cell's device px / scale,
// so a cell is round(cellcss × scale) device px (cell_dev) and a CSS px is
// scale device px. A point (x, y) in CSS px of a surface at cell (c, r) is
//
//	dev     = (c·cell_dev.w + x·scale,  r·cell_dev.h + y·scale)    device px from the grid's top-left
//	logical = window_origin + (padding_dev + dev) / output_scale   compositor (pointer) px
//
// hottyterm (Ghostty) takes scale from the font's DPI: round(96 × the
// output's content scale) / 96. So at output scale 1 and 2 a CSS px is a
// logical px exactly, and at 1.6 it is 154/96/1.6 = 1.0026 logical px
// (2.4 px over a 937 px window). padding_dev is Ghostty's window padding,
// floor(2 pt × DPI / 72) on each side by default: 2, 4 and 5 device px at
// scale 1, 1.6 and 2 (2, 2.5 and 2.5 logical px); launch with
// --window-padding-x=0 --window-padding-y=0 to make it 0. Aiming at a row's
// centre leaves half a row (20 CSS px by default) for all of that. The
// layout file has each row's centre in device px from the grid's
// top-left (dx, dy), so a rig only adds the padding, divides by the
// output's scale and adds the window's origin.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
	"golang.org/x/term"

	hotty "github.com/neuroplastio/hotty-go"
)

// scenario is one program: what it draws, how it answers, where things are.
type scenario interface {
	// hotty reports whether it needs a host.
	hotty(a *app) bool
	// draw draws everything for the terminal's size: first, and after a
	// resize. The caller holds a.out.
	draw(a *app)
	// input answers one read; false quits.
	input(a *app, in *input) bool
	// layout fills in where the scenario's things are.
	layout(a *app, l *layout)
}

// app is the terminal, the options and the state every scenario shares.
type app struct {
	name       string // the scenario
	size       string // row, half or full
	rowPx      int
	hz         float64
	paint      bool
	hoverEv    bool
	layoutPath string

	// out is held by whoever writes to the terminal: the read loop, the
	// paint ticker, the signal handler.
	out        sync.Mutex
	closed     bool // after cleanup: nothing more is written
	cols, rows int
	caps       hotty.Caps
	surfaces   []string
	seq        int

	scan    hotty.Scanner
	dec     hotty.Decoder
	restore *term.State
	once    sync.Once
}

// input is one read from the terminal.
type input struct {
	t    int64 // when the read returned, on the trace clock; 0 untraced
	n    int   // bytes read
	pass []byte
	msgs []hotty.Message
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	if os.Args[1] == "html" {
		os.Exit(htmlMain(os.Args[2:]))
	}
	a := &app{name: os.Args[1]}
	fs := flag.NewFlagSet("feelprog "+a.name, flag.ExitOnError)
	fs.StringVar(&a.size, "size", "full", "the surface's height: row, half or full")
	fs.IntVar(&a.rowPx, "row-px", 40, "e3: a row's height in CSS px")
	fs.Float64Var(&a.hz, "hz", 10, "--paint: repaints per second")
	fs.BoolVar(&a.paint, "paint", false, "e1, e2, e3: a dash below, repainted at --hz")
	fs.BoolVar(&a.hoverEv, "hover-events", false, "e3: ask for hover events (v=1); the program ignores them")
	fs.StringVar(&a.layoutPath, "layout", "", "write where things are to this file, as JSON")
	_ = fs.Parse(os.Args[2:])
	switch a.size {
	case "row", "half", "full":
	default:
		fmt.Fprintln(os.Stderr, "feelprog: --size is row, half or full")
		os.Exit(2)
	}
	var s scenario
	switch a.name {
	case "e1":
		s = &e1{}
	case "e2":
		s = &e2{}
	case "e3":
		s = &e3{}
	case "e6":
		s = newE6()
	default:
		usage()
	}
	os.Exit(a.run(s))
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: feelprog <e1|e2|e3|e6> [--size row|half|full] [--paint] [--hz N] [--row-px N] [--layout FILE]")
	fmt.Fprintln(os.Stderr, "       feelprog html <e1p|e2|e3|e6a|e6b> [--cols N] [--rows N] [--cell WxH] [--size S]")
	os.Exit(2)
}

func (a *app) run(s scenario) int {
	if !term.IsTerminal(0) {
		fmt.Fprintln(os.Stderr, "feelprog: stdin is not a terminal")
		return 2
	}
	openTrace()
	st, err := term.MakeRaw(0)
	if err != nil {
		fmt.Fprintln(os.Stderr, "feelprog:", err)
		return 1
	}
	a.restore = st
	a.cols, a.rows = winsize()
	if s.hotty(a) && !a.detect() {
		_ = term.Restore(0, st)
		fmt.Fprintln(os.Stderr, "feelprog: the terminal is not a hotty host")
		return 2
	}

	sigs := make(chan os.Signal, 4)
	signal.Notify(sigs, syscall.SIGWINCH, syscall.SIGTERM, syscall.SIGHUP, syscall.SIGINT, syscall.SIGQUIT)
	go a.signals(s, sigs)

	a.out.Lock()
	// The alternate screen, cleared; the cursor hidden where a surface is
	// the scenario, steady where e1 echoes.
	screen := "\x1b[?1049h\x1b[H\x1b[2J"
	if a.name == "e1" {
		screen += "\x1b[2 q\x1b[?12l"
	} else {
		screen += "\x1b[?25l"
	}
	a.write(screen)
	s.draw(a)
	a.writeLayout(s)
	a.out.Unlock()
	if tr != nil {
		tr.flush()
	}

	buf := make([]byte, 64<<10)
	for {
		n, err := os.Stdin.Read(buf)
		var t int64
		if tr != nil {
			t = now()
		}
		if n <= 0 {
			if err != nil && err != syscall.EINTR && err != syscall.EAGAIN {
				break
			}
			continue
		}
		in := a.parse(buf[:n], t)
		more := s.input(a, in)
		if tr != nil {
			a.stampRead(in)
			tr.flush()
		}
		if !more {
			break
		}
	}
	a.cleanup()
	return 0
}

// parse cuts hotty's messages out of a read; the rest is keys.
func (a *app) parse(b []byte, t int64) *input {
	in := &input{t: t, n: len(b)}
	segs := a.scan.Feed(b)
	if h := a.scan.Holding(); len(h) == 1 && !a.scan.InSequence() {
		segs = append(segs, a.scan.Flush()...) // a lone ESC: the Escape key
	}
	for _, seg := range segs {
		switch seg.Kind {
		case hotty.SegmentPass:
			in.pass = append(in.pass, seg.Data...)
		case hotty.SegmentOSC:
			if m, r := a.dec.Feed(string(seg.Data)); r == hotty.Complete {
				in.msgs = append(in.msgs, m)
			}
		}
	}
	return in
}

// stampRead writes prog.read: when the bytes arrived, how many, the key if
// they are one, and the hotty events among them.
func (a *app) stampRead(in *input) {
	args := []kv{num("n", in.n)}
	if len(in.msgs) == 0 {
		if keys := hotty.DecodeKeys(in.pass); len(keys) == 1 && keys[0] != "" {
			args = append(args, str("k", keys[0]))
		}
	}
	var kinds []string
	for _, m := range in.msgs {
		if e, ok := hotty.EventOf(m); ok {
			kinds = append(kinds, e.Kind)
		} else if r, ok := hotty.ReplyOf(m); ok {
			kinds = append(kinds, "reply:"+r.Re+":"+r.Code)
		}
	}
	if len(kinds) > 0 {
		args = append(args, str("e", strings.Join(kinds, ",")))
	}
	tr.instant("prog.read", "main", in.t, args...)
}

// caps folds the host's caps events into what it said (SPEC §4), and
// reports whether a cell's size changed.
func (a *app) capsEvents(in *input) bool {
	changed := false
	for _, m := range in.msgs {
		if e, ok := hotty.EventOf(m); ok && e.Kind == hotty.EventCaps && e.Changed != nil {
			was := a.caps.CellCSS
			a.caps = hotty.Merge(a.caps, *e.Changed)
			changed = changed || a.caps.CellCSS != was
		}
	}
	return changed
}

// write writes to the terminal; the caller holds a.out.
func (a *app) write(s string) {
	if a.closed || s == "" {
		return
	}
	_, _ = os.Stdout.WriteString(s)
}

// answer writes s as a stamped span (prog.write, prog.tick) on a track.
func (a *app) answer(stage, track, s string, extra ...kv) {
	if a.closed || s == "" {
		return
	}
	var t0 int64
	if tr != nil {
		t0 = now()
	}
	_, _ = os.Stdout.WriteString(s)
	if tr != nil {
		t1 := now()
		tr.span(stage, track, t0, t1-t0, append([]kv{num("n", len(s))}, extra...)...)
	}
}

// detect asks whether the terminal is a hotty host (SPEC §4), reading the
// terminal itself, and keeps the host's capabilities.
func (a *app) detect() bool {
	var d hotty.Detector
	a.scan.DA1 = true
	_, _ = os.Stdout.WriteString(d.Start(time.Now()))
	buf := make([]byte, 4096)
	for !d.Done {
		ms := int(time.Until(d.Deadline)/time.Millisecond) + 1
		fds := []unix.PollFd{{Fd: 0, Events: unix.POLLIN}}
		n, err := unix.Poll(fds, max(ms, 0))
		if err == unix.EINTR {
			continue
		}
		if err != nil {
			d.End(time.Now())
			break
		}
		if n > 0 {
			k, err := os.Stdin.Read(buf)
			if k <= 0 && err != nil {
				d.End(time.Now())
				break
			}
			for _, seg := range a.scan.Feed(buf[:k]) {
				switch seg.Kind {
				case hotty.SegmentOSC:
					if m, r := a.dec.Feed(string(seg.Data)); r == hotty.Complete {
						if rep, ok := hotty.ReplyOf(m); ok {
							d.Reply(rep, time.Now())
						}
					}
				case hotty.SegmentDA1:
					d.DA1(time.Now())
				}
			}
		}
		d.Tick(time.Now())
	}
	a.caps = d.Caps
	return d.State == hotty.Native
}

// signals redraws on a resize, and quits cleanly on the others.
func (a *app) signals(s scenario, sigs <-chan os.Signal) {
	for sig := range sigs {
		if sig != syscall.SIGWINCH {
			a.cleanup()
			os.Exit(0)
		}
		a.out.Lock()
		if !a.closed {
			cols, rows := winsize()
			if cols != a.cols || rows != a.rows {
				a.cols, a.rows = cols, rows
				if tr != nil {
					tr.instant("prog.resize", "main", now(), num("cols", cols), num("rows", rows))
				}
				s.draw(a)
				a.writeLayout(s)
			}
		}
		a.out.Unlock()
		if tr != nil {
			tr.flush()
		}
	}
}

// cleanup deletes the surfaces, leaves the alternate screen, restores the
// terminal and flushes the trace, once. A writer blocked on a terminal that
// no longer reads gets 300 ms, and then the terminal is left as it is.
func (a *app) cleanup() {
	a.once.Do(func() {
		locked := false
		for deadline := time.Now().Add(300 * time.Millisecond); time.Now().Before(deadline); {
			if locked = a.out.TryLock(); locked {
				break
			}
			time.Sleep(5 * time.Millisecond)
		}
		if locked {
			var b strings.Builder
			for _, s := range a.surfaces {
				b.WriteString(hotty.Del(s, hotty.Q(hotty.NoReply)))
			}
			b.WriteString("\x1b[0 q\x1b[?25h\x1b[?1049l")
			a.write(b.String())
			a.closed = true
			a.out.Unlock()
		}
		if a.restore != nil {
			_ = term.Restore(0, a.restore)
		}
		if tr != nil {
			tr.flush()
		}
	})
}

// winsize is the terminal's size in cells, 80×24 when it cannot be told.
func winsize() (cols, rows int) {
	ws, err := unix.IoctlGetWinsize(1, unix.TIOCGWINSZ)
	if err != nil || ws.Col == 0 || ws.Row == 0 {
		ws, err = unix.IoctlGetWinsize(0, unix.TIOCGWINSZ)
	}
	if err != nil || ws.Col == 0 || ws.Row == 0 {
		return 80, 24
	}
	return int(ws.Col), int(ws.Row)
}

// surfaceName names this process's surface.
func surfaceName(sc string) string {
	return hotty.SurfaceName(fmt.Sprintf("feel-%s-%d", sc, os.Getpid()))
}

// heightRows is the surface's rows for --size, below top rows kept for text.
func heightRows(size string, rows, top int) int {
	avail := max(rows-top, 1)
	switch size {
	case "row":
		return 1
	case "half":
		return min(max(rows/2, 1), avail)
	}
	return avail
}

// layout is where things are, for the rig: see the package comment.
type layout struct {
	Scenario string `json:"scenario"`
	Size     string `json:"size,omitempty"`
	// Seq counts the layouts this run wrote: the last is current.
	Seq int `json:"seq"`
	// Term is the terminal's size in cells: cols, rows.
	Term [2]int `json:"term"`
	// What the host said (SPEC §4); zero for e1 without --paint, which
	// asks nothing.
	CellCSS [2]float64 `json:"cell_css"`
	Scale   float64    `json:"scale"`
	CellDev [2]int     `json:"cell_dev"`
	Host    string     `json:"host,omitempty"`
	// The surface: its top-left cell, its size in cells and in CSS px.
	Surface      string     `json:"surface,omitempty"`
	SurfaceCell  [2]int     `json:"surface_cell"`
	SurfaceCells [2]int     `json:"surface_cells"`
	SurfaceCSS   [2]float64 `json:"surface_css"`
	// Rows are e3's rows (with --size row, its items side by side).
	Rows []rect `json:"rows,omitempty"`
	// Echo is the cells e1 echoes on.
	Echo *echoLayout `json:"echo,omitempty"`
	// Field is e2's text field.
	Field *fieldLayout `json:"field,omitempty"`
	// Docs are e6's documents' sizes.
	Docs *docsLayout `json:"docs,omitempty"`
	// Dash is --paint's surface, which changes on its own.
	Dash *dashLayout `json:"dash,omitempty"`
	// ToLogical is how a CSS px becomes a pointer's px.
	ToLogical string `json:"to_logical"`
}

// rect is a box in CSS px from the surface's top-left (x, y, w, h), its
// centre (cx, cy), and the centre in device px from the grid's top-left
// (dx, dy).
type rect struct {
	I  int     `json:"i"`
	X  float64 `json:"x"`
	Y  float64 `json:"y"`
	W  float64 `json:"w"`
	H  float64 `json:"h"`
	CX float64 `json:"cx"`
	CY float64 `json:"cy"`
	DX float64 `json:"dx"`
	DY float64 `json:"dy"`
}

type echoLayout struct {
	// Row and Rows: the echo is on these terminal rows, from 0, all
	// columns; Col is where typing starts, after the prompt.
	Row    int    `json:"row"`
	Rows   int    `json:"rows"`
	Col    int    `json:"col"`
	Prompt string `json:"prompt"`
	// Dev is the echo rows' box in device px from the grid's top-left:
	// x, y, w, h (with --paint, when the host told the cell's size).
	Dev [4]int `json:"dev"`
}

type fieldLayout struct {
	// FontRem is the field's font: the terminal's, times this.
	FontRem float64 `json:"font_rem"`
	// CharsFit is about how many characters the field shows before its
	// text scrolls, which repaints all of it at every key.
	CharsFit int `json:"chars_fit"`
}

type docsLayout struct {
	HTML [2]int `json:"html"` // each document's HTML, bytes
	Wire [2]int `json:"wire"` // each a=doc as written, bytes
}

const toLogical = "dev = (surface_cell.x*cell_dev.w + x*scale, surface_cell.y*cell_dev.h + y*scale); " +
	"logical = window_origin + (padding_dev + dev) / output_scale"

// cellDev is a cell's size in device px.
func (a *app) cellDev() (w, h int) {
	s := a.caps.Scale
	if s <= 0 {
		s = 1
	}
	return int(a.caps.CellCSS.W*s + 0.5), int(a.caps.CellCSS.H*s + 0.5)
}

// surfaceCSS is a surface's size in CSS px.
func (a *app) surfaceCSS(cols, rows int) (w, h float64) {
	return float64(cols) * a.caps.CellCSS.W, float64(rows) * a.caps.CellCSS.H
}

// writeLayout writes the layout: to --layout's file, replaced whole, or as
// a line to stderr when that is not the terminal.
func (a *app) writeLayout(s scenario) {
	a.seq++
	cw, ch := a.cellDev()
	l := layout{
		Scenario:  a.name,
		Size:      a.size,
		Seq:       a.seq,
		Term:      [2]int{a.cols, a.rows},
		CellCSS:   [2]float64{a.caps.CellCSS.W, a.caps.CellCSS.H},
		Scale:     a.caps.Scale,
		CellDev:   [2]int{cw, ch},
		Host:      strings.TrimSpace(a.caps.Host + " " + a.caps.Version),
		ToLogical: toLogical,
	}
	s.layout(a, &l)
	b, err := json.Marshal(l)
	if err != nil {
		return
	}
	if a.layoutPath == "" {
		if !term.IsTerminal(2) {
			_, _ = os.Stderr.Write(append(b, '\n'))
		}
		return
	}
	tmp := a.layoutPath + ".tmp"
	if os.WriteFile(tmp, append(b, '\n'), 0o644) == nil {
		_ = os.Rename(tmp, a.layoutPath)
	}
}

// fillRects gives each rect its centre, and the centre in device px from
// the grid's top-left, for a surface at cell (col, row).
func (a *app) fillRects(rs []rect, col, row int) {
	cw, ch := a.cellDev()
	s := a.caps.Scale
	for i := range rs {
		r := &rs[i]
		r.CX, r.CY = r.X+r.W/2, r.Y+r.H/2
		r.DX = float64(col*cw) + r.CX*s
		r.DY = float64(row*ch) + r.CY*s
	}
}
