package main

import "golang.org/x/sys/unix"

// clockName is the header's clock (docs/trace.md): macOS CLOCK_UPTIME_RAW,
// which is mach_absolute_time in ns.
const clockName = "uptime-raw"

// now is the trace clock, in ns.
func now() int64 {
	var ts unix.Timespec
	_ = unix.ClockGettime(unix.CLOCK_UPTIME_RAW, &ts)
	return ts.Nano()
}
