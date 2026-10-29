package main

import (
	"fmt"
	"html"
	"math"
	"strings"

	hotty "github.com/neuroplastio/hotty-go"
)

// The scenarios' documents. Each is a pure function of its arguments, so
// a run draws the same pixels every time, and `feelprog html` prints them
// for `hotty render`. No transitions, animations or carets: nothing moves
// unless the rig moves it.

// e2Doc is one text field filling the surface. Its font is the terminal's
// (rem), twice its size unless the surface is one row tall, so a typed
// character covers 2×2 cells. The caret is transparent: hotty-blitz blinks
// it for 10 s after each key, which would change pixels the rig did not.
func e2Doc(size string) string {
	return `<style>
html,body{margin:0;height:100%;overflow:hidden;background:#0f1419}
#f{display:block;box-sizing:border-box;width:100%;height:100%;margin:0;padding:0 1ch;border:0;outline:none;
font:` + fmt.Sprint(e2FontRem(size)) + `rem/1 var(--hotty-font),monospace;color:#e6edf3;background:#0f1419;caret-color:transparent}
#f:focus,#f:focus-visible{outline:none;border:0}
</style><input id=f type=text autocomplete=off spellcheck=false aria-label=Type>`
}

// e2FontRem is the field's font size in rem: the terminal's font times it.
func e2FontRem(size string) float64 {
	if size == "row" {
		return 1
	}
	return 2
}

// e3Items are e3's rows in CSS px from the surface's top-left: rows of
// rowPx down the surface's width, as many as fit whole; with --size row,
// whose surface is shorter than a row, eight items side by side across
// it, each its full height.
func e3Items(size string, w, h float64, rowPx int) []rect {
	var rs []rect
	if size == "row" {
		iw := math.Floor(w / 8)
		for i := range 8 {
			rs = append(rs, rect{I: i, X: float64(i) * iw, Y: 0, W: iw, H: h})
		}
		return rs
	}
	n := max(int(h)/rowPx, 1)
	for i := range n {
		rs = append(rs, rect{I: i, X: 0, Y: float64(i * rowPx), W: w, H: float64(rowPx)})
	}
	return rs
}

var regions = []string{"us-east-1", "eu-west-2", "ap-south-1", "us-west-2", "eu-central-1", "sa-east-1"}
var services = []string{"orders-api", "billing", "search", "auth", "ingest", "notify", "reports", "gateway", "media", "ledger"}

// e3Doc is the list: each row's background changes on :hover, and only
// that changes.
func e3Doc(size string, items []rect, rowPx int) string {
	var b strings.Builder
	b.WriteString(`<style>
html,body{margin:0;height:100%;overflow:hidden;background:#0d1117;color:#c9d1d9;font:15px/1.3 sans-serif}
ul{margin:0;padding:0;list-style:none}
li{box-sizing:border-box;margin:0;display:flex;align-items:center;background:#161b22;transition:none;cursor:default;overflow:hidden;white-space:nowrap}
li:nth-child(even){background:#1c2330}
li:hover{background:#1f6feb;color:#ffffff}
li b{font-weight:600}
`)
	if size == "row" {
		fmt.Fprintf(&b, `ul{display:flex;height:100%%}
li{flex:none;height:100%%;width:%gpx;padding:0 8px;border-right:1px solid #0d1117;font-size:13px}
`, items[0].W)
	} else {
		fmt.Fprintf(&b, `li{height:%dpx;padding:0 16px;gap:16px;border-bottom:1px solid #0d1117}
li b{width:7ch}
li span{color:#8b949e}
li:hover span{color:#dbe9ff}
li .n{margin-left:auto;font-family:var(--hotty-font),monospace;color:inherit}
`, rowPx)
	}
	b.WriteString("</style><ul>")
	for _, r := range items {
		if size == "row" {
			fmt.Fprintf(&b, `<li id=r%d><b>Item %02d</b></li>`, r.I, r.I)
			continue
		}
		fmt.Fprintf(&b, `<li id=r%d><b>Row %02d</b><span>%s · %s</span><span class=n>%d.%d ms</span></li>`,
			r.I, r.I, services[r.I%len(services)], regions[r.I%len(regions)], 3+r.I*7%40, r.I*3%10)
	}
	b.WriteString("</ul>")
	return b.String()
}

// paintGrid is how many of e1 --paint's cards fit: side by side in one
// row, or a grid.
func paintGrid(size string, w, h float64) (cols, rows int) {
	if size == "row" {
		return max(int(w)/150, 1), 1
	}
	return max(int(w-8)/208, 1), max(int(h-8)/96, 1)
}

// paintDoc is e1 --paint's dash: cards with a number and a bar, n of them,
// which ticks change a few at a time (paintTick).
func paintDoc(size string, w, h float64) (string, int) {
	cols, rows := paintGrid(size, w, h)
	n := cols * rows
	var b strings.Builder
	b.WriteString(`<style>
html,body{margin:0;height:100%;overflow:hidden;background:#0b0f14;color:#c9d1d9;font:13px/1.2 sans-serif}
.g{display:grid;gap:8px;padding:8px}
.c{box-sizing:border-box;background:#151b23;border:1px solid #232b36;border-radius:6px;padding:8px 10px;overflow:hidden}
.c span{display:block;color:#7d8590;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.c b{display:block;font:600 22px/1.2 var(--hotty-font),monospace;color:#e6edf3}
.bar{display:block;height:8px;border-radius:4px;background:#232b36;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;width:calc(var(--p,0)*1%);background:linear-gradient(90deg,#2ea043,#d29922,#f85149)}
`)
	if size == "row" {
		b.WriteString(`.g{display:flex;gap:0;padding:0;height:100%}
.c{flex:none;width:150px;height:100%;display:flex;align-items:center;gap:6px;padding:0 6px;border-radius:0;border-width:0 1px 0 0}
.c span{font-size:10px}
.c b{font-size:13px;width:4.5ch}
.bar{flex:1;margin:0}
`)
	} else {
		fmt.Fprintf(&b, ".g{grid-template-columns:repeat(%d,minmax(0,1fr));grid-auto-rows:88px}\n", cols)
	}
	b.WriteString(`</style><div class=g>`)
	for j := range n {
		v, p := paintValue(0, j)
		fmt.Fprintf(&b, `<div class=c><span>%s</span><b id=v%d>%s</b><i class=bar><i id=b%d style="--p:%d"></i></i></div>`,
			services[j%len(services)], j, v, j, p)
	}
	b.WriteString(`</div>`)
	return b.String(), n
}

// paintValue is card j's number and bar at tick k: a hash, so every run
// paints the same.
func paintValue(k, j int) (string, int) {
	x := uint32(k)*2654435761 ^ uint32(j)*40503 ^ 0x9e3779b9
	x ^= x >> 15
	x *= 0x2c1b3c6d
	x ^= x >> 12
	return fmt.Sprintf("%d.%d", x%1000, (x>>10)%10), int((x >> 16) % 101)
}

// paintTick is tick k's delta: six cards spread across the surface get a
// new number and bar.
func paintTick(name string, n, k int) string {
	m := min(6, n)
	ops := make([]hotty.Op, 0, 2*m)
	for i := range m {
		j := (k*7 + i*n/m) % n
		v, p := paintValue(k, j)
		ops = append(ops, hotty.OpText(fmt.Sprintf("v%d", j), v), hotty.OpVar(fmt.Sprintf("b%d", j), "p", fmt.Sprint(p)))
	}
	return hotty.Delta(name, ops)
}

// The storybook pages (e6): a storybook's docs page for one component,
// with a header, a sidebar, a banner, a canvas, cards, prose and a props
// table that fills it out to about 60 KB.

const storyTarget = 60000

var words = strings.Fields(`account action active add alert align amount archive arrow asset audit
badge banner basic batch billing border bounded branch breadcrumb build bundle button cache calendar
canvas caption card cell change channel chart check chip cluster code collapse color column commit
compact component config content context control copy count cursor dashboard data date default delete
density deploy detail dialog disabled divider dock draft drawer dropdown edge editor empty error event
expand export field filter focus footer form frame grid group header height helper hidden history hover
icon image index inline input inset item label layout legend level limit link list loading local menu
message meta metric modal mode muted name navigation node notice number offset option order outline
overlay padding page panel pattern pending picker pill placeholder popover primary progress prop query
radio range record region release render resize result review route row scale schema scroll search
secondary section select selected shadow sheet size slider slot sort source spacing stack state status
step story style surface switch tab table tag task text theme timeline title toast toggle token toolbar
tooltip track tree trigger type update upload user value variant view visible warning width window wrap zone`)

var groups = []struct {
	name  string
	items []string
}{
	{"Inputs", []string{"Button", "Checkbox", "Combobox", "Date picker", "Radio group", "Select", "Slider", "Switch", "Text field"}},
	{"Data display", []string{"Avatar", "Badge", "Card", "Data table", "Description list", "Stat", "Tag", "Timeline", "Tree view"}},
	{"Feedback", []string{"Alert", "Banner", "Dialog", "Progress", "Skeleton", "Spinner", "Toast", "Tooltip"}},
	{"Navigation", []string{"Breadcrumbs", "Command menu", "Link", "Menu", "Pagination", "Sidebar", "Tabs"}},
	{"Layout", []string{"Box", "Divider", "Grid", "Split pane", "Stack", "Sticky header"}},
}

type story struct {
	title, group, desc, c1, c2, accent, accentBg string
	seed                                         uint32
}

var stories = [2]story{
	{"Button", "Inputs", "Buttons start an action: a primary one for the main step of a page, secondary and ghost ones for the rest, and a danger one for what cannot be undone.",
		"#1f6feb", "#8957e5", "#58a6ff", "#1f6feb33", 1},
	{"Data table", "Data display", "A data table shows records in rows and columns, sorted, filtered and paged, with a selection that bulk actions apply to.",
		"#bf8700", "#cf222e", "#f2cc60", "#bf870033", 2},
}

type rng uint32

func (r *rng) next() uint32 {
	x := uint32(*r)
	x ^= x << 13
	x ^= x >> 17
	x ^= x << 5
	*r = rng(x)
	return x
}
func (r *rng) word() string   { return words[r.next()%uint32(len(words))] }
func (r *rng) intn(n int) int { return int(r.next() % uint32(n)) }

func (r *rng) sentence(lo, hi int) string {
	n := lo + r.intn(hi-lo+1)
	ws := make([]string, n)
	for i := range ws {
		ws[i] = r.word()
	}
	ws[0] = strings.ToUpper(ws[0][:1]) + ws[0][1:]
	return strings.Join(ws, " ") + "."
}

func (r *rng) titleWords(n int) string {
	ws := make([]string, n)
	for i := range ws {
		w := r.word()
		ws[i] = strings.ToUpper(w[:1]) + w[1:]
	}
	return strings.Join(ws, " ")
}

// storybook is page v (0 or 1): their tops differ in colour, title and
// canvas, and the sidebar selects another item.
func storybook(v int) string {
	s := stories[v]
	r := rng(s.seed * 2654435761)
	var b strings.Builder
	fmt.Fprintf(&b, `<!doctype html><html><head><meta charset=utf-8><title>%s · Storybook</title><style>
:root{--c1:%s;--c2:%s;--accent:%s;--accent-bg:%s}
*{box-sizing:border-box}
html,body{margin:0;height:100%%;overflow:hidden}
body{background:#0d1117;color:#c9d1d9;font:14px/1.45 system-ui,sans-serif}
.top{display:flex;align-items:center;gap:20px;height:48px;padding:0 20px;background:#010409;border-bottom:1px solid #30363d}
.logo{font-weight:700;color:#fff;letter-spacing:.02em;white-space:nowrap}
.logo i{display:inline-block;width:14px;height:14px;border-radius:3px;background:var(--accent);margin-right:8px;vertical-align:-2px}
.top nav{white-space:nowrap}
.top nav a{color:#8b949e;text-decoration:none;margin-right:16px}
.top nav a.on{color:#fff}
.find{margin-left:auto;width:240px;height:28px;border:1px solid #30363d;border-radius:6px;color:#6e7681;padding:4px 10px;font-size:13px;white-space:nowrap}
.ver{color:#6e7681;font-size:12px;white-space:nowrap}
.wrap{display:flex;height:calc(100%% - 48px)}
.side{width:240px;flex:none;overflow:hidden;border-right:1px solid #21262d;padding:12px 0}
.side h4{margin:12px 20px 4px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6e7681}
.side a{display:block;padding:3px 20px 3px 28px;color:#adbac7;text-decoration:none;font-size:13px}
.side a.sel{background:var(--accent-bg);color:#fff;border-left:3px solid var(--accent);padding-left:25px}
main{flex:1;min-width:0;overflow:hidden;padding:0 0 40px}
.banner{padding:24px 32px 0;background:linear-gradient(120deg,var(--c1),var(--c2));color:#fff}
.crumb{font-size:12px;opacity:.85}
.banner h1{margin:6px 0 4px;font-size:34px;line-height:1.15}
.banner p{margin:0 0 18px;max-width:720px;opacity:.92}
.tabs{display:flex;gap:4px}
.tabs span{padding:8px 16px;border-radius:6px 6px 0 0;background:rgba(0,0,0,.2)}
.tabs span.on{background:#0d1117;color:#fff}
.canvas{margin:24px 32px;padding:24px;border:1px dashed #30363d;border-radius:8px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:#010409}
.btn{display:inline-block;padding:8px 16px;border-radius:6px;font-weight:600;font-size:13px;border:1px solid transparent;color:#fff}
.btn.p{background:#1f6feb}.btn.s{background:#21262d;border-color:#30363d;color:#c9d1d9}
.btn.d{background:#da3633}.btn.g{background:transparent;color:#58a6ff}
.btn.sm{padding:4px 10px;font-size:12px}.btn.lg{padding:12px 22px;font-size:15px}.btn.off{opacity:.45}
.mini{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;width:100%%;font-size:13px;border:1px solid #30363d;border-radius:6px;overflow:hidden}
.mini div{padding:7px 12px;border-bottom:1px solid #21262d}
.mini .h{background:#161b22;color:#8b949e;font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin:0 32px 24px}
.card{border:1px solid #30363d;border-radius:8px;padding:14px 16px;background:#161b22}
.card h3{margin:0 0 6px;font-size:15px;color:#e6edf3}
.card p{margin:0 0 10px;color:#8b949e;font-size:13px}
.card footer{display:flex;justify-content:space-between;color:#6e7681;font-size:12px;margin-top:10px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;margin-right:6px;background:#21262d;color:#adbac7}
.tag.ok{background:#12361f;color:#56d364}.tag.warn{background:#3b2300;color:#e3b341}.tag.bad{background:#3c1618;color:#f85149}
h2{margin:28px 32px 12px;font-size:20px;color:#e6edf3}
.prose{margin:0 32px;max-width:780px;color:#adbac7}
.prose p{margin:0 0 12px}
table{border-collapse:collapse;margin:0 32px 24px;width:calc(100%% - 64px);font-size:13px}
th{text-align:left;color:#8b949e;font-weight:600;border-bottom:1px solid #30363d;padding:8px 10px}
td{border-bottom:1px solid #21262d;padding:6px 10px;vertical-align:top}
td code{font-family:var(--hotty-font),monospace;color:var(--accent);font-size:12px}
tr:nth-child(even) td{background:#0f141b}
</style></head><body>
`, html.EscapeString(s.title), s.c1, s.c2, s.accent, s.accentBg)

	b.WriteString(`<header class=top><span class=logo><i></i>Storybook</span><nav>`)
	for i, n := range []string{"Docs", "Components", "Tokens", "Patterns", "Changelog"} {
		cls := ""
		if i == 1 {
			cls = ` class=on`
		}
		fmt.Fprintf(&b, `<a href="#%s"%s>%s</a>`, strings.ToLower(n), cls, n)
	}
	b.WriteString(`</nav><span class=find>Find components…  /</span><span class=ver>v8.3.1</span></header><div class=wrap><aside class=side>`)
	for _, g := range groups {
		fmt.Fprintf(&b, `<h4>%s</h4>`, html.EscapeString(g.name))
		for _, it := range g.items {
			cls := ""
			if it == s.title {
				cls = ` class=sel`
			}
			fmt.Fprintf(&b, `<a href="#%s"%s>%s</a>`, strings.ReplaceAll(strings.ToLower(it), " ", "-"), cls, html.EscapeString(it))
		}
	}
	fmt.Fprintf(&b, `</aside><main><section class=banner><div class=crumb>Components / %s / %s</div><h1>%s</h1><p>%s</p>`+
		`<div class=tabs><span class=on>Canvas</span><span>Docs</span><span>Controls</span><span>Accessibility</span></div></section>`,
		html.EscapeString(s.group), html.EscapeString(s.title), html.EscapeString(s.title), html.EscapeString(s.desc))

	b.WriteString(`<section class=canvas>`)
	if v == 0 {
		b.WriteString(`<span class="btn p">Primary</span><span class="btn s">Secondary</span><span class="btn d">Delete</span>` +
			`<span class="btn g">Ghost</span><span class="btn p sm">Small</span><span class="btn p lg">Large</span><span class="btn p off">Disabled</span>`)
	} else {
		b.WriteString(`<div class=mini><div class=h>Service</div><div class=h>Region</div><div class=h>p50</div><div class=h>Status</div>`)
		for i := range 4 {
			fmt.Fprintf(&b, `<div>%s</div><div>%s</div><div>%d ms</div><div><span class="tag ok">healthy</span></div>`,
				services[i], regions[i], 8+i*5)
		}
		b.WriteString(`</div>`)
	}
	b.WriteString(`</section><h2>Examples</h2><section class=cards>`)
	tags := []string{"ok", "warn", "bad", ""}
	for i := range 36 {
		t := tags[r.intn(len(tags))]
		fmt.Fprintf(&b, `<article class=card><h3>%s</h3><p>%s</p><span class="tag %s">%s</span><span class=tag>%s</span>`+
			`<footer><span>Updated %d days ago</span><span>v1.%d.%d</span></footer></article>`,
			r.titleWords(2+r.intn(2)), r.sentence(14, 22), t, r.word(), r.word(), 1+r.intn(40), r.intn(9), r.intn(30))
		_ = i
	}
	b.WriteString(`</section><h2>Usage</h2><div class=prose>`)
	for range 4 {
		fmt.Fprintf(&b, `<p>%s %s %s</p>`, r.sentence(12, 18), r.sentence(10, 16), r.sentence(14, 20))
	}
	b.WriteString(`</div><h2>Props</h2><table><thead><tr><th>Prop</th><th>Type</th><th>Default</th><th>Description</th><th>Status</th></tr></thead><tbody>`)
	tail := `</tbody></table></main></div></body></html>`
	types := []string{"boolean", "string", "number", "ReactNode", `"sm" | "md" | "lg"`, "() => void", "Record<string, unknown>", "Date"}
	defs := []string{"false", "true", `"md"`, "0", "—", "null", `""`}
	status := []string{"ok", "warn", "bad"}
	statusText := map[string]string{"ok": "stable", "warn": "beta", "bad": "deprecated"}
	for b.Len()+len(tail) < storyTarget {
		w1, w2 := r.word(), r.word()
		prop := w1 + strings.ToUpper(w2[:1]) + w2[1:]
		st := status[r.intn(len(status))]
		fmt.Fprintf(&b, `<tr><td><code>%s</code></td><td><code>%s</code></td><td><code>%s</code></td><td>%s</td><td><span class="tag %s">%s</span></td></tr>`,
			prop, html.EscapeString(types[r.intn(len(types))]), html.EscapeString(defs[r.intn(len(defs))]), r.sentence(10, 16), st, statusText[st])
	}
	b.WriteString(tail)
	return b.String()
}
