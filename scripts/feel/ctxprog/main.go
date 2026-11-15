// Command ctxprog is the program of ctxmenu.sh (docs/feel.md): one hotty
// document filling the window on the alternate screen, scroll=1 as
// hotty-pot's Tasks has it, rows that take a click (data-on="click") and
// none that take a secondary press, so a right press is hottyterm's own
// (its context menu). Mouse reporting is off.
//
//	ctxprog --event-log FILE
//
// Every event the program hears is a line in FILE ("<ms> event click t=r7"),
// and "alive" once a second, so a log whose events stop is the terminal's
// doing, not the program's. q or Ctrl-C quits.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	uv "github.com/charmbracelet/ultraviolet"

	"neuroplast.io/hotty-go"
	"neuroplast.io/hotty-go/hottyterm"
)

func main() {
	logPath := flag.String("event-log", "", "write what the program hears to this file")
	flag.Parse()
	logf, err := os.OpenFile(*logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ctxprog:", err)
		os.Exit(1)
	}
	log := func(format string, args ...any) {
		fmt.Fprintf(logf, "%d %s\n", time.Now().UnixMilli(), fmt.Sprintf(format, args...))
	}
	t, err := hottyterm.Open("ctx")
	if err != nil {
		fmt.Fprintln(os.Stderr, "ctxprog:", err)
		os.Exit(1)
	}
	defer t.Close()
	restore, err := t.Raw()
	if err != nil {
		fmt.Fprintln(os.Stderr, "ctxprog:", err)
		os.Exit(1)
	}
	defer restore()
	ctx := context.Background()
	if !t.Detect(ctx) {
		fmt.Fprintln(os.Stderr, "ctxprog: the terminal is not a hotty host")
		os.Exit(2)
	}
	sz := t.Size()
	name := t.Surface("ctx")
	var b strings.Builder
	b.WriteString(`<style>
html,body{margin:0;background:#0d1117;color:#c9d1d9;font:15px/1.3 sans-serif}
ul{margin:0;padding:0;list-style:none}
li{box-sizing:border-box;height:40px;padding:0 16px;display:flex;align-items:center;background:#161b22;border-bottom:1px solid #0d1117}
li:nth-child(even){background:#1c2330}
li:hover{background:#1f6feb;color:#fff}
</style><ul>`)
	for i := range 200 {
		fmt.Fprintf(&b, `<li id=r%d data-on="click">Task %03d, a row that takes a click</li>`, i, i)
	}
	b.WriteString("</ul>")
	_ = t.Send("\x1b[?1049h\x1b[H\x1b[2J\x1b[?25l",
		hotty.Doc(name, b.String(), hotty.Scroll(hotty.ScrollVertical)),
		hotty.PlaceAt(name, 0, 0, hotty.Placement{Cols: sz.Cols, Rows: sz.Rows}))
	defer t.Send("\x1b[?25h\x1b[?1049l", hotty.Del(name))
	log("up %dx%d", sz.Cols, sz.Rows)

	go func() {
		for range time.Tick(time.Second) {
			log("alive")
		}
	}()
	for ev := range t.Events(ctx) {
		switch e := ev.(type) {
		case hottyterm.Message:
			if m, ok := hotty.EventOf(e.Message); ok && m.Kind != hotty.EventCaps {
				log("event %s t=%s", m.Kind, m.Target)
			}
		case uv.KeyPressEvent:
			log("key %s", e.String())
			if e.String() == "q" || e.String() == "ctrl+c" {
				return
			}
		}
	}
}
