"""Print the body of every POST request received on 127.0.0.1:8080."""

import http.server


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (name set by BaseHTTPRequestHandler)
        length = int(self.headers.get('Content-Length', 0))
        print(self.rfile.read(length).decode(), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        pass


if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', 8080), _Handler)
    print('listening on http://127.0.0.1:8080', flush=True)
    server.serve_forever()
