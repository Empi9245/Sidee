"""Generate the phone access QR locally, using the bundled MIT QR encoder.

Encoder source: https://github.com/nayuki/QR-Code-generator/tree/v1.8.0/python
"""
from __future__ import annotations

import base64

from ._qrcodegen import QrCode


def qr_image(url: str) -> str:
    qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    border = 4  # QR quiet zone, in modules
    size = qr.get_size() + border * 2
    squares = " ".join(
        f"M{x + border},{y + border}h1v1h-1z"
        for y in range(qr.get_size()) for x in range(qr.get_size())
        if qr.get_module(x, y))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
           'shape-rendering="crispEdges">'
           '<rect width="100%" height="100%" fill="#fff"/>'
           f'<path d="{squares}" fill="#000"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")
