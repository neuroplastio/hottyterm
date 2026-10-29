package main

import (
	hotty "github.com/neuroplastio/hotty-go"
)

// e2 is typing in a host text field: a surface holding one
// <input type=text>, focused with a=focus, so the host does the typing
// and the program hears only what the field does not use (a change when
// it commits, which it ignores). Ctrl-C and Escape quit: the field types
// q. Only what reaches the program is stamped. With --paint, a dash fills
// the rows below the field's surface, a row apart (dash.go).
type e2 struct {
	name  string
	srows int
	dash  dash
}

func (e *e2) hotty(*app) bool { return true }

func (e *e2) draw(a *app) {
	var b string
	if e.name == "" {
		e.name = surfaceName("e2")
		a.surfaces = append(a.surfaces, e.name)
		b = hotty.Doc(e.name, e2Doc(a.size))
	}
	e.srows = heightRows(a.size, a.rows, 0)
	b += hotty.PlaceAt(e.name, 0, 0, hotty.Placement{Cols: a.cols, Rows: e.srows})
	if a.paint && e.srows+1 < a.rows {
		b += e.dash.draw(a, e.srows+1)
	}
	a.write(b + hotty.Focus(e.name, "f"))
	if a.paint && e.dash.name != "" {
		e.dash.start(a)
	}
}

func (e *e2) input(a *app, in *input) bool {
	for _, k := range hotty.DecodeKeys(in.pass) {
		if k == "ctrl+c" || k == "escape" || k == "q" {
			return false
		}
	}
	if a.capsEvents(in) {
		a.out.Lock()
		a.writeLayout(e)
		a.out.Unlock()
	}
	return true
}

func (e *e2) layout(a *app, l *layout) {
	w, h := a.surfaceCSS(a.cols, e.srows)
	l.Surface = e.name
	l.SurfaceCells = [2]int{a.cols, e.srows}
	l.SurfaceCSS = [2]float64{w, h}
	rem := e2FontRem(a.size)
	// The terminal's font advances a cell per character; the padding is
	// a character on each side.
	l.Field = &fieldLayout{FontRem: rem, CharsFit: max(int(float64(a.cols)/rem)-2, 0)}
	l.Dash = e.dash.layout(a)
}
