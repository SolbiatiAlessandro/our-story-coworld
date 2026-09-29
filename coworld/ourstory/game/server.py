"""Our Story coworld game server.

Env (Coworld runtime contract): COGAME_CONFIG_URI, COGAME_RESULTS_URI, COGAME_SAVE_REPLAY_URI,
optional COGAME_RESULTS_METHOD / COGAME_SAVE_REPLAY_METHOD (PUT or POST), COGAME_HOST, COGAME_PORT.
Protocol: see ourstory/docs/PLAYER_PROTOCOL.md and GLOBAL_PROTOCOL.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from ourstory.engine import COLOUR_NAMES, Game, InvalidAction
from ourstory.render import png_b64

CLIENT_DIR = Path(__file__).parent / "client"
GAME_HOST = os.environ.get("COGAME_HOST", "0.0.0.0")
GAME_PORT = int(os.environ.get("COGAME_PORT", "8080"))
HTTP_USER_AGENT = "coworld-our-story/0.1"


def read_data(uri: str) -> bytes:
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        with urlopen(Request(uri, headers={"User-Agent": HTTP_USER_AGENT}), timeout=30) as response:
            return response.read()
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).read_bytes()
    if parsed.scheme == "":
        return Path(uri).read_bytes()
    raise ValueError(f"Unsupported URI: {uri}")


def write_data(uri: str, data: str, *, content_type: str, env_method: str) -> None:
    method = os.environ.get(env_method, "PUT").upper()
    if method not in {"POST", "PUT"}:
        raise ValueError(f"{env_method} must be PUT or POST")
    body = data.encode()
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        request = Request(uri, data=body, method=cast(Literal["POST", "PUT"], method))
        request.add_header("Content-Type", content_type)
        request.add_header("User-Agent", HTTP_USER_AGENT)
        with urlopen(request, timeout=60):
            return
    path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


CONFIG: dict[str, Any] = json.loads(read_data(os.environ["COGAME_CONFIG_URI"]))
RESULTS_URI = os.environ["COGAME_RESULTS_URI"]
REPLAY_URI = os.environ["COGAME_SAVE_REPLAY_URI"]
TOKENS: list[str] = CONFIG["tokens"]
PLAYER_NAMES = [p["name"] for p in CONFIG.get("players", [])] or [f"player {i}" for i in range(len(TOKENS))]
CONNECT_TIMEOUT = float(CONFIG.get("player_connect_timeout_seconds", 180))
ACTION_TIMEOUT = float(CONFIG.get("action_timeout_seconds", 180))
INCLUDE_IMAGES = bool(CONFIG.get("include_images", True))

game = Game(players=len(TOKENS), width=CONFIG.get("width", 128), height=CONFIG.get("height", 96),
            size=CONFIG.get("size", 32), rounds=CONFIG.get("rounds", 5), keep=CONFIG.get("keep", 1),
            theme=CONFIG.get("theme", "AI age"), seed=CONFIG.get("seed", 0))


class State:
    def __init__(self) -> None:
        self.sockets: dict[int, WebSocket] = {}
        self.step = 0
        self.acted: set[int] = set()
        self.frames: list[dict[str, Any]] = []
        self.started = False
        self.done = False
        self.version = 0   # bumps whenever spectators should get a new snapshot


state = State()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    timeout_task = asyncio.create_task(_start_after_connect_timeout())
    yield
    timeout_task.cancel()
    with suppress(asyncio.CancelledError):
        await timeout_task


app = FastAPI(lifespan=lifespan)
server: uvicorn.Server


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/client/global")
def global_client() -> HTMLResponse:
    return HTMLResponse((CLIENT_DIR / "viewer.html").read_text())


@app.get("/client/player")
def player_client() -> HTMLResponse:
    return HTMLResponse((CLIENT_DIR / "viewer.html").read_text())


@app.websocket("/global")
async def global_socket(websocket: WebSocket) -> None:
    await websocket.accept()

    async def send_snapshots() -> None:
        seen = -1
        while True:
            if state.version != seen:
                seen = state.version
                await websocket.send_json(snapshot())
                if state.done:
                    return
            await asyncio.sleep(0.2)

    async def drain() -> None:
        with suppress(WebSocketDisconnect):
            async for _ in websocket.iter_text():
                pass

    tasks = {asyncio.create_task(send_snapshots()), asyncio.create_task(drain())}
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


@app.websocket("/player")
async def player_socket(websocket: WebSocket) -> None:
    try:
        slot = int(websocket.query_params.get("slot", "-1"))
    except ValueError:
        slot = -1
    token = websocket.query_params.get("token", "")
    if not (0 <= slot < len(TOKENS)) or TOKENS[slot] != token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    state.sockets[slot] = websocket
    await websocket.send_json(welcome(slot))
    if state.started and not state.done and slot not in state.acted:
        await websocket.send_json(observation(slot))
    if len(state.sockets) == len(TOKENS) and not state.started:
        state.started = True
        asyncio.create_task(play())
    try:
        async for raw in websocket.iter_text():
            await handle_action(slot, websocket, raw)
    except WebSocketDisconnect:
        pass
    finally:
        if state.sockets.get(slot) is websocket:
            del state.sockets[slot]


async def handle_action(slot: int, websocket: WebSocket, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "send JSON"})
        return
    if not isinstance(msg, dict) or msg.get("step") != state.step or not state.started or state.done:
        await websocket.send_json({"type": "error", "step": state.step,
                                   "message": f"stale or unexpected message; the current step is {state.step}"})
        return
    if slot in state.acted:
        await websocket.send_json({"type": "error", "step": state.step, "message": "already accepted this step"})
        return
    try:
        if game.phase == "draw":
            piece = msg.get("piece") or {}
            game.submit_piece(slot, piece.get("x"), piece.get("y"), piece.get("rows"), msg.get("why"))
        elif game.phase == "vote":
            if not game.rankable(slot):
                raise InvalidAction("nothing to rank this round")
            game.submit_vote(slot, msg.get("ranking"), msg.get("why"))
        else:
            raise InvalidAction("the game is not accepting actions")
    except InvalidAction as e:
        await websocket.send_json({"type": "error", "step": state.step, "message": str(e)})
        return
    state.acted.add(slot)
    state.version += 1
    await websocket.send_json({"type": "accepted", "step": state.step})


async def _start_after_connect_timeout() -> None:
    await asyncio.sleep(CONNECT_TIMEOUT)
    if not state.started and not state.done:
        state.started = True
        asyncio.create_task(play())


async def run_step() -> None:
    """Send every connected seat its observation, then wait until all have acted or time runs out."""
    state.step += 1
    state.acted = set()
    # In the vote, a seat with nothing to rank has nothing to do.
    idle = {s for s in range(len(TOKENS)) if game.phase == "vote" and not game.rankable(s)}
    state.acted |= idle
    for slot, ws in list(state.sockets.items()):
        if slot not in idle:
            with suppress(Exception):
                await ws.send_json(observation(slot))
    deadline = time.monotonic() + ACTION_TIMEOUT
    while time.monotonic() < deadline:
        if all(s in state.acted for s in state.sockets):
            break   # every connected seat has acted (or nobody is connected)
        await asyncio.sleep(0.2)


async def play() -> None:
    await asyncio.sleep(0.3)
    game.start()
    record()
    while game.phase != "done":
        await run_step()                       # draw
        game.paint()
        record()
        await run_step()                       # vote
        game.end_round()
        record()
    results = game.results(PLAYER_NAMES)
    replay = {"version": 1, "config": {k: v for k, v in CONFIG.items() if k != "tokens"},
              "player_names": PLAYER_NAMES, "letters": game.letters, "frames": state.frames, "results": results}
    write_data(RESULTS_URI, json.dumps(results), content_type="application/json", env_method="COGAME_RESULTS_METHOD")
    write_data(REPLAY_URI, json.dumps(replay), content_type="application/json", env_method="COGAME_SAVE_REPLAY_METHOD")
    state.done = True
    state.version += 1
    for slot, ws in list(state.sockets.items()):
        with suppress(Exception):
            await ws.send_json({"type": "final", "slot": slot, "letter": game.letters[slot], **results})
    await asyncio.sleep(1.0)
    server.should_exit = True


def record() -> None:
    state.frames.append(snapshot())
    state.version += 1


# ---- messages -----------------------------------------------------------------

RULES = (
    "Our Story: a drawing contest on one shared pixel canvas. The game has one theme. Each round every "
    "player submits one new piece (up to size x size characters, '.' transparent) anywhere on the canvas, "
    "with one sentence on why. Pieces are painted in a random order; overlaps: the later one covers. Then "
    "every player ranks this round's other pieces best first, with one sentence on why. Borda points: with "
    "P pieces, first gets P-1, last gets 1. Only the top piece of the round stays; the rest of this round is "
    "erased. Earlier winners stay unless covered. Most total points wins. Players cannot talk to each other."
)


def welcome(slot: int) -> dict[str, Any]:
    return {"type": "welcome", "slot": slot, "letter": game.letters[slot], "players": len(TOKENS),
            "width": game.width, "height": game.height, "size": game.size, "rounds": game.rounds,
            "keep": game.keep, "theme": game.theme, "colours": COLOUR_NAMES, "rules": RULES,
            "action_timeout_seconds": ACTION_TIMEOUT}


def public_history() -> list[dict[str, Any]]:
    """What players may know about past rounds: points and survivors, not other players' reasons."""
    return [{"round": h["round"], "points": h["points"], "kept": h["kept"]} for h in game.history]


def observation(slot: int) -> dict[str, Any]:
    obs: dict[str, Any] = {
        "type": "observation", "step": state.step, "phase": game.phase, "round": game.round,
        "rounds": game.rounds, "theme": game.theme, "slot": slot, "letter": game.letters[slot],
        "width": game.width, "height": game.height, "size": game.size,
        "canvas": game.canvas_rows(), "owner": game.owner_rows(), "history": public_history(),
        "your_points": game.totals[slot], "action_timeout_seconds": ACTION_TIMEOUT,
    }
    images: dict[str, str] = {}
    if INCLUDE_IMAGES:
        images["canvas"] = png_b64(game.grid)
    if game.phase == "vote":
        obs["rank"] = game.rankable(slot)
        obs["pieces"] = {l: {**{k: v for k, v in game.pieces[f"{game.round}{l}"].to_json().items()
                                if k in ("x", "y", "rows")},
                             "visible_pixels": game.visible(f"{game.round}{l}")} for l in obs["rank"]}
        if INCLUDE_IMAGES:
            for l in obs["rank"]:
                images[f"piece_{l}"] = png_b64(game.piece_alone_grid(l))
        obs["reply"] = {"step": state.step, "ranking": obs["rank"], "why": "one sentence"}
    else:
        obs["reply"] = {"step": state.step, "piece": {"x": 0, "y": 0, "rows": ["...", ".r.", "..."]},
                        "why": "one sentence"}
    if images:
        obs["images_png_base64"] = images
    return obs


def snapshot() -> dict[str, Any]:
    """Spectator view: everything, including reasons, except this round's pieces before they are painted."""
    hidden = game.phase == "draw"
    return {
        "type": "state", "phase": game.phase if not state.done else "done", "round": game.round,
        "rounds": game.rounds, "theme": game.theme, "width": game.width, "height": game.height,
        "size": game.size, "canvas": game.canvas_rows(),
        "owner": [[o for o in row] for row in game.owner],
        "pieces": [p.to_json() for p in game.pieces.values() if not (hidden and p.round == game.round)],
        "history": game.history, "totals": game.totals, "letters": game.letters,
        "player_names": PLAYER_NAMES, "step": state.step,
        "acted": sorted(state.acted), "connected": sorted(state.sockets), "done": state.done,
    }


if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(app, host=GAME_HOST, port=GAME_PORT))
    server.run()
