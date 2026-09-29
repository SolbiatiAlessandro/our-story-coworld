"""our-story-coworld: a drawing contest on one shared pixel canvas.

Stdlib only. Run: python3 server.py [--port 8765] [--pixels 16] [--turns 3] [--epochs 4]
                                     [--keep 3] [--fresh]

Rules:
  lobby   players join; each gets an anonymous letter (A, B, ...). Names stay hidden
          until the end. No chat: the canvas is the only channel.
  draw    turn based, no clock. Each turn every player secretly submits up to
          --pixels pixels anywhere on the canvas, on top of anyone's, or '.' to
          erase. When all players have submitted, the moves are applied in a new
          random player order, so later moves overwrite earlier ones.
          A player's piece is every pixel that currently shows that player's move.
  rank    after --turns turns, each player ranks every other piece, best first.
          Borda points: with P players, first place gets P-1, last gets 1.
  keep    only the --keep best pieces of the epoch stay on the canvas; every other
          piece is erased. Then the next epoch starts.
  end     after --epochs epochs, the most total points wins.
"""

import argparse
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state.json"
WIDTH, HEIGHT = 64, 48
LETTERS = "ABCDEFGHIJKL"

# One character per colour so agents can read the canvas as plain text.
PALETTE = {
    "w": "#ffffff", "k": "#1a1a1a", "g": "#8a8a8a", "r": "#e23b3b",
    "o": "#f28c28", "y": "#f5d33b", "l": "#7ed957", "d": "#2e8b3d",
    "c": "#4fd1e0", "b": "#2f6fdf", "n": "#1f2f7a", "p": "#9b5de5",
    "m": "#f15bb5", "t": "#8b5a2b", "s": "#f2c9a0", "e": "#c9e7ff",
}
NAMES = dict(zip(PALETTE, "white black grey red orange yellow light-green dark-green "
                          "cyan blue navy purple magenta brown skin pale-blue".split()))
EMPTY = "."

lock = threading.Lock()
cfg = None
state = None


def new_state():
    return {
        "phase": "lobby", "epoch": 0, "turn": 0,
        "epochs": cfg.epochs, "turns": cfg.turns, "keep": cfg.keep, "pixels_per_turn": cfg.pixels,
        "width": WIDTH, "height": HEIGHT,
        "grid": [EMPTY * WIDTH for _ in range(HEIGHT)],
        "owner": [EMPTY * WIDTH for _ in range(HEIGHT)],   # letter of the player whose move shows
        "players": {},   # name -> {"letter", "queue": [[x,y,c]], "done", "ranking", "total"}
        "log": [],       # {"epoch", "turn", "t", "kind", "text", "moves"}
        "history": [],   # per epoch: {"epoch", "points", "kept", "rankings"}
    }


def save():
    STATE_FILE.write_text(json.dumps(state))


def add_log(kind, text="", moves=None):
    state["log"].append({"epoch": state["epoch"], "turn": state["turn"], "t": time.time(),
                         "kind": kind, "text": text, "moves": moves or []})
    state["log"] = state["log"][-300:]


def letters():
    return sorted(p["letter"] for p in state["players"].values())


def set_cell(grid, x, y, ch):
    row = grid[y]
    grid[y] = row[:x] + ch + row[x + 1:]


def piece_size(letter):
    return sum(row.count(letter) for row in state["owner"])


def get_player(name):
    name = (name or "").strip()[:24]
    if name not in state["players"]:
        raise ValueError(f"unknown player {name!r}; join first")
    return name, state["players"][name]


# ---- phase changes ---------------------------------------------------------

def start_game():
    if state["phase"] != "lobby":
        raise ValueError("game already started")
    if len(state["players"]) < 2:
        raise ValueError("need at least 2 players")
    state.update(phase="draw", epoch=1, turn=1)
    add_log("phase", f"game starts: {cfg.epochs} epochs of {cfg.turns} turns, "
                     f"{cfg.pixels} pixels per turn, top {cfg.keep} pieces survive each epoch")
    add_log("turn", "epoch 1, turn 1")


def resolve_turn():
    """Apply every queued move in a random player order, then start the next turn."""
    order = list(state["players"].values())
    random.shuffle(order)
    moves = []
    for p in order:
        for x, y, c in p["queue"]:
            set_cell(state["grid"], x, y, c)
            set_cell(state["owner"], x, y, EMPTY if c == EMPTY else p["letter"])
        if p["queue"]:
            moves.append({"letter": p["letter"], "pixels": p["queue"]})
        p["queue"], p["done"] = [], False
    add_log("resolve", "order: " + " ".join(p["letter"] for p in order), moves)
    if state["turn"] >= cfg.turns:
        state["phase"] = "rank"
        add_log("phase", f"epoch {state['epoch']} drawing is over; rank every other piece, best first")
    else:
        state["turn"] += 1
        add_log("turn", f"epoch {state['epoch']}, turn {state['turn']}")


def end_epoch():
    ls = letters()
    points = {l: 0 for l in ls}
    for p in state["players"].values():
        for i, l in enumerate(p["ranking"] or []):
            points[l] += len(ls) - 1 - i
    for p in state["players"].values():
        p["total"] += points[p["letter"]]
    best = sorted(ls, key=lambda l: -points[l])
    cutoff = points[best[min(cfg.keep, len(best)) - 1]]
    kept = [l for l in best if points[l] >= cutoff]   # ties at the cutoff all survive
    for y in range(HEIGHT):
        for x in range(WIDTH):
            o = state["owner"][y][x]
            if o != EMPTY and o not in kept:
                set_cell(state["grid"], x, y, EMPTY)
                set_cell(state["owner"], x, y, EMPTY)
    state["history"].append({"epoch": state["epoch"], "points": points, "kept": kept,
                             "rankings": {p["letter"]: p["ranking"] for p in state["players"].values()}})
    add_log("phase", f"epoch {state['epoch']} points: " +
            " ".join(f"{l}={points[l]}" for l in best) + f"; kept {' '.join(kept)}, erased the rest")
    for p in state["players"].values():
        p["ranking"] = None
    if state["epoch"] >= cfg.epochs:
        state["phase"] = "results"
        add_log("phase", "game over: " + ", ".join(
            f"{p['letter']}={n} {p['total']}" for n, p in
            sorted(state["players"].items(), key=lambda kv: -kv[1]["total"])))
    else:
        state.update(phase="draw", epoch=state["epoch"] + 1, turn=1)
        add_log("turn", f"epoch {state['epoch']}, turn 1")


def maybe_advance():
    ps = state["players"].values()
    if state["phase"] == "draw" and all(p["done"] or len(p["queue"]) >= cfg.pixels for p in ps):
        resolve_turn()
    elif state["phase"] == "rank" and all(p["ranking"] for p in ps):
        end_epoch()


# ---- actions ---------------------------------------------------------------

def do_join(body):
    name = (body.get("name") or "").strip()[:24]
    if not name:
        raise ValueError("name required")
    if name in state["players"]:
        return {"ok": True, "letter": state["players"][name]["letter"]}
    if state["phase"] != "lobby":
        raise ValueError("game already started; wait for the next game")
    free = [l for l in LETTERS if l not in letters()]
    if not free:
        raise ValueError("game is full")
    state["players"][name] = {"letter": free[0], "queue": [], "done": False, "ranking": None, "total": 0}
    add_log("join", f"a player joined ({len(state['players'])} now)")
    return {"ok": True, "letter": free[0]}


def do_place(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "draw":
        raise ValueError(f"cannot draw during the {state['phase']} phase")
    if p["done"]:
        raise ValueError("you already submitted this turn; wait for the next one")
    pixels = body.get("pixels") or []
    left = cfg.pixels - len(p["queue"])
    if len(pixels) > left:
        raise ValueError(f"only {left} pixels left this turn (asked for {len(pixels)})")
    queued = []
    for px in pixels:
        x, y, c = int(px[0]), int(px[1]), str(px[2])
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise ValueError(f"({x},{y}) is off the canvas; x is 0-{WIDTH - 1}, y is 0-{HEIGHT - 1}")
        if c not in PALETTE and c != EMPTY:
            raise ValueError(f"unknown colour {c!r}; use one of {''.join(PALETTE)} or '.' to erase")
        queued.append([x, y, c])
    p["queue"] += queued
    turn = (state["epoch"], state["turn"])
    maybe_advance()
    return {"ok": True, "queued": len(queued), "pixels_left": max(0, cfg.pixels - len(p["queue"])),
            "turn_resolved": turn != (state["epoch"], state["turn"]) or state["phase"] != "draw"}


def do_done(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "draw":
        raise ValueError(f"nothing to submit during the {state['phase']} phase")
    p["done"] = True
    maybe_advance()
    return {"ok": True}


def do_rank(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "rank":
        raise ValueError(f"cannot rank during the {state['phase']} phase")
    order = body.get("order")
    if isinstance(order, str):
        order = order.replace(",", " ").split()
    order = [str(o).strip().upper() for o in order or []]
    expected = [l for l in letters() if l != p["letter"]]
    if sorted(order) != expected:
        raise ValueError(f"rank each of {' '.join(expected)} exactly once, best first "
                         f"(your own piece {p['letter']} is excluded)")
    p["ranking"] = order
    add_log("rank", f"a ranking came in ({sum(1 for q in state['players'].values() if q['ranking'])}"
                    f"/{len(state['players'])})")
    maybe_advance()
    return {"ok": True}


def do_force(body):
    """Host override: start the game, or move on past a stuck player."""
    if state["phase"] == "lobby":
        start_game()
    elif state["phase"] == "draw":
        resolve_turn()
    elif state["phase"] == "rank":
        end_epoch()
    return {"ok": True, "phase": state["phase"]}


# ---- views -----------------------------------------------------------------

def status(p):
    if state["phase"] == "draw":
        return "submitted" if p["done"] or len(p["queue"]) >= cfg.pixels else "thinking"
    if state["phase"] == "rank":
        return "ranked" if p["ranking"] else "ranking"
    return "ready"


def public_state(me=None):
    s = {k: state[k] for k in ("phase", "epoch", "turn", "epochs", "turns", "keep",
                               "pixels_per_turn", "width", "height", "grid", "owner", "history")}
    over = state["phase"] == "results"
    s.update(palette=PALETTE, empty=EMPTY, letters=letters(), log=state["log"][-120:],
             pieces={l: piece_size(l) for l in letters()},
             players=[{"name": n, "status": status(p),
                       **({"letter": p["letter"], "total": p["total"]} if over else {})}
                      for n, p in state["players"].items()])
    if me in state["players"]:
        p = state["players"][me]
        s["me"] = {"name": me, "letter": p["letter"], "queue": p["queue"], "done": p["done"],
                   "ranking": p["ranking"], "total": p["total"]}
    return s


def grid_text(grid, rows=None):
    tens = "".join(str(x // 10) for x in range(WIDTH))
    units = "".join(str(x % 10) for x in range(WIDTH))
    out = ["    " + tens, "    " + units]
    for y in rows if rows is not None else range(HEIGHT):
        out.append(f"{y:3d} {grid[y]}")
    return out


def piece_text(letter):
    """The canvas with only this piece's pixels, cropped to the rows it uses."""
    rows = [y for y in range(HEIGHT) if letter in state["owner"][y]]
    if not rows:
        return ["    (empty: nothing of this piece is on the canvas)"]
    masked = ["".join(state["grid"][y][x] if state["owner"][y][x] == letter else EMPTY
                      for x in range(WIDTH)) for y in range(HEIGHT)]
    return grid_text(masked, range(rows[0], rows[-1] + 1))


def canvas_text(me=None):
    p = state["players"].get(me)
    mine = p["letter"] if p else None
    lines = [{
        "lobby": f"LOBBY: waiting for the host to start. {len(state['players'])} players joined.",
        "draw": f"DRAW: epoch {state['epoch']}/{cfg.epochs}, turn {state['turn']}/{cfg.turns}. "
                f"Submit up to {cfg.pixels} pixels anywhere.",
        "rank": f"RANK: epoch {state['epoch']}/{cfg.epochs} drawing is over. Rank every other piece, best first.",
        "results": "RESULTS: game over.",
    }[state["phase"]]]
    if p:
        extra = ""
        if state["phase"] == "draw":
            extra = ("; you already submitted this turn" if p["done"] or len(p["queue"]) >= cfg.pixels
                     else f"; pixels left this turn: {cfg.pixels - len(p['queue'])}")
        lines.append(f"you are {me}, your piece is {mine}, your total points: {p['total']}{extra}")
    lines.append("players: " + ", ".join(f"{n} ({status(q)})" for n, q in state["players"].items()))
    lines.append("pieces (pixels on canvas): " + " ".join(f"{l}={piece_size(l)}" for l in letters()))
    lines.append("colours: " + " ".join(f"{k}={v}" for k, v in NAMES.items()) + " .=empty")
    lines.append(f"x = column 0-{WIDTH - 1} left to right, y = row 0-{HEIGHT - 1} top to bottom")
    lines += ["", "CANVAS"] + grid_text(state["grid"])
    lines += ["", "OWNERSHIP (which piece each pixel belongs to)"] + grid_text(state["owner"])
    if state["phase"] == "rank":
        for l in letters():
            if l != mine:
                lines += ["", f"PIECE {l}"] + piece_text(l)
    if state["history"]:
        lines.append("")
        for h in state["history"]:
            lines.append(f"epoch {h['epoch']}: points " +
                         " ".join(f"{l}={v}" for l, v in sorted(h["points"].items(), key=lambda kv: -kv[1])) +
                         f"; kept {' '.join(h['kept'])}")
    if state["phase"] == "results":
        lines.append("final: " + ", ".join(f"{q['letter']}={n} {q['total']}" for n, q in
                                           sorted(state["players"].items(), key=lambda kv: -kv[1]["total"])))
    return "\n".join(lines) + "\n"


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
        url = urlparse(self.path)
        me = parse_qs(url.query).get("name", [None])[0]
        with lock:
            if url.path in ("/", "/index.html"):
                return self.send(200, (ROOT / "index.html").read_text(), "text/html")
            if url.path == "/api/state":
                return self.send(200, public_state(me))
            if url.path == "/api/canvas.txt":
                return self.send(200, canvas_text(me), "text/plain")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        global state
        path = urlparse(self.path).path
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "body must be JSON"})
        routes = {"/api/join": do_join, "/api/place": do_place, "/api/done": do_done,
                  "/api/rank": do_rank, "/api/force": do_force}
        with lock:
            if path == "/api/reset":
                state = new_state()
                save()
                return self.send(200, {"ok": True})
            if path not in routes:
                return self.send(404, {"error": "not found"})
            try:
                result = routes[path](body)
                save()
                return self.send(200, result)
            except (ValueError, TypeError, IndexError) as e:
                return self.send(400, {"error": str(e)})


def main():
    global cfg, state
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--pixels", type=int, default=16, help="pixels per player per turn")
    ap.add_argument("--turns", type=int, default=3, help="drawing turns per epoch")
    ap.add_argument("--epochs", type=int, default=4, help="epochs per game")
    ap.add_argument("--keep", type=int, default=3, help="pieces that survive each epoch")
    ap.add_argument("--fresh", action="store_true", help="ignore state.json and start a new game")
    cfg = ap.parse_args()
    state = new_state()
    if STATE_FILE.exists() and not cfg.fresh:
        saved = json.loads(STATE_FILE.read_text())
        if "owner" in saved:
            state.update(saved)
    print(f"our-story-coworld on http://localhost:{cfg.port}  ({cfg.pixels} px/turn, "
          f"{cfg.turns} turns x {cfg.epochs} epochs, keep {cfg.keep})")
    ThreadingHTTPServer(("127.0.0.1", cfg.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
