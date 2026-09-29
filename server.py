"""our-story-coworld: a drawing contest on one shared pixel canvas.

Stdlib only. Run: python3 server.py [--port 8765] [--size 16] [--rounds 4] [--keep 2]
                                     [--players N] [--fresh]

Rules:
  lobby   agents join (the webpage is for watching only); the game starts when
          --players have joined, or when the host runs `play.py start`. Each agent
          gets an anonymous letter (A, B, ...). No chat: the canvas is the only channel.
  draw    each round every agent secretly submits one piece: a --size x --size
          picture placed anywhere on the canvas, even over other pieces ('.' in the
          picture is transparent). When all pieces are in, they are painted in a
          random order, so a later piece covers an earlier one where they overlap.
          A piece is every pixel on the canvas that still shows it.
  vote    each agent ranks every other piece, best first. Borda points: with P
          agents, first place gets P-1, last gets 1.
  keep    only the --keep best pieces of the round stay on the canvas; the others
          are erased. Then the next round starts.
  end     after --rounds rounds, the most total points wins.
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
        "phase": "lobby", "round": 0, "rounds": cfg.rounds, "keep": cfg.keep, "size": cfg.size,
        "width": WIDTH, "height": HEIGHT,
        "grid": [EMPTY * WIDTH for _ in range(HEIGHT)],
        "owner": [EMPTY * WIDTH for _ in range(HEIGHT)],   # letter of the piece each pixel shows
        "players": {},   # name -> {"letter", "piece": {"x", "y", "rows"} | None, "ranking", "total"}
        "log": [],       # {"round", "t", "kind", "text", "moves"}
        "history": [],   # per round: {"round", "points", "kept", "rankings"}
    }


def save():
    STATE_FILE.write_text(json.dumps(state))


def add_log(kind, text="", moves=None):
    state["log"].append({"round": state["round"], "t": time.time(),
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
    state.update(phase="draw", round=1)
    add_log("phase", f"game starts: {cfg.rounds} rounds, one {cfg.size}x{cfg.size} piece per agent "
                     f"per round, top {cfg.keep} pieces survive each round")
    add_log("turn", "round 1: draw")


def paint_pieces():
    """Paint every submitted piece in a random order, then open the vote."""
    order = [p for p in state["players"].values() if p["piece"]]
    random.shuffle(order)
    moves = []
    for p in order:
        pc, px = p["piece"], []
        for dy, row in enumerate(pc["rows"]):
            for dx, c in enumerate(row):
                x, y = pc["x"] + dx, pc["y"] + dy
                if c != EMPTY and 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    set_cell(state["grid"], x, y, c)
                    set_cell(state["owner"], x, y, p["letter"])
                    px.append([x, y, c])
        moves.append({"letter": p["letter"], "pixels": px})
        p["piece"] = None
    add_log("resolve", "painted in order: " + " ".join(p["letter"] for p in order), moves)
    state["phase"] = "vote"
    add_log("phase", f"round {state['round']} pieces are on the canvas; rank every other piece, best first")


def end_round():
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
    state["history"].append({"round": state["round"], "points": points, "kept": kept,
                             "rankings": {p["letter"]: p["ranking"] for p in state["players"].values()}})
    add_log("phase", f"round {state['round']} points: " +
            " ".join(f"{l}={points[l]}" for l in best) + f"; kept {' '.join(kept)}, erased the rest")
    for p in state["players"].values():
        p["ranking"] = None
    if state["round"] >= cfg.rounds:
        state["phase"] = "results"
        add_log("phase", "game over: " + ", ".join(
            f"{p['letter']}={n} {p['total']}" for n, p in
            sorted(state["players"].items(), key=lambda kv: -kv[1]["total"])))
    else:
        state.update(phase="draw", round=state["round"] + 1)
        add_log("turn", f"round {state['round']}: draw")


def maybe_advance():
    ps = state["players"].values()
    if state["phase"] == "draw" and all(p["piece"] for p in ps):
        paint_pieces()
    elif state["phase"] == "vote" and all(p["ranking"] for p in ps):
        end_round()


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
    state["players"][name] = {"letter": free[0], "piece": None, "ranking": None, "total": 0}
    add_log("join", f"an agent joined ({len(state['players'])} now)")
    if cfg.players and len(state["players"]) >= cfg.players:
        start_game()
    return {"ok": True, "letter": free[0]}


def do_draw(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "draw":
        raise ValueError(f"cannot draw during the {state['phase']} phase")
    if p["piece"]:
        raise ValueError("you already submitted your piece this round")
    x, y = int(body.get("x")), int(body.get("y"))
    rows = body.get("rows")
    if isinstance(rows, str):
        rows = rows.split("\n")
    rows = [r.rstrip() for r in rows or []]
    while rows and not rows[-1]:
        rows.pop()
    n = cfg.size
    if not rows or len(rows) > n or any(len(r) > n for r in rows):
        raise ValueError(f"a piece is at most {n} rows of at most {n} characters")
    for r in rows:
        for c in r:
            if c not in PALETTE and c != EMPTY:
                raise ValueError(f"unknown colour {c!r}; use one of {''.join(PALETTE)} or '.' for transparent")
    if not (0 <= x <= WIDTH - 1 and 0 <= y <= HEIGHT - 1):
        raise ValueError(f"top-left corner must be on the canvas: x 0-{WIDTH - 1}, y 0-{HEIGHT - 1}")
    if not any(c != EMPTY for r in rows for c in r):
        raise ValueError("your piece is empty")
    p["piece"] = {"x": x, "y": y, "rows": rows}
    add_log("submit", f"a piece came in ({sum(1 for q in state['players'].values() if q['piece'])}"
                      f"/{len(state['players'])})")
    maybe_advance()
    return {"ok": True}


def do_rank(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "vote":
        raise ValueError(f"cannot vote during the {state['phase']} phase")
    order = body.get("order")
    if isinstance(order, str):
        order = order.replace(",", " ").split()
    order = [str(o).strip().upper() for o in order or []]
    expected = [l for l in letters() if l != p["letter"]]
    if sorted(order) != expected:
        raise ValueError(f"rank each of {' '.join(expected)} exactly once, best first "
                         f"(your own piece {p['letter']} is excluded)")
    p["ranking"] = order
    add_log("rank", f"a vote came in ({sum(1 for q in state['players'].values() if q['ranking'])}"
                    f"/{len(state['players'])})")
    maybe_advance()
    return {"ok": True}


def do_force(body):
    """Host override: start the game, or move on past a stuck agent."""
    if state["phase"] == "lobby":
        start_game()
    elif state["phase"] == "draw":
        paint_pieces()
    elif state["phase"] == "vote":
        end_round()
    return {"ok": True, "phase": state["phase"]}


# ---- views -----------------------------------------------------------------

def status(p):
    if state["phase"] == "draw":
        return "submitted" if p["piece"] else "drawing"
    if state["phase"] == "vote":
        return "voted" if p["ranking"] else "voting"
    return "ready"


def public_state(me=None):
    s = {k: state[k] for k in ("phase", "round", "rounds", "keep", "size",
                               "width", "height", "grid", "owner", "history")}
    over = state["phase"] == "results"
    s.update(palette=PALETTE, empty=EMPTY, letters=letters(), log=state["log"][-120:],
             pieces={l: piece_size(l) for l in letters()},
             players=[{"name": n, "status": status(p),
                       **({"letter": p["letter"], "total": p["total"]} if over else {})}
                      for n, p in state["players"].items()])
    if me in state["players"]:
        p = state["players"][me]
        s["me"] = {"name": me, "letter": p["letter"], "submitted": bool(p["piece"]),
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
        return ["    (empty: nothing of this piece is visible)"]
    masked = ["".join(state["grid"][y][x] if state["owner"][y][x] == letter else EMPTY
                      for x in range(WIDTH)) for y in range(HEIGHT)]
    return grid_text(masked, range(rows[0], rows[-1] + 1))


def canvas_text(me=None):
    p = state["players"].get(me)
    mine = p["letter"] if p else None
    n = cfg.size
    lines = [{
        "lobby": f"LOBBY: waiting for the game to start. {len(state['players'])} agents joined.",
        "draw": f"DRAW: round {state['round']}/{cfg.rounds}. Submit one piece: up to {n}x{n}, anywhere.",
        "vote": f"VOTE: round {state['round']}/{cfg.rounds}. Rank every other piece, best first.",
        "results": "RESULTS: game over.",
    }[state["phase"]]]
    if p:
        extra = ""
        if state["phase"] == "draw":
            extra = "; you already submitted" if p["piece"] else "; your piece is not submitted yet"
        if state["phase"] == "vote":
            extra = "; you already voted" if p["ranking"] else "; your vote is not submitted yet"
        lines.append(f"you are {me}, your piece is {mine}, your total points: {p['total']}{extra}")
    lines.append("agents: " + ", ".join(f"{nm} ({status(q)})" for nm, q in state["players"].items()))
    lines.append("pieces on canvas (visible pixels): " + " ".join(f"{l}={piece_size(l)}" for l in letters()))
    lines.append("colours: " + " ".join(f"{k}={v}" for k, v in NAMES.items()) + " .=empty/transparent")
    lines.append(f"x = column 0-{WIDTH - 1} left to right, y = row 0-{HEIGHT - 1} top to bottom")
    lines += ["", "CANVAS"] + grid_text(state["grid"])
    lines += ["", "OWNERSHIP (which piece each pixel belongs to)"] + grid_text(state["owner"])
    if state["phase"] == "vote":
        for l in letters():
            if l != mine:
                lines += ["", f"PIECE {l}"] + piece_text(l)
    if state["history"]:
        lines.append("")
        for h in state["history"]:
            lines.append(f"round {h['round']}: points " +
                         " ".join(f"{l}={v}" for l, v in sorted(h["points"].items(), key=lambda kv: -kv[1])) +
                         f"; kept {' '.join(h['kept'])}")
    if state["phase"] == "results":
        lines.append("final: " + ", ".join(f"{q['letter']}={nm} {q['total']}" for nm, q in
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
        routes = {"/api/join": do_join, "/api/draw": do_draw,
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
    ap.add_argument("--size", type=int, default=16, help="a piece is at most size x size")
    ap.add_argument("--rounds", type=int, default=4, help="rounds per game")
    ap.add_argument("--keep", type=int, default=2, help="pieces that survive each round")
    ap.add_argument("--players", type=int, default=0,
                    help="start the game automatically once this many agents have joined")
    ap.add_argument("--fresh", action="store_true", help="ignore state.json and start a new game")
    cfg = ap.parse_args()
    state = new_state()
    if STATE_FILE.exists() and not cfg.fresh:
        saved = json.loads(STATE_FILE.read_text())
        if "rounds" in saved:
            state.update(saved)
    print(f"our-story-coworld on http://localhost:{cfg.port}  ({cfg.size}x{cfg.size} pieces, "
          f"{cfg.rounds} rounds, keep {cfg.keep})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", cfg.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
