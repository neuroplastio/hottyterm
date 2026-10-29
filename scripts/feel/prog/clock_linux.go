package main

import "golang.org/x/sys/unix"

// clockName is the header's clock (docs/trace.md): Linux CLOCK_MONOTONIC.
const clockName = "monotonic"

// now is the trace clock, in ns.
func now() int64 {
	var ts unix.Timespec
	_ = unix.ClockGettime(unix.CLOCK_MONOTONIC, &ts)
	return ts.Nano()
}
