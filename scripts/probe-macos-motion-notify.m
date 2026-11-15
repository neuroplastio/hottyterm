// Probe-only: deliver an accessibility notification inside the unmodified
// app process. This tests its observer and getter, not macOS's own delivery.
#import <AppKit/AppKit.h>
#import <CoreFoundation/CoreFoundation.h>
#import <dispatch/dispatch.h>
#include <stdio.h>
#include <stdlib.h>

static NSString *probeDirectory;

static void record(NSString *file, BOOL reduce) {
    NSString *path = [probeDirectory stringByAppendingPathComponent:file];
    NSError *error = nil;
    if (![[NSString stringWithFormat:@"%d\n", reduce ? 1 : 0]
            writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:&error]) {
        fprintf(stderr, "motion probe: cannot write %s: %s\n",
                path.UTF8String, error.localizedDescription.UTF8String);
    }
}

static void changed(CFNotificationCenterRef center, void *observer,
                    CFStringRef name, const void *object, CFDictionaryRef info) {
    (void)center; (void)observer; (void)name; (void)object; (void)info;
    dispatch_async(dispatch_get_main_queue(), ^{
        @autoreleasepool {
            Boolean synced = CFPreferencesAppSynchronize(CFSTR("com.apple.universalaccess"));
            NSWorkspace *workspace = NSWorkspace.sharedWorkspace;
            BOOL before = workspace.accessibilityDisplayShouldReduceMotion;
            [workspace.notificationCenter
                postNotificationName:NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification
                object:workspace];
            BOOL after = workspace.accessibilityDisplayShouldReduceMotion;
            fprintf(stderr, "motion probe: preferences synchronized=%d; posted "
                    "NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification on main queue; "
                    "AppKit reduceMotion before=%d after=%d\n", synced, before, after);
            record(@"motion-ack", after);
        }
    });
}

__attribute__((constructor)) static void start(void) {
    const char *directory = getenv("HOTTY_MOTION_PROBE_DIR");
    if (!directory) return;
    @autoreleasepool {
        probeDirectory = [NSString stringWithUTF8String:directory];
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL,
            changed, CFSTR("io.github.neuroplastio.hottyterm.probe.motion"), NULL,
            CFNotificationSuspensionBehaviorDeliverImmediately);
        dispatch_async(dispatch_get_main_queue(), ^{
            @autoreleasepool {
                BOOL reduce = NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion;
                fprintf(stderr, "motion probe: injected helper loaded; startup AppKit reduceMotion=%d\n", reduce);
                record(@"motion-loaded", reduce);
            }
        });
    }
}
