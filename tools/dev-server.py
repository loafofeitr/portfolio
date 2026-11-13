import http.server, os, sys, json

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
SNIPPET = b"""<script>(function(){var v=null;setInterval(function(){fetch('/__version',{cache:'no-store'}).then(function(r){return r.text()}).then(function(t){if(v!==null&&t!==v)location.reload();v=t}).catch(function(){})},1000)})();</script>"""

def version():
    m = 0
    for d, _, files in os.walk(ROOT):
        if "/.git" in d:
            continue
        for f in files:
            m = max(m, os.path.getmtime(os.path.join(d, f)))
    return str(m).encode()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def send_body(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/__version":
            return self.send_body(version(), "text/plain")
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if path.endswith(".html") and os.path.isfile(path):
            with open(path, "rb") as f:
                html = f.read()
            html = html.replace(b"</body>", SNIPPET + b"</body>") if b"</body>" in html else html + SNIPPET
            return self.send_body(html, "text/html; charset=utf-8")
        super().do_GET()

    def log_message(self, *a):
        pass

http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
