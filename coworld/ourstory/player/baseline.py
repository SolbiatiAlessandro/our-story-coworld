"""Deterministic no-LLM baseline for Our Story.

Draws a small robot head (the default theme is "AI age") in its own spot, a new colour each
round, and ranks other pieces by how many of their pixels are visible, then by letter.
Establishes what always-legal, zero-effort play scores.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import websockets

ROBOT = [
    "....kk....",
    "....kk....",
    ".kkkkkkkk.",
    ".k{c}{c}{c}{c}{c}{c}k.",
    ".k{c}w{c}{c}w{c}k.",
    ".k{c}{c}{c}{c}{c}{c}k.",
    ".k{c}kkkk{c}k.",
    ".kkkkkkkk.",
]
COLOURS = "bgmoc"


def piece(slot: int, rnd: int, width: int, height: int) -> dict[str, Any]:
    colour = COLOURS[(slot + rnd) % len(COLOURS)]
    rows = [r.replace("{c}", colour) for r in ROBOT]
    x = (8 + slot * 14 + rnd * 3) % (width - 12)
    y = (8 + (slot % 4) * 20 + rnd * 2) % (height - 10)
    return {"x": x, "y": y, "rows": rows}


def ranking(obs: dict[str, Any]) -> list[str]:
    pieces = obs["pieces"]
    return sorted(obs["rank"], key=lambda l: (-pieces[l]["visible_pixels"], l))


async def main() -> None:
    url = os.environ["COWORLD_PLAYER_WS_URL"]
    async with websockets.connect(url, ping_timeout=None, max_size=None) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "final":
                return
            if msg["type"] != "observation":
                continue
            if msg["phase"] == "draw":
                reply = {"step": msg["step"], "piece": piece(msg["slot"], msg["round"], msg["width"], msg["height"]),
                         "why": "A small robot head, because the theme is the age of machines."}
            else:
                reply = {"step": msg["step"], "ranking": ranking(msg),
                         "why": "I ranked the pieces by how much of each is still visible on the canvas."}
            await ws.send(json.dumps(reply))


if __name__ == "__main__":
    asyncio.run(main())
