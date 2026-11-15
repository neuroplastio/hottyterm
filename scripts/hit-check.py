#!/usr/bin/env python3
"""Run the spec's hit vectors through a hottyterm PTY (no host test hooks).

Started by hit-check.sh. HOTTY_DIR supplies the unchanged spec vectors and
Python wire client; the layout, C ABI call and reply all happen in hottyterm.
"""
import json
import os
from pathlib import Path
import sys
import time
import traceback

HOTTY = Path(os.environ['HOTTY_DIR'])
sys.path.insert(0, str(HOTTY / 'clients/python'))
from hotty import Hotty  # noqa: E402


def drain(host, seconds):
    messages = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        host.read(max(0, end - time.monotonic()))
        got, _ = host.take()
        messages.extend(got)
    return messages


def matches(message, expected):
    body = message.body or {}
    for key, value in expected.items():
        if key == 'body':
            for name, want in value.items():
                if want is None:
                    assert name not in body, (name, body)
                else:
                    assert body.get(name) == want, (name, want, body)
                    assert type(body[name]) is type(want), (name, want, body)
        elif key in ('code', 'detail'):
            assert body.get(key) == value, (key, value, body)
        else:
            assert message.get(key) == value, (key, value, message.control)


def main(out):
    vectors = json.loads((HOTTY / 'conformance/vectors.json').read_text())
    cases = [v for v in vectors['vectors'] if any(
        step.get('send', {}).get('a') == 'hit' for step in v['steps'])]
    assert len(cases) == 2, 'review new hit vectors before running this probe'
    host = Hotty()
    results = []
    with host.raw():
        for case in cases:
            host.write('\x1bc\x1b[H')
            drain(host, .2)
            hits = 0
            for index, step in enumerate(case['steps']):
                assert set(step) <= {'send', 'payload', 'reply', 'events'}, step
                host.send(payload=step.get('payload', '').encode(), **step['send'])
                # Give placements a frame before querying their layout. Gather
                # another frame after the reply too: a hit must send no events.
                messages = drain(host, .3)
                replies = [m for m in messages if m.get('a') in ('ok', 'err')]
                events = [m for m in messages if m.get('a') == 'ev']
                if 'reply' in step:
                    expected = step['reply']
                    if expected is None:
                        assert not replies, (case['name'], index, replies)
                    else:
                        assert len(replies) == 1, (case['name'], index, replies)
                        matches(replies[0], expected)
                if 'events' in step:
                    assert step['events'] == [] and not events, (index, events)
                if step['send']['a'] == 'hit':
                    hits += 1
                    # Every hit body uses signed integer steps, when present.
                    for reply in replies:
                        for key in ('tx', 'ty'):
                            if key in (reply.body or {}):
                                assert type(reply.body[key]) is int, reply.body
            results.append({'name': case['name'], 'hits': hits})
    out.write_text(json.dumps({'ok': True, 'vectors': results}, indent=2) + '\n')


if __name__ == '__main__':
    result = Path(sys.argv[1])
    try:
        main(result)
    except Exception:
        result.write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}, indent=2) + '\n')
        raise
