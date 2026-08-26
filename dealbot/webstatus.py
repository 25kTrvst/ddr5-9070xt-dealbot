from __future__ import annotations

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Config

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DealBot V6 status</title>
<style>
  :root { color-scheme: dark; }
  body { background: #1e1f22; color: #dbdee1; font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 24px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  .updated { color: #949ba4; font-size: 12px; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
  .card { background: #2b2d31; border-radius: 8px; padding: 14px 16px; border-left: 4px solid #4e5058; }
  .card.ok { border-left-color: #23a55a; }
  .card.error { border-left-color: #f23f42; }
  .card.crashed { border-left-color: #f23f42; }
  .card.backoff { border-left-color: #f0b232; }
  .card.quarantine { border-left-color: #f0b232; }
  .name { font-weight: 600; margin-bottom: 4px; }
  .state { text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; color: #949ba4; }
  .detail { font-size: 13px; margin-top: 6px; color: #dbdee1; word-break: break-word; }
  .section { margin-top: 28px; }
  .connections span { display: inline-block; margin: 2px 10px 2px 0; padding: 3px 10px; border-radius: 12px; font-size: 12px; background: #2b2d31; }
  .connections span.ready { color: #23a55a; }
  .connections span.missing { color: #949ba4; }
</style>
</head>
<body>
<h1>DealBot V6 status</h1>
<div class="updated" id="updated">loading…</div>
<div class="section connections" id="connections"></div>
<div class="section grid" id="sources"></div>
<script>
function badge(cls, text) { return `<div class="card ${cls}"><div class="state">${cls}</div><div class="name">${text.source}</div><div class="detail">${text.detail || ''}</div></div>`; }
async function refresh() {
  try {
    const r = await fetch('/status.json', {cache: 'no-store'});
    const data = await r.json();
    document.getElementById('updated').textContent = 'Updated ' + new Date().toLocaleTimeString() + ' — auto-refreshes every 5s';
    const conn = document.getElementById('connections');
    conn.innerHTML = Object.entries(data.connections).map(([name, ok]) =>
      `<span class="${ok ? 'ready' : 'missing'}">${name}: ${ok ? 'ready' : 'not configured'}</span>`).join('');
    const sources = document.getElementById('sources');
    sources.innerHTML = data.sources.map(s => badge((s.state || 'unknown').toLowerCase(), s)).join('') || '<p>Waiting for the first scans…</p>';
  } catch (e) {
    document.getElementById('updated').textContent = 'Could not reach the bot (is it still running?)';
  }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


def _make_handler(cfg: Config, engine) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # silence default stderr access log spam
            pass

        def do_GET(self) -> None:  # noqa: N802 - required name by BaseHTTPRequestHandler
            if self.path in {"/", "/index.html"}:
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif self.path == "/status.json":
                self._send(200, json.dumps(self._snapshot()).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")

        def _snapshot(self) -> dict:
            with sqlite3.connect(f"file:{cfg.database_path}?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                rows = [dict(r) for r in db.execute("SELECT * FROM source_health ORDER BY source")]
            return {
                "sources": rows,
                "connections": {
                    "eBay": engine.ebay.configured,
                    "Best Buy": engine.bestbuy.configured,
                    "Reddit": engine.discovery[0].configured,
                    "Slickdeals": engine.discovery[1].configured,
                    "Zoho Mail": engine.discovery[2].configured,
                },
            }

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


class StatusWebServer:
    """A tiny local-only webpage mirroring /status, so you can glance at a
    browser tab instead of typing /status in Discord every time. Reads the
    same sqlite database the bot already writes to, in its own read-only
    connection, so it can't interfere with the bot's own writes."""

    def __init__(self, cfg: Config, engine) -> None:
        self.cfg, self.engine = cfg, engine
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = _make_handler(self.cfg, self.engine)
        self._server = ThreadingHTTPServer(("127.0.0.1", self.cfg.status_web_port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="status-web", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
