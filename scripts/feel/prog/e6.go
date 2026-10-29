package main

import (
	hotty "github.com/neuroplastio/hotty-go"
)

// e6 is a whole-document swap, as a storybook's switch is: each key sends
// the surface a new document of about 60 KB (a=doc), the two pages in
// turn, whose tops differ in colour, title and canvas. Both commands are
// made once at the start, so a key costs only their write (prog.write,
// a.doc: which page, a.html: its HTML's bytes).
type e6 struct {
	name  string
	html  [2]int
	cmds  [2]string
	cur   int
	srows int
	drawn bool
}

func newE6() *e6 {
	e := &e6{name: surfaceName("e6")}
	for v := range 2 {
		h := storybook(v)
		e.html[v] = len(h)
		e.cmds[v] = hotty.Doc(e.name, h)
	}
	return e
}

func (e *e6) hotty(*app) bool { return true }

func (e *e6) draw(a *app) {
	var b string
	if !e.drawn {
		e.drawn = true
		a.surfaces = append(a.surfaces, e.name)
		b = e.cmds[0]
	}
	e.srows = heightRows(a.size, a.rows, 0)
	a.write(b + hotty.PlaceAt(e.name, 0, 0, hotty.Placement{Cols: a.cols, Rows: e.srows}))
}

func (e *e6) input(a *app, in *input) bool {
	a.out.Lock()
	defer a.out.Unlock()
	for _, k := range hotty.DecodeKeys(in.pass) {
		switch k {
		case "":
		case "ctrl+c", "q":
			return false
		default:
			e.cur ^= 1
			a.answer("prog.write", "main", e.cmds[e.cur], num("doc", e.cur), num("html", e.html[e.cur]))
		}
	}
	return true
}

func (e *e6) layout(a *app, l *layout) {
	w, h := a.surfaceCSS(a.cols, e.srows)
	l.Surface = e.name
	l.SurfaceCells = [2]int{a.cols, e.srows}
	l.SurfaceCSS = [2]float64{w, h}
	l.Docs = &docsLayout{HTML: e.html, Wire: [2]int{len(e.cmds[0]), len(e.cmds[1])}}
}
