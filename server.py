"""our-story-coworld: a drawing contest on one shared pixel canvas.

Stdlib only. Run: python3 server.py [--port 8765] [--size 32] [--rounds 5] [--keep 1]
                                     [--players N] [--fresh]

Rules:
  lobby   agents join (the webpage is for watching only); the game starts when
          --players have joined, or when the host runs `host.py start`. Each agent
          gets an anonymous letter (A, B, ...). No chat: the canvas is the only channel.
  theme   the whole game has one theme (--theme, default "AI age"), shown to the agents.
  draw    each round every agent secretly submits a new piece: a picture of up to
          --size x --size placed anywhere, even over earlier pieces ('.' is
          transparent), plus one sentence on why it drew that. Each round's pieces
          are new pieces, never merged with earlier ones. When all are in, they
          are painted in a random order; where they overlap, the later one covers.
  vote    each agent ranks this round's other pieces, best first, with one sentence
          on why. Borda points: with P agents, first place gets P-1, last gets 1.
  keep    only the --keep best pieces of the round stay on the canvas; this
          round's other pieces are erased. Winners of earlier rounds stay unless
          covered.
  end     after --rounds rounds, the most total points wins.

Rationales are shown on the webpage, never to the agents during the game.
"""

import argparse
import json
import random
import struct
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state.json"
ARCHIVE = ROOT / "games"
WIDTH, HEIGHT = 128, 96
LETTERS = "ABCDEFGHIJKL"
DEFAULT_THEME = "AI age"   # one theme for the whole game; change with --theme
OLD = "#"   # ownership mark for surviving pieces from earlier rounds

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
        "theme": cfg.theme,
        "width": WIDTH, "height": HEIGHT, "started": time.time(),
        "grid": [EMPTY * WIDTH for _ in range(HEIGHT)],
        "owner": [[""] * WIDTH for _ in range(HEIGHT)],   # piece id ("2B" = round 2, letter B) per pixel
        "players": {},   # name -> {"letter", "model", "submitted", "ranking", "vote_why", "total"}
        "pieces": {},    # id -> {"round", "letter", "x", "y", "rows", "why", "points", "kept"}
        "log": [],       # {"round", "t", "kind", "text", "moves"}
        "history": [],   # per round: {"round", "points", "kept", "rankings", "why"}
    }


def save():
    STATE_FILE.write_text(json.dumps(state))


def archive():
    """Keep a copy of a game that got past the lobby before it is wiped."""
    if state and state["phase"] != "lobby":
        ARCHIVE.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(state.get("started", time.time())))
        (ARCHIVE / f"game-{stamp}.json").write_text(json.dumps(state, indent=1))


def add_log(kind, text="", moves=None):
    state["log"].append({"round": state["round"], "t": time.time(),
                         "kind": kind, "text": text, "moves": moves or []})
    state["log"] = state["log"][-300:]


def letters():
    return sorted(p["letter"] for p in state["players"].values())


def theme():
    return state.get("theme") or DEFAULT_THEME


def pid(letter, rnd=None):
    return f"{rnd or state['round']}{letter}"


def set_cell(x, y, ch, owner):
    row = state["grid"][y]
    state["grid"][y] = row[:x] + ch + row[x + 1:]
    state["owner"][y][x] = owner


def visible(piece_id):
    return sum(row.count(piece_id) for row in state["owner"])


def get_player(name):
    name = (name or "").strip()[:24]
    if name not in state["players"]:
        raise ValueError(f"unknown player {name!r}; join first")
    return name, state["players"][name]


def sentence(body, key, what):
    text = " ".join(str(body.get(key) or "").split())
    if not text:
        raise ValueError(f"add one sentence on why {what}")
    return text[:300]


# ---- phase changes ---------------------------------------------------------

def start_game():
    if state["phase"] != "lobby":
        raise ValueError("game already started")
    if len(state["players"]) < 2:
        raise ValueError("need at least 2 players")
    state.update(phase="draw", round=1, started=time.time())
    add_log("phase", f"game starts. Theme: {theme()}. {cfg.rounds} rounds, one new {cfg.size}x{cfg.size} piece per agent "
                     f"per round, the top {cfg.keep} of each round stays")
    add_log("turn", "round 1: draw")


def paint_pieces():
    """Paint this round's pieces in a random order, then open the vote."""
    state["base_grid"] = list(state["grid"])   # the canvas before this round's pieces
    mine = [p for p in state["players"].values() if p["submitted"]]
    random.shuffle(mine)
    moves = []
    for p in mine:
        pc, px = state["pieces"][pid(p["letter"])], []
        for dy, row in enumerate(pc["rows"]):
            for dx, c in enumerate(row):
                x, y = pc["x"] + dx, pc["y"] + dy
                if c != EMPTY and 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    set_cell(x, y, c, pid(p["letter"]))
                    px.append([x, y, c])
        moves.append({"letter": p["letter"], "pixels": px})
    add_log("resolve", "painted in order: " + " ".join(p["letter"] for p in mine), moves)
    state["phase"] = "vote"
    add_log("phase", f"round {state['round']} pieces are on the canvas; vote")


def end_round():
    rnd = state["round"]
    ls = [l for l in letters() if pid(l) in state["pieces"]]
    points = {l: 0 for l in ls}
    for p in state["players"].values():
        for i, l in enumerate(p["ranking"] or []):
            if l in points:
                points[l] += len(ls) - 1 - i
    for p in state["players"].values():
        p["total"] += points.get(p["letter"], 0)
    best = sorted(ls, key=lambda l: -points[l])
    kept = []
    if best:
        cutoff = points[best[min(cfg.keep, len(best)) - 1]]
        kept = [l for l in best if points[l] >= cutoff]   # ties at the cutoff all stay
    for l in ls:
        state["pieces"][pid(l)].update(points=points[l], kept=l in kept)
    losers = {pid(l) for l in ls if l not in kept}
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if state["owner"][y][x] in losers:
                set_cell(x, y, EMPTY, "")
    state["history"].append({
        "round": rnd, "points": points, "kept": kept,
        "rankings": {p["letter"]: p["ranking"] for p in state["players"].values()},
        "why": {p["letter"]: p["vote_why"] for p in state["players"].values()}})
    add_log("phase", f"round {rnd} points: " + " ".join(f"{l}={points[l]}" for l in best) +
            f"; {' '.join(kept)} stays, the rest of this round is erased")
    for p in state["players"].values():
        p.update(submitted=False, ranking=None, vote_why=None)
    if rnd >= cfg.rounds:
        state["phase"] = "results"
        add_log("phase", "game over: " + ", ".join(
            f"{p['letter']}={n} {p['total']}" for n, p in
            sorted(state["players"].items(), key=lambda kv: -kv[1]["total"])))
    else:
        state.update(phase="draw", round=rnd + 1)
        add_log("turn", f"round {state['round']}: draw")


def maybe_advance():
    ps = state["players"].values()
    if state["phase"] == "draw" and all(p["submitted"] for p in ps):
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
    state["players"][name] = {"letter": free[0], "model": str(body.get("model") or "")[:60],
                              "submitted": False, "ranking": None,
                              "vote_why": None, "total": 0}
    add_log("join", f"an agent joined ({len(state['players'])} now)")
    if cfg.players and len(state["players"]) >= cfg.players:
        start_game()
    return {"ok": True, "letter": free[0]}


def do_draw(body):
    name, p = get_player(body.get("name"))
    if state["phase"] != "draw":
        raise ValueError(f"cannot draw during the {state['phase']} phase")
    if p["submitted"]:
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
    why = sentence(body, "why", "you drew this")
    state["pieces"][pid(p["letter"])] = {"round": state["round"], "letter": p["letter"], "x": x, "y": y,
                                         "rows": rows, "why": why, "points": None, "kept": None}
    p["submitted"] = True
    add_log("submit", f"a piece came in ({sum(1 for q in state['players'].values() if q['submitted'])}"
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
    expected = [l for l in letters() if l != p["letter"] and pid(l) in state["pieces"]]
    if sorted(order) != expected:
        raise ValueError(f"rank each of {' '.join(expected)} exactly once, best first "
                         f"(your own piece {p['letter']} is excluded)")
    p["vote_why"] = sentence(body, "why", "you voted this way")
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
        return "submitted" if p["submitted"] else "drawing"
    if state["phase"] == "vote":
        return "voted" if p["ranking"] else "voting"
    return "ready"


def public_state(me=None):
    """Everything, including rationales: this feeds the watch-only webpage."""
    s = {k: state[k] for k in ("phase", "round", "rounds", "keep", "size", "width", "height",
                               "grid", "owner", "history", "theme")}
    over = state["phase"] == "results"
    # This round's pieces are hidden until painted.
    s["pieces"] = {i: {**pc, "visible": visible(i)} for i, pc in state["pieces"].items()
                   if not (pc["round"] == state["round"] and state["phase"] == "draw")}
    s.update(palette=PALETTE, empty=EMPTY, letters=letters(), log=state["log"][-120:],
             players=[{"name": n, "status": status(p),
                       **({"letter": p["letter"], "total": p["total"], "model": p.get("model", "")}
                          if over else {})}
                      for n, p in state["players"].items()],
             votes={p["letter"]: {"ranking": p["ranking"], "why": p["vote_why"]}
                    for p in state["players"].values() if p["ranking"]})
    if me in state["players"]:
        p = state["players"][me]
        s["me"] = {"name": me, "letter": p["letter"], "submitted": p["submitted"],
                   "ranking": p["ranking"], "total": p["total"]}
    return s


def grid_text(grid, rows=None):
    hundreds = "".join(str(x // 100) for x in range(WIDTH))
    tens = "".join(str(x // 10 % 10) for x in range(WIDTH))
    units = "".join(str(x % 10) for x in range(WIDTH))
    out = ["    " + hundreds, "    " + tens, "    " + units]
    for y in rows if rows is not None else range(HEIGHT):
        out.append(f"{y:3d} {grid[y]}")
    return out


def owner_text():
    """One character per pixel: this round's letter, '#' for earlier winners, '.' empty."""
    rnd = str(state["round"])
    return ["".join(o[len(rnd):] if o and o[:-1] == rnd else (OLD if o else EMPTY) for o in row)
            for row in state["owner"]]


def piece_text(piece_id):
    """The canvas with only this piece's pixels, cropped to the rows it uses."""
    rows = [y for y in range(HEIGHT) if piece_id in state["owner"][y]]
    if not rows:
        return ["    (nothing of this piece is visible)"]
    masked = ["".join(state["grid"][y][x] if state["owner"][y][x] == piece_id else EMPTY
                      for x in range(WIDTH)) for y in range(HEIGHT)]
    return grid_text(masked, range(rows[0], rows[-1] + 1))


def canvas_text(me=None):
    p = state["players"].get(me)
    mine = p["letter"] if p else None
    n = cfg.size
    lines = [{
        "lobby": f"LOBBY: waiting for the game to start. {len(state['players'])} agents joined.",
        "draw": f"DRAW: round {state['round']}/{cfg.rounds}. THEME: {theme()}. "
                f"Submit one new piece: up to {n}x{n}, anywhere.",
        "vote": f"VOTE: round {state['round']}/{cfg.rounds}. THEME: {theme()}. "
                f"Rank this round's other pieces, best first.",
        "results": "RESULTS: game over.",
    }[state["phase"]]]
    if p:
        extra = ""
        if state["phase"] == "draw":
            extra = "; you already submitted" if p["submitted"] else "; your piece is not submitted yet"
        if state["phase"] == "vote":
            extra = "; you already voted" if p["ranking"] else "; your vote is not submitted yet"
        lines.append(f"you are {me}, your letter is {mine}, your total points: {p['total']}{extra}")
    lines.append("agents: " + ", ".join(f"{nm} ({status(q)})" for nm, q in state["players"].items()))
    lines.append("colours: " + " ".join(f"{k}={v}" for k, v in NAMES.items()) + " .=empty/transparent")
    lines.append(f"x = column 0-{WIDTH - 1} left to right, y = row 0-{HEIGHT - 1} top to bottom")
    lines += ["", "CANVAS"] + grid_text(state["grid"])
    lines += ["", f"OWNERSHIP (letter = this round's piece, {OLD} = winner of an earlier round)"]
    lines += grid_text(owner_text())
    if state["phase"] == "vote":
        for l in letters():
            if l != mine and pid(l) in state["pieces"]:
                lines += ["", f"PIECE {l}"] + piece_text(pid(l))
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


# ---- PNG images (stdlib only), so agents can look at pieces instead of reading letters

BACKGROUND = (244, 241, 234)


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def png(pixels, scale):
    """pixels: list of rows of (r, g, b). Returns PNG bytes, each pixel drawn scale x scale."""
    raw = bytearray()
    for row in pixels:
        line = b"".join(bytes(c) * scale for c in row)
        for _ in range(scale):
            raw += b"\x00" + line
    h, w = len(pixels) * scale, len(pixels[0]) * scale

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def canvas_png(scale=6):
    return png([[hex_rgb(PALETTE[c]) if c != EMPTY else BACKGROUND for c in row]
                for row in state["grid"]], scale)


def piece_png(letter, scale=6):
    """The full canvas as it was before this round, with only this piece painted on it,
    whole: what the canvas would look like if this piece wins, without the other new pieces."""
    pc = state["pieces"].get(pid(letter))
    if not pc:
        raise ValueError(f"no piece {letter} this round")
    grid = [list(r) for r in state.get("base_grid") or state["grid"]]
    for dy, row in enumerate(pc["rows"]):
        for dx, c in enumerate(row):
            x, y = pc["x"] + dx, pc["y"] + dy
            if c != EMPTY and 0 <= x < WIDTH and 0 <= y < HEIGHT:
                grid[y][x] = c
    return png([[hex_rgb(PALETTE[c]) if c != EMPTY else BACKGROUND for c in row] for row in grid], scale)


def league():
    """Standings per model over every finished game in games/ (players that carry a model tag)."""
    table = {}
    for f in sorted(ARCHIVE.glob("game-*.json")):
        try:
            g = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if g.get("phase") != "results":
            continue
        ps = [p for p in g["players"].values() if p.get("model")]
        if not ps:
            continue
        top = max(p["total"] for p in g["players"].values())
        for p in ps:
            row = table.setdefault(p["model"], {"model": p["model"], "games": 0, "points": 0,
                                                "wins": 0, "rounds_won": 0})
            row["games"] += 1
            row["points"] += p["total"]
            row["wins"] += p["total"] == top
            row["rounds_won"] += sum(p["letter"] in h["kept"] for h in g["history"])
    rows = list(table.values())
    for r in rows:
        r["avg_points"] = round(r["points"] / r["games"], 2)
    return sorted(rows, key=lambda r: (-r["avg_points"], -r["wins"]))


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

    def send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
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
            if url.path == "/api/league":
                return self.send(200, league())
            if url.path == "/api/canvas.png":
                return self.send_bytes(canvas_png(), "image/png")
            if url.path.startswith("/api/piece/") and url.path.endswith(".png"):
                if state["phase"] != "vote":
                    return self.send(400, {"error": "pieces are shown only during the vote"})
                try:
                    return self.send_bytes(piece_png(url.path[len("/api/piece/"):-4].upper()), "image/png")
                except ValueError as e:
                    return self.send(404, {"error": str(e)})
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
                archive()
                state = new_state()
                save()
                return self.send(200, {"ok": True})
            if path not in routes:
                return self.send(404, {"error": "not found"})
            try:
                result = routes[path](body)
                save()
                if state["phase"] == "results":
                    archive()
                return self.send(200, result)
            except (ValueError, TypeError, IndexError) as e:
                return self.send(400, {"error": str(e)})


def main():
    global cfg, state
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--size", type=int, default=32, help="a piece is at most size x size")
    ap.add_argument("--rounds", type=int, default=5, help="rounds per game")
    ap.add_argument("--theme", default=DEFAULT_THEME, help="theme of the whole game")
    ap.add_argument("--keep", type=int, default=1, help="pieces of each round that stay")
    ap.add_argument("--players", type=int, default=0,
                    help="start the game automatically once this many agents have joined")
    ap.add_argument("--fresh", action="store_true", help="ignore state.json and start a new game")
    cfg = ap.parse_args()
    state = new_state()
    if STATE_FILE.exists() and not cfg.fresh:
        saved = json.loads(STATE_FILE.read_text())
        if "pieces" in saved and isinstance(saved.get("owner", [[]])[0], list):
            state.update(saved)
    print(f"our-story-coworld on http://localhost:{cfg.port}  ({cfg.size}x{cfg.size} pieces, "
          f"{cfg.rounds} rounds, keep {cfg.keep})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", cfg.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
