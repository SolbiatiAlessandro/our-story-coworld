"""LLM player for Our Story, calling a model through the Softmax hosted LLM sidecar.

Hosted: upload the policy with `--use-bedrock --bedrock-model <OpenRouter slug>` (for example
anthropic/claude-haiku-4.5 or openai/gpt-6-astra). The platform sets AWS_ENDPOINT_URL_BEDROCK_RUNTIME
(the sidecar's base URL; the name is historical) and BEDROCK_MODEL. We call its OpenAI-compatible
POST /v1/chat/completions over plain HTTP, so any model family works and no SDK is needed.
Each step is one model call: the rules, the theme, the canvas as text and as a PNG (plus, in the
vote, each piece alone on the canvas before the round) go in; one JSON action comes out. If the
server rejects the action, the error goes back to the model for up to two more tries; after that
the player falls back to the baseline action so the game never waits on it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import urllib.error
import urllib.request

import websockets

from ourstory.player import baseline

MODEL = os.environ.get("BEDROCK_MODEL", "anthropic/claude-haiku-4.5")
ENDPOINT = os.environ.get("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", "").rstrip("/")
MAX_TRIES = 3


def log(*args: Any) -> None:
    print("[llm_player]", *args, file=sys.stderr, flush=True)


class BadReply(ValueError):
    """The model answered, but not with usable JSON; tell it and ask again."""


def image(b64: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


class Brain:
    def __init__(self) -> None:
        self.welcome: dict[str, Any] = {}
        self.my_pieces: list[str] = []   # short memory of what this player drew

    def system(self) -> str:
        w = self.welcome
        colours = ", ".join(f"{k}={v}" for k, v in w.get("colours", {}).items())
        return (
            f"{w.get('rules', '')}\n\nYou are player {w.get('letter')} of {w.get('players')}. "
            f"Canvas: {w.get('width')} wide x {w.get('height')} tall; x is the column (0 left), y the row "
            f"(0 top). A piece is at most {w.get('size')} rows of at most {w.get('size')} characters. "
            f"Colours: {colours}; '.' is transparent (never use spaces). Each row is a JSON string. Your goal is the most points: make pieces the other "
            f"players will rank highly for the theme, and rank others honestly or strategically as you see fit. "
            f"Answer with ONE JSON object only, no other text."
        )

    def call(self, content: list[dict[str, Any]]) -> str:
        if not ENDPOINT:
            raise RuntimeError("AWS_ENDPOINT_URL_BEDROCK_RUNTIME is not set: upload the policy with --use-bedrock")
        body = {"model": MODEL, "max_tokens": 6000, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": self.system()}, {"role": "user", "content": content}]}
        req = urllib.request.Request(f"{ENDPOINT}/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Authorization": "Bearer sidecar"})
        try:
            with urllib.request.urlopen(req, timeout=170) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:   # log the body: it names route, model or spend failures
            raise RuntimeError(f"HTTP {e.code} from {ENDPOINT}: {e.read()[:500]!r}") from None
        return data["choices"][0]["message"]["content"] or ""

    def content(self, obs: dict[str, Any], error: str | None) -> list[dict[str, Any]]:
        images = obs.get("images_png_base64", {})
        parts: list[dict[str, Any]] = []
        hist = "; ".join(f"round {h['round']}: points {h['points']}, stayed {h['kept']}" for h in obs["history"])
        parts.append({"type": "text", "text": (
            f"Theme: {obs['theme']}. Round {obs['round']} of {obs['rounds']}. Phase: {obs['phase']}. "
            f"You are {obs['letter']} with {obs['your_points']} points. Past rounds: {hist or 'none'}. "
            f"Your earlier pieces: {'; '.join(self.my_pieces) or 'none'}.\n"
            "Canvas (one line per row, '.' empty):\n" + "\n".join(obs["canvas"]) +
            "\nOwnership (this round's letters, # = winners of earlier rounds):\n" + "\n".join(obs["owner"]))})
        if "canvas" in images:
            parts.append({"type": "text", "text": "The canvas now:"})
            parts.append(image(images["canvas"]))
        if obs["phase"] == "draw":
            parts.append({"type": "text", "text": (
                "Draw one new piece for this round. Reply exactly like "
                '{"piece": {"x": 40, "y": 10, "rows": ["..kk..", ".kyyk."]}, "why": "one sentence on why you drew this"}')})
        else:
            for l in obs["rank"]:
                if f"piece_{l}" in images:
                    parts.append({"type": "text", "text": f"Piece {l}, alone on the canvas as it was before this round:"})
                    parts.append(image(images[f"piece_{l}"]))
            parts.append({"type": "text", "text": (
                f"Rank these pieces best first: {', '.join(obs['rank'])}. Reply exactly like "
                f'{{"ranking": {json.dumps(obs["rank"])}, "why": "one sentence on why you ranked them so"}}')})
        if error:
            parts.append({"type": "text", "text": f"Your previous answer was rejected: {error}. Fix it and answer again."})
        return parts

    def act(self, obs: dict[str, Any], error: str | None = None) -> dict[str, Any]:
        text = self.call(self.content(obs, error))
        start = text.find("{")
        if start < 0:
            raise BadReply(f"your reply had no JSON object: {text[:200]!r}")
        try:
            reply, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as e:
            raise BadReply(f"your reply was not valid JSON ({e})") from None
        if not isinstance(reply, dict):
            raise BadReply("your reply must be one JSON object")
        reply["step"] = obs["step"]
        return reply


async def main() -> None:
    brain = Brain()
    url = os.environ["COWORLD_PLAYER_WS_URL"]
    log("model", MODEL, "endpoint", ENDPOINT or "(not set)")
    async with websockets.connect(url, ping_timeout=None, max_size=None) as ws:
        obs: dict[str, Any] | None = None
        tries, error, pending_why = 0, None, ""
        async for raw in ws:
            msg = json.loads(raw)
            kind = msg["type"]
            if kind == "final":
                return
            if kind == "welcome":
                brain.welcome = msg
                continue
            if kind == "observation" and msg.get("phase") in ("draw", "vote"):
                obs, tries, error = msg, 0, None
            elif kind == "error" and obs is not None and msg.get("step") == obs["step"]:
                error = msg["message"]
                log("rejected:", error)
            elif kind == "accepted" and obs is not None and obs["phase"] == "draw" and pending_why:
                brain.my_pieces.append(f"round {obs['round']}: {pending_why}")
                continue
            else:
                continue
            tries += 1
            if tries > MAX_TRIES:
                reply = fallback(obs)
                log("falling back to the baseline action")
            else:
                try:
                    reply = await asyncio.to_thread(brain.act, obs, error)
                except BadReply as e:    # counts as a try; the model sees what was wrong
                    log("bad reply:", str(e)[:300])
                    error = str(e)
                    while tries < MAX_TRIES:
                        tries += 1
                        try:
                            reply = await asyncio.to_thread(brain.act, obs, error)
                            break
                        except BadReply as e2:
                            log("bad reply:", str(e2)[:300])
                            error = str(e2)
                    else:
                        reply = fallback(obs)
                except Exception as e:   # model or transport failure: log the body, then fall back
                    log("model call failed:", repr(e)[:500])
                    reply = fallback(obs)
            pending_why = reply.get("why", "") if obs["phase"] == "draw" else ""
            await ws.send(json.dumps(reply))


def fallback(obs: dict[str, Any]) -> dict[str, Any]:
    if obs["phase"] == "draw":
        return {"step": obs["step"], "piece": baseline.piece(obs["slot"], obs["round"], obs["width"], obs["height"]),
                "why": "A small robot head (fallback: the model call failed)."}
    return {"step": obs["step"], "ranking": baseline.ranking(obs),
            "why": "Ranked by visible pixels (fallback: the model call failed)."}


if __name__ == "__main__":
    asyncio.run(main())
