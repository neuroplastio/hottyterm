package main

import (
	hotty "github.com/neuroplastio/hotty-go"
)

// e3 is the pointer across a list whose rows have :hover: a surface filling
// --size, rows of --row-px CSS px (with --size row, eight items side by
// side), each one's background changing on :hover and nothing else. The
// host does the hover; with --hover-events the program also asks for
// hover events (v=1) and ignores them. The layout gives the rows'
// geometry (see the package comment for turning it into pointer px).
// With --paint, a dash fills the rows below the list, a row apart
// (dash.go).
type e3 struct {
	name  string
	srows int
	items []rect
	dash  dash
}

func (e *e3) hotty(*app) bool { return true }

func (e *e3) draw(a *app) {
	if e.name == "" {
		e.name = surfaceName("e3")
		a.surfaces = append(a.surfaces, e.name)
	}
	e.srows = heightRows(a.size, a.rows, 0)
	w, h := a.surfaceCSS(a.cols, e.srows)
	e.items = e3Items(a.size, w, h, a.rowPx)
	a.fillRects(e.items, 0, 0)
	p := hotty.Placement{Cols: a.cols, Rows: e.srows}
	if a.hoverEv {
		p.Hover = hotty.On
	}
	b := hotty.Doc(e.name, e3Doc(a.size, e.items, a.rowPx)) + hotty.PlaceAt(e.name, 0, 0, p)
	if a.paint && e.srows+1 < a.rows {
		b += e.dash.draw(a, e.srows+1)
	}
	a.write(b)
	if a.paint && e.dash.name != "" {
		e.dash.start(a)
	}
}

func (e *e3) input(a *app, in *input) bool {
	for _, k := range hotty.DecodeKeys(in.pass) {
		if k == "ctrl+c" || k == "q" {
			return false
		}
	}
	if a.capsEvents(in) { // a cell's size changed: the rows that fit too
		a.out.Lock()
		e.draw(a)
		a.writeLayout(e)
		a.out.Unlock()
	}
	return true
}

func (e *e3) layout(a *app, l *layout) {
	w, h := a.surfaceCSS(a.cols, e.srows)
	l.Surface = e.name
	l.SurfaceCells = [2]int{a.cols, e.srows}
	l.SurfaceCSS = [2]float64{w, h}
	l.Rows = e.items
	l.Dash = e.dash.layout(a)
}
