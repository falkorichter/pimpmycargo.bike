"""Tiny local receiver: the browser POSTs files to http://127.0.0.1:8765/save?path=rel/path
and they are written under the import directory given as argv[1]."""
import os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.realpath(sys.argv[1])

# Relay page: opened as a popup from a page whose CSP blocks localhost; it receives
# {path, data} via postMessage and POSTs them here (same origin).
RELAY = """<!doctype html><title>relay</title><pre id=l>ready</pre><script>
let n=0;
addEventListener('message', async e => {
  const {id, path, data} = e.data || {};
  if (!path) return;
  try {
    const r = await fetch('/save?path=' + encodeURIComponent(path), {method: 'POST', body: data});
    n++; document.getElementById('l').textContent = n + ' saved, last: ' + path;
    e.source.postMessage({id, ok: r.status === 200}, '*');
  } catch (err) { e.source.postMessage({id, ok: false, err: String(err)}, '*'); }
});
</script>"""

class H(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()
    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        rel = q.get("path", [""])[0]
        dest = os.path.realpath(os.path.join(ROOT, rel))
        if not rel or not dest.startswith(ROOT + os.sep):
            self.send_response(400); self.cors(); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f: f.write(data)
        self.send_response(200); self.cors(); self.end_headers(); self.wfile.write(b"ok")
    def do_GET(self):
        body = RELAY.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
