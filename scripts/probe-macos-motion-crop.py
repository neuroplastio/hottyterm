#!/usr/bin/env python3
"""Crop a shadowless macOS window capture to its unobscured content area.

The injected AppKit helper records bounds in points. Derive pixels per point
from the captured window size, so Retina screenshots exclude the title bar too.
The GTK PPM checker and its full-screen captures are unchanged.
"""
import json
import math
from pathlib import Path
import sys


def content_box(size, geometry):
    width, height = size
    fw, fh = float(geometry['window_width']), float(geometry['window_height'])
    x, y = float(geometry['content_x']), float(geometry['content_y'])
    w, h = float(geometry['content_width']), float(geometry['content_height'])
    assert all(math.isfinite(v) for v in (fw, fh, x, y, w, h)), geometry
    assert fw > 0 and fh > 0 and w > 0 and h > 0, geometry
    assert 0 <= x < x + w <= fw and 0 <= y < y + h <= fh, geometry
    sx, sy = width / fw, height / fh
    assert abs(sx - sy) < .01, ('window capture aspect differs from bounds', size, geometry)
    # Round inward, keeping title-bar and frame pixels outside the count.
    box = (math.ceil(x * sx), math.ceil(y * sy),
           math.floor((x + w) * sx), math.floor((y + h) * sy))
    assert box[0] < box[2] and box[1] < box[3], (size, geometry, box)
    return box


def main(args):
    if args[0] == '--window-id':
        geometry = json.loads(Path(args[1]).read_text())
        window_id = geometry['window_id']
        assert type(window_id) is int and window_id > 0, geometry
        print(window_id)
        return
    from PIL import Image
    source, bounds, target = args
    geometry = json.loads(Path(bounds).read_text())
    with Image.open(source) as image:
        box = content_box(image.size, geometry)
        image.crop(box).save(target)
        print(f'crop {source}: window {image.size}, content {box} -> {target}')


if __name__ == '__main__':
    main(sys.argv[1:])
