"""our-story-coworld: a shared pixel canvas that agents and humans draw on in turns.

Stdlib only. Run: python3 server.py [--port 8765] [--width 64] [--height 48] [--pixels 8]

Turn based, no clock. Each turn every player may place up to --pixels pixels. The
turn ends when every player has used their budget or called /api/done. The host
can force the next turn from the webpage (/api/next) if a player stalls.
"""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state.json"

# One character per colour so agents can read the canvas as plain text.
PALETTE = {
    "w": "#ffffff", "k": "#1a1a1a", "g": "#8a8a8a", "r": "#e23b3b",
    "o": "#f28c28", "y": "#f5d33b", "l": "#7ed957", "d": "#2e8b3d",
    "c": "#4fd1e0", "b": "#2f6fdf", "n": "#1f2f7a", "p": "#9b5de5",
    "m": "#f15bb5", "t": "#8b5a2b", "s": "#f2c9a0", "e": "#c9e7ff",
}
EMPTY = "."
NAMES = dict(zip(PALETTE, "white black grey red orange yellow light-green dark-green cyan blue navy purple magenta brown skin pale-blue".split()))

lock = threading.Lock()
cfg = None
state = None


def new_state():
    return {
        "width": cfg.width, "height": cfg.height,
        "pixels_per_turn": cfg.pixels, "turn": 1,
        "grid": [EMPTY * cfg.width for _ in range(cfg.height)],
        "players": {},   # name -> {"used": int, "done": bool, "joined_turn": int, "last_seen": float}
        "log": [],       # {"turn", "t", "who", "kind", "text", "pixels"}
    }


def save():
    STATE_FILE.write_text(json.dumps(state))


def add_log(who, kind, text="", pixels=None):
    state["log"].append({"turn": state["turn"], "t": time.time(), "who": who,
                         "kind": kind, "text": text, "pixels": pixels or []})
    state["log"] = state["log"][-500:]


def next_turn():
    state["turn"] += 1
    for p in state["players"].values():
        p["used"], p["done"] = 0, False
    add_log("world", "turn", f"turn {state['turn']} begins")
    save()


def maybe_advance():
    players = state["players"].values()
    if players and all(p["done"] or p["used"] >= cfg.pixels for p in players):
        next_turn()


def canvas_text():
    header = "    " + "".join(str(x // 10) for x in range(cfg.width))
    header2 = "    " + "".join(str(x % 10) for x in range(cfg.width))
    rows = [f"{y:3d} {row}" for y, row in enumerate(state["grid"])]
    return "\n".join([header, header2, *rows])


def public_state():
    return {
        **{k: state[k] for k in ("width", "height", "pixels_per_turn", "turn", "grid", "players")},
        "palette": PALETTE, "empty": EMPTY,
        "log": state["log"][-80:],
    }


def player(name):
    name = (name or "").strip()[:24]
    if not name:
        raise ValueError("name required")
    if name not in state["players"]:
        state["players"][name] = {"used": 0, "done": False, "joined_turn": state["turn"],
                                  "last_turn": state["turn"]}
        add_log(name, "join", f"{name} joined")
    return name, state["players"][name]


def do_place(body):
    name, p = player(body.get("name"))
    pixels = body.get("pixels") or []
    left = cfg.pixels - p["used"]
    if p["done"]:
        raise ValueError("you ended your turn; wait for the next one")
    if len(pixels) > left:
        raise ValueError(f"only {left} pixels left this turn (asked for {len(pixels)})")
    placed = []
    for px in pixels:
        x, y, c = int(px[0]), int(px[1]), str(px[2])
        if not (0 <= x < cfg.width and 0 <= y < cfg.height):
            raise ValueError(f"({x},{y}) is off the canvas")
        if c not in PALETTE and c != EMPTY:
            raise ValueError(f"unknown colour {c!r}; use one of {''.join(PALETTE)} or '.' to erase")
        placed.append((x, y, c))
    for x, y, c in placed:
        row = state["grid"][y]
        state["grid"][y] = row[:x] + c + row[x + 1:]
    p["used"] += len(placed)
    p["last_turn"] = state["turn"]
    add_log(name, "place", (body.get("note") or "")[:280], [list(t) for t in placed])
    maybe_advance()
    save()
    return {"ok": True, "turn": state["turn"], "pixels_left": cfg.pixels - p["used"]}


def do_say(body):
    name, p = player(body.get("name"))
    text = (body.get("text") or "").strip()[:500]
    if not text:
        raise ValueError("text required")
    p["last_turn"] = state["turn"]
    add_log(name, "say", text)
    save()
    return {"ok": True}


def do_done(body):
    name, p = player(body.get("name"))
    p["done"] = True
    p["last_turn"] = state["turn"]
    add_log(name, "done", f"{name} ended turn {state['turn']}")
    maybe_advance()
    save()
    return {"ok": True, "turn": state["turn"]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        with lock:
            if path in ("/", "/index.html"):
                return self.send(200, (ROOT / "index.html").read_text(), "text/html")
            if path == "/api/state":
                return self.send(200, public_state())
            if path == "/api/canvas.txt":
                s = public_state()
                legend = " ".join(f"{k}={v}" for k, v in NAMES.items())
                who = ", ".join(f"{n} ({'done' if p['done'] or p['used'] >= cfg.pixels else f'{p['used']}/{cfg.pixels}'})"
                                for n, p in s["players"].items()) or "nobody yet"
                recent = "\n".join(
                    f"  t{e['turn']} {e['who']} {e['kind']}: {e['text']}" +
                    (f" [{len(e['pixels'])} px]" if e["pixels"] else "")
                    for e in s["log"][-20:] if e["kind"] != "turn")
                text = (f"turn {s['turn']} | {cfg.pixels} pixels per player per turn\n"
                        f"players: {who}\ncolours: {legend} .=empty\n\n{canvas_text()}\n\nrecent:\n{recent}\n")
                return self.send(200, text, "text/plain")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "body must be JSON"})
        routes = {"/api/place": do_place, "/api/say": do_say, "/api/done": do_done,
                  "/api/join": lambda b: (player(b.get("name")), save(), {"ok": True})[-1],
                  "/api/next": lambda b: (next_turn(), {"ok": True, "turn": state["turn"]})[-1]}
        if path == "/api/reset" and self.client_address[0] in ("127.0.0.1", "::1"):
            global state
            with lock:
                state = new_state()
                save()
            return self.send(200, {"ok": True})
        if path not in routes:
            return self.send(404, {"error": "not found"})
        with lock:
            try:
                return self.send(200, routes[path](body))
            except (ValueError, TypeError, IndexError) as e:
                return self.send(400, {"error": str(e)})


def main():
    global cfg, state
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--height", type=int, default=48)
    ap.add_argument("--pixels", type=int, default=8)
    ap.add_argument("--fresh", action="store_true", help="ignore state.json and start a blank canvas")
    cfg = ap.parse_args()
    state = new_state()
    if STATE_FILE.exists() and not cfg.fresh:
        saved = json.loads(STATE_FILE.read_text())
        if saved.get("width") == cfg.width and saved.get("height") == cfg.height:
            state.update(saved)
            state["pixels_per_turn"] = cfg.pixels
    print(f"our-story-coworld on http://localhost:{cfg.port}  ({cfg.width}x{cfg.height}, "
          f"{cfg.pixels} px/turn)")
    ThreadingHTTPServer(("127.0.0.1", cfg.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
