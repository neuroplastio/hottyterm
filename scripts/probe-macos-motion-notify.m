// Probe-only: deliver an accessibility notification inside the unmodified
// app process. Startup uses the real getter. Live checks may explicitly
// substitute the getter after the single system-refresh attempt fails.
#import <AppKit/AppKit.h>
#import <CoreFoundation/CoreFoundation.h>
#import <dispatch/dispatch.h>
#import <objc/runtime.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

static NSString *probeDirectory;
static atomic_bool simulatedMotion;
static BOOL getterSwizzled;

static BOOL simulatedGetter(id self, SEL selector) {
    (void)self; (void)selector;
    return atomic_load(&simulatedMotion);
}

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
            NSString *mode = [NSString stringWithContentsOfFile:
                [probeDirectory stringByAppendingPathComponent:@"motion-mode"]
                encoding:NSUTF8StringEncoding error:NULL];
            if ([mode hasPrefix:@"simulate"]) {
                NSString *value = [NSString stringWithContentsOfFile:
                    [probeDirectory stringByAppendingPathComponent:@"motion-value"]
                    encoding:NSUTF8StringEncoding error:NULL];
                if (![value isEqualToString:@"0\n"] && ![value isEqualToString:@"1\n"]) {
                    fprintf(stderr, "motion probe: invalid simulated getter value\n");
                    return;
                }
                atomic_store(&simulatedMotion, value.intValue != 0);
                if (!getterSwizzled) {
                    SEL selector = @selector(accessibilityDisplayShouldReduceMotion);
                    Class cls = object_getClass(workspace);
                    Method method = class_getInstanceMethod(cls, selector);
                    if (!method) {
                        fprintf(stderr, "motion probe: cannot find getter to simulate\n");
                        return;
                    }
                    class_replaceMethod(cls, selector, (IMP)simulatedGetter, method_getTypeEncoding(method));
                    getterSwizzled = YES;
                }
                fprintf(stderr, "motion probe: SIMULATED macOS live getter=%d; testing observer only\n",
                        atomic_load(&simulatedMotion));
            }
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

static void refresh(CFNotificationCenterRef center, void *observer,
                    CFStringRef name, const void *object, CFDictionaryRef info) {
    (void)center; (void)observer; (void)name; (void)object; (void)info;
    dispatch_async(dispatch_get_main_queue(), ^{
        @autoreleasepool {
            NSString *names = [NSString stringWithContentsOfFile:
                [probeDirectory stringByAppendingPathComponent:@"motion-notifications.txt"]
                encoding:NSUTF8StringEncoding error:NULL];
            for (NSString *candidate in [names componentsSeparatedByString:@"\n"]) {
                if (candidate.length == 0) continue;
                fprintf(stderr, "motion probe: one-time distributed refresh candidate %s\n", candidate.UTF8String);
                [NSDistributedNotificationCenter.defaultCenter postNotificationName:candidate
                    object:nil userInfo:nil deliverImmediately:YES];
            }
            record(@"motion-refresh-ack", YES);
        }
    });
}

static void windowBounds(CFNotificationCenterRef center, void *observer,
                         CFStringRef name, const void *object, CFDictionaryRef info) {
    (void)center; (void)observer; (void)name; (void)object; (void)info;
    dispatch_async(dispatch_get_main_queue(), ^{
        @autoreleasepool {
            NSWindow *window = NSApp.keyWindow ?: NSApp.mainWindow;
            if (!window.isVisible) {
                window = nil;
                for (NSWindow *candidate in NSApp.windows) {
                    if (candidate.isVisible && candidate.level == NSNormalWindowLevel) {
                        window = candidate;
                        break;
                    }
                }
            }
            if (!window) {
                fprintf(stderr, "motion probe: no visible app window for capture\n");
                return;
            }
            NSRect frame = window.frame;
            NSRect content = [window convertRectToScreen:window.contentLayoutRect];
            // screencapture -l -o has the window frame, no shadow. Its image
            // starts at the top left; AppKit screen coordinates start below.
            NSDictionary *geometry = @{
                @"window_id": @(window.windowNumber),
                @"window_width": @(NSWidth(frame)), @"window_height": @(NSHeight(frame)),
                @"content_x": @(NSMinX(content) - NSMinX(frame)),
                @"content_y": @(NSMaxY(frame) - NSMaxY(content)),
                @"content_width": @(NSWidth(content)), @"content_height": @(NSHeight(content))
            };
            NSError *error = nil;
            NSData *data = [NSJSONSerialization dataWithJSONObject:geometry options:0 error:&error];
            NSString *path = [probeDirectory stringByAppendingPathComponent:@"motion-window.json"];
            if (!data || ![data writeToFile:path options:NSDataWritingAtomic error:&error]) {
                fprintf(stderr, "motion probe: cannot record window bounds: %s\n",
                        error.localizedDescription.UTF8String);
            } else {
                fprintf(stderr, "motion probe: capture bounds %s\n", geometry.description.UTF8String);
            }
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
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL,
            refresh, CFSTR("io.github.neuroplastio.hottyterm.probe.motion.refresh"), NULL,
            CFNotificationSuspensionBehaviorDeliverImmediately);
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL,
            windowBounds, CFSTR("io.github.neuroplastio.hottyterm.probe.motion.bounds"), NULL,
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
