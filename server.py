"""로컬 수요 실험 서버. Python 표준 라이브러리만 사용한다."""

import argparse
import json
import sqlite3
import uuid
import webbrowser
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pricing import quote


ROOT = Path(__file__).resolve().parent
DDL = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parameters TEXT NOT NULL,
    result TEXT NOT NULL,
    seen_at TEXT,
    proceeded_at TEXT
);
"""


def order_parameters(body):
    return dict(menu=body.get("menu"), servings=body.get("servings"),
                containers=body.get("containers", 0), extra=body.get("extra"),
                extra_grams=body.get("extra_grams", 0), per_serving=body.get("per_serving", False))


def save_quote(db, request_id, params, catalog):
    serialized = json.dumps(params, ensure_ascii=False, sort_keys=True)
    db.execute("BEGIN IMMEDIATE")
    existing = db.execute("SELECT parameters, result FROM requests WHERE id=?", (request_id,)).fetchone()
    if existing:
        if json.loads(existing[0]) != params:
            raise ValueError("같은 요청 번호에 다른 조건이 들어왔습니다. 다시 입력해 주세요.")
        return json.loads(existing[1])
    result = quote(catalog=catalog, **params)
    db.execute("INSERT INTO requests(id, parameters, result) VALUES (?, ?, ?)",
               (request_id, serialized, json.dumps(result, ensure_ascii=False)))
    return result


def save_event(db, request_id, event):
    if event not in ("seen", "proceed"):
        raise ValueError("알 수 없는 기록 유형입니다.")
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT result FROM requests WHERE id=?", (request_id,)).fetchone()
    if row is None or json.loads(row[0]).get("status") != "estimated":
        raise ValueError("제시된 가격이 있는 요청만 기록할 수 있습니다.")
    # A deliberate click also establishes that the offer reached the visitor.
    db.execute("UPDATE requests SET seen_at=COALESCE(seen_at, CURRENT_TIMESTAMP) WHERE id=?", (request_id,))
    if event == "proceed":
        db.execute("UPDATE requests SET proceeded_at=COALESCE(proceeded_at, CURRENT_TIMESTAMP) WHERE id=?",
                   (request_id,))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Local research records contain no client addresses or access logs.
        pass

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlsplit(self.path).path == "/":
            self.reply(200, self.server.index, "text/html; charset=utf-8")
        else:
            self.reply(404, {"error": "페이지를 찾을 수 없습니다."})

    def do_POST(self):
        if self.path not in ("/api/quote", "/api/event"):
            self.reply(404, {"error": "페이지를 찾을 수 없습니다."})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "JSON 형식이 필요합니다."})
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 16384:
                raise ValueError("요청 크기를 확인해 주세요.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("요청 형식을 확인해 주세요.")
            request_id = body.get("id")
            if not isinstance(request_id, str) or str(uuid.UUID(request_id)) != request_id:
                raise ValueError("요청 번호를 확인해 주세요.")
            with closing(sqlite3.connect(self.server.database, timeout=10)) as db, db:
                if self.path == "/api/quote":
                    result = save_quote(db, request_id, order_parameters(body), self.server.catalog)
                else:
                    save_event(db, request_id, body.get("event"))
                    result = {"ok": True}
        except (ValueError, UnicodeError) as error:
            self.reply(400, {"error": str(error)})
            return
        except sqlite3.Error:
            self.reply(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "기록을 저장하지 못했습니다. 다시 시도해 주세요."})
            return
        self.reply(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="가격 기준표 JSON 경로")
    parser.add_argument("--db", type=Path, default=Path("experiment.sqlite3"), help="실험 기록 SQLite 파일")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="로컬 브라우저에서 열기")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(args.db)) as db:
        db.executescript(DDL)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.catalog, server.database = catalog, args.db
        server.index = (ROOT / "index.html").read_bytes()
        print(f"레시피 가격 측정기  http://127.0.0.1:{server.server_port}", flush=True)
        if args.open:
            webbrowser.open(f"http://127.0.0.1:{server.server_port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
