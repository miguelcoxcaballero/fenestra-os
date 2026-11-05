#!/usr/bin/python3
"""Builds app.ico: the Fenestra arched-window mark (original artwork) with an export arrow badge."""
import io
import sys
from pathlib import Path

from PIL import Image

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 64 64">
<defs><linearGradient id="a" x1="0" y1="0" x2="0.6" y2="1"><stop offset="0" stop-color="#6fdcff"/><stop offset="1" stop-color="#0c62d8"/></linearGradient>
<linearGradient id="b" x1="0" y1="0" x2="0.6" y2="1"><stop offset="0" stop-color="#52c6ff"/><stop offset="1" stop-color="#0a4fb4"/></linearGradient>
<linearGradient id="c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3ddc84"/><stop offset="1" stop-color="#0f9d58"/></linearGradient></defs>
<path d="M6 28C6 15.8 15.8 6 28 6v22z" fill="url(#a)"/>
<path d="M30 6c12.2 0 20 9.8 20 22H30z" fill="url(#b)"/>
<path d="M6 30h22v22H8a2 2 0 0 1-2-2z" fill="url(#b)"/>
<path d="M30 30h20v20a2 2 0 0 1-2 2H30z" fill="url(#a)"/>
<circle cx="47" cy="47" r="15" fill="#ffffff"/>
<circle cx="47" cy="47" r="13" fill="url(#c)"/>
<path d="M47 38v14M41 46.5l6 6 6-6" stroke="#fff" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''


def render(size):
    """SVG -> PNG bytes with librsvg (python3-gobject + librsvg2, present on any GNOME host)."""
    import cairo
    import gi
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    handle = Rsvg.Handle.new_from_data(SVG.encode())
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    rect = Rsvg.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0, 0, size, size
    handle.render_document(cairo.Context(surface), rect)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def main(out):
    images = []
    for size in (256, 64, 48, 40, 32, 24, 20, 16):
        png = render(size)
        images.append(Image.open(io.BytesIO(png)).convert('RGBA'))
    images[0].save(out, format='ICO', sizes=[im.size for im in images], append_images=images[1:])
    Path(out).with_suffix('.svg').write_text(SVG + '\n')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'app.ico')
