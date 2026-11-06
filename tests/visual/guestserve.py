#!/usr/bin/env python3
"""Loopback-only file server for the reference VM (QEMU user networking reaches it as 10.0.2.2).

    guestserve.py DIR PORT     GET /x.ps1 serves DIR/x.ps1; PUT /out/name stores DIR/out/name
"""
import functools
import http.server
import os
import sys


class H(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        name = os.path.basename(self.path)
        n = int(self.headers.get('Content-Length', 0))
        os.makedirs(os.path.join(self.directory, 'out'), exist_ok=True)
        with open(os.path.join(self.directory, 'out', name), 'wb') as f:
            f.write(self.rfile.read(n))
        self.send_response(201)
        self.end_headers()


d, port = sys.argv[1], int(sys.argv[2])
os.makedirs(d, exist_ok=True)
http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(H, directory=d)).serve_forever()
