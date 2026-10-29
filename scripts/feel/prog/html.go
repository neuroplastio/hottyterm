package main

import (
	"flag"
	"fmt"
	"os"
)

// htmlMain prints a scenario's document for a terminal of --cols × --rows
// cells of --cell CSS px, for `hotty render` to check what it draws:
//
//	feelprog html e3 --cols 120 --rows 35 --cell 10x21 > e3.html
//	hotty render e3.html --cols 120 --rows 35 --cell 10x21 -o e3.png
func htmlMain(args []string) int {
	if len(args) < 1 {
		usage()
	}
	which := args[0]
	fs := flag.NewFlagSet("feelprog html", flag.ExitOnError)
	cols := fs.Int("cols", 120, "the surface's columns")
	rows := fs.Int("rows", 35, "the surface's rows")
	cell := fs.String("cell", "10x21", "a cell in CSS px, WxH")
	size := fs.String("size", "full", "row, half or full")
	rowPx := fs.Int("row-px", 40, "e3: a row's height in CSS px")
	_ = fs.Parse(args[1:])
	var cw, ch float64
	if _, err := fmt.Sscanf(*cell, "%gx%g", &cw, &ch); err != nil {
		fmt.Fprintln(os.Stderr, "feelprog html: --cell is WxH")
		return 2
	}
	w, h := float64(*cols)*cw, float64(*rows)*ch
	switch which {
	case "e1p":
		doc, _ := paintDoc(*size, w, h)
		fmt.Print(doc)
	case "e2":
		fmt.Print(e2Doc(*size))
	case "e3":
		fmt.Print(e3Doc(*size, e3Items(*size, w, h, *rowPx), *rowPx))
	case "e6a":
		fmt.Print(storybook(0))
	case "e6b":
		fmt.Print(storybook(1))
	default:
		usage()
	}
	return 0
}
