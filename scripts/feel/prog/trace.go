package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"sync"
)

// tracer writes the stamps of trace format hotty/1 (docs/trace.md) to
// $HOTTY_TRACE/prog-<pid>.jsonl. tr is nil when HOTTY_TRACE is unset or
// empty, and every call site tests it first: off costs one branch, with no
// clock read and nothing built.
type tracer struct {
	mu  sync.Mutex
	f   *os.File
	buf []byte
}

var tr *tracer

// openTrace opens the trace file and writes its header, when HOTTY_TRACE
// names a directory.
func openTrace() {
	dir := os.Getenv("HOTTY_TRACE")
	if dir == "" {
		return
	}
	pid := os.Getpid()
	f, err := os.OpenFile(filepath.Join(dir, fmt.Sprintf("prog-%d.jsonl", pid)),
		os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		fmt.Fprintln(os.Stderr, "feelprog: no trace:", err)
		return
	}
	t := &tracer{f: f}
	t.buf = fmt.Appendf(t.buf, `{"trace":"hotty/1","proc":"prog","pid":%d,"clock":%q}`+"\n", pid, clockName)
	t.flush()
	tr = t
}

// kv is one of a line's arguments: a number, or a string when s is set.
type kv struct {
	k   string
	s   string
	n   int64
	str bool
}

func num(k string, n int) kv { return kv{k: k, n: int64(n)} }
func str(k, s string) kv     { return kv{k: k, s: s, str: true} }
func (t *tracer) instant(name, track string, at int64, a ...kv) {
	t.line(name, track, at, -1, a)
}

// span is a span's line, written at its end: its start and duration.
func (t *tracer) span(name, track string, start, dur int64, a ...kv) {
	t.line(name, track, start, dur, a)
}

func (t *tracer) line(name, track string, at, dur int64, a []kv) {
	t.mu.Lock()
	defer t.mu.Unlock()
	b := append(t.buf, `{"t":`...)
	b = strconv.AppendInt(b, at, 10)
	b = append(b, `,"n":`...)
	b = appendJSON(b, name)
	if dur >= 0 {
		b = append(b, `,"dur":`...)
		b = strconv.AppendInt(b, dur, 10)
	}
	b = append(b, `,"tr":`...)
	b = appendJSON(b, track)
	if len(a) > 0 {
		b = append(b, `,"a":{`...)
		for i, x := range a {
			if i > 0 {
				b = append(b, ',')
			}
			b = appendJSON(b, x.k)
			b = append(b, ':')
			if x.str {
				b = appendJSON(b, x.s)
			} else {
				b = strconv.AppendInt(b, x.n, 10)
			}
		}
		b = append(b, '}')
	}
	t.buf = append(b, "}\n"...)
}

// flush writes the whole lines buffered so far, in one write: after each
// answer, each tick, and at exit.
func (t *tracer) flush() {
	t.mu.Lock()
	defer t.mu.Unlock()
	if len(t.buf) == 0 {
		return
	}
	_, _ = t.f.Write(t.buf)
	t.buf = t.buf[:0]
}

// appendJSON appends s as a JSON string.
func appendJSON(b []byte, s string) []byte {
	const hex = "0123456789abcdef"
	b = append(b, '"')
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c == '"' || c == '\\':
			b = append(b, '\\', c)
		case c < 0x20:
			b = append(b, '\\', 'u', '0', '0', hex[c>>4], hex[c&15])
		default:
			b = append(b, c)
		}
	}
	return append(b, '"')
}
