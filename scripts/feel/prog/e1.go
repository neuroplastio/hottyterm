package main

// e1 is a shell's echo, text only: raw mode, and each byte read written
// back as a line editor does. The echo is always on row 0: after the
// prompt, printable bytes are echoed; Enter, or a line that reaches the
// last column, returns the carriage and clears the row for a new prompt
// (CR, EL, prompt), so the rig's pixels for an echo are always row 0's.
// Backspace erases one character back to the prompt; other control bytes
// and escape sequences (arrows, F-keys) are dropped. Ctrl-C or Ctrl-D
// quits: q is a letter like any other here, and the rig types it.
//
// With --paint, a dash below the echo, from row paintTop down (dash.go).
// It tests whether an echo waits behind hotty work on the terminal's pty
// thread.
type e1 struct {
	col  int // the cursor's column on row 0
	esc  int // where an escape sequence being dropped is (escNone, …)
	dash dash
}

const (
	prompt   = "$ "
	paintTop = 3 // the dash's first row: rows 1 and 2 stay blank
)

// The states of the dropped escape sequence.
const (
	escNone = iota
	escStart
	escCSI
	escSS3
	escString
	escStringEsc
)

func (e *e1) hotty(a *app) bool { return a.paint }

func (e *e1) draw(a *app) {
	e.col = len(prompt)
	b := "\x1b[H\x1b[2K" + prompt
	if a.paint {
		b += e.dash.draw(a, paintTop)
	}
	// The cursor back after the prompt (PlaceAt restores it too).
	b += "\x1b[1;" + itoa(e.col+1) + "H"
	a.write(b)
	if a.paint {
		e.dash.start(a)
	}
}

func (e *e1) input(a *app, in *input) bool {
	a.out.Lock()
	defer a.out.Unlock()
	var out []byte
	reset := func() {
		out = append(out, "\r\x1b[2K"+prompt...)
		e.col = len(prompt)
	}
	for _, c := range in.pass {
		switch e.esc {
		case escStart:
			switch c {
			case '[':
				e.esc = escCSI
			case 'O':
				e.esc = escSS3
			case ']', 'P', '_', '^', 'X':
				e.esc = escString
			default:
				e.esc = escNone // Alt and a key: dropped
			}
			continue
		case escCSI:
			if c >= 0x40 && c <= 0x7e {
				e.esc = escNone
			}
			continue
		case escSS3:
			e.esc = escNone
			continue
		case escString:
			if c == 0x07 {
				e.esc = escNone
			} else if c == 0x1b {
				e.esc = escStringEsc
			}
			continue
		case escStringEsc:
			e.esc = escNone
			if c != '\\' {
				e.esc = escString
			}
			continue
		}
		switch {
		case c == 0x03 || c == 0x04: // Ctrl-C, Ctrl-D; q is echoed, as a shell does
			if len(out) > 0 {
				a.answer("prog.write", "main", string(out))
			}
			return false
		case c == 0x1b:
			e.esc = escStart
		case c == '\r' || c == '\n':
			reset()
		case c == 0x7f || c == 0x08:
			if e.col > len(prompt) {
				out = append(out, "\b \b"...)
				e.col--
			}
		case c >= 0x20 && c < 0x7f, c >= 0x80:
			if c < 0x80 || c >= 0xc0 { // a character's first byte takes a column
				if e.col >= a.cols-1 {
					reset()
				}
				e.col++
			}
			out = append(out, c)
		}
	}
	if e.esc == escStart {
		e.esc = escNone // a lone ESC that ended the read: the Escape key
	}
	if len(out) > 0 {
		a.answer("prog.write", "main", string(out))
	}
	return true
}

func (e *e1) layout(a *app, l *layout) {
	cw, ch := a.cellDev()
	l.Echo = &echoLayout{Row: 0, Rows: 1, Col: len(prompt), Prompt: prompt, Dev: [4]int{0, 0, a.cols * cw, ch}}
	if !a.paint {
		l.Size = ""
		return
	}
	l.Dash = e.dash.layout(a)
	l.Surface = l.Dash.Surface
	l.SurfaceCell = l.Dash.Cell
	l.SurfaceCells = l.Dash.Cells
	l.SurfaceCSS = l.Dash.CSS
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}
