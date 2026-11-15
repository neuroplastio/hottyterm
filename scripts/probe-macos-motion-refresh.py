#!/usr/bin/env python3
"""One bounded search/post attempt for universal-access refresh notifications.

Run only by the macOS CI probe. Names from strings are candidates, not a claim
that the daemon uses each one. Missing cached framework binaries are logged.
The caller broadcasts the same list through the injected distributed center.
"""
import re
import subprocess
import sys
import time
from pathlib import Path


def attempt(target, frameworks=Path('/System/Library/PrivateFrameworks'), budget=15):
    deadline = time.monotonic() + budget
    names = {'com.apple.universalaccess',
             'NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification'}
    scanned = set()
    motion_lines = 0
    for bundle in sorted(frameworks.glob('UniversalAccess*.framework')):
        for binary in [bundle / bundle.stem, *sorted(bundle.glob(f'Versions/*/{bundle.stem}'))]:
            binary = binary.resolve()
            if not binary.is_file() or binary in scanned:
                continue
            if len(scanned) == 4 or deadline - time.monotonic() < 1:
                break
            scanned.add(binary)
            print(f'one-time refresh: strings {binary}', flush=True)
            try:
                result = subprocess.run(['strings', '-a', str(binary)], capture_output=True,
                                        text=True, errors='replace',
                                        timeout=min(2, deadline - time.monotonic()))
                if result.returncode:
                    print(f'strings exit {result.returncode}: {result.stderr}', flush=True)
                for line in result.stdout.splitlines():
                    if time.monotonic() >= deadline:
                        break
                    if re.search(r'motion|display|setting|preference|changed', line, re.I):
                        if motion_lines < 20 and re.search(r'motion', line, re.I):
                            print(f'framework motion string: {line[:200]}', flush=True)
                            motion_lines += 1
                        names.update(re.findall(r'com\.apple\.(?:universalaccess|accessibility)[\w.-]*', line))
            except subprocess.TimeoutExpired:
                print('strings timed out; no retry', flush=True)
        if len(scanned) == 4 or deadline - time.monotonic() < 1:
            break
    if not scanned:
        print('No standalone UniversalAccess framework binaries (may live in the dyld cache); using seed candidates, no further search.', flush=True)
    ordered = sorted(names, key=lambda n: ('motion' not in n.lower(), n))[:8]
    target.write_text('\n'.join(ordered) + '\n')
    for name in ordered:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print('15-second search/post budget exhausted; no retry', flush=True)
            break
        print(f'one-time refresh: Darwin candidate notifyutil -p {name}', flush=True)
        try:
            result = subprocess.run(['notifyutil', '-p', name], capture_output=True,
                                    text=True, timeout=min(.5, remaining))
            print(f'notifyutil exit {result.returncode}: {result.stderr.strip()}', flush=True)
        except subprocess.TimeoutExpired:
            print('notifyutil timed out; no retry', flush=True)


if __name__ == '__main__':
    attempt(Path(sys.argv[1]))
