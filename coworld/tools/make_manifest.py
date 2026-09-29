"""Write coworld_manifest_template.json from the docs in ourstory/docs (single source for the text)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "ourstory" / "docs"
MAX_SEATS = 12


def text(name: str) -> dict:
    return {"type": "text", "value": (DOCS / name).read_text()}


def names(n: int) -> list[dict]:
    return [{"name": f"Player {i + 1}"} for i in range(n)]


game_config_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["tokens", "players"],
    "properties": {
        "tokens": {"type": "array", "minItems": 2, "maxItems": MAX_SEATS,
                   "items": {"type": "string", "minLength": 1}},
        "players": {"type": "array", "minItems": 2, "maxItems": MAX_SEATS,
                    "items": {"type": "object", "additionalProperties": False, "required": ["name"],
                              "properties": {"name": {"type": "string", "minLength": 1}}}},
        "theme": {"type": "string", "minLength": 1, "maxLength": 80, "default": "AI age"},
        "rounds": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        "keep": {"type": "integer", "minimum": 1, "maximum": 11, "default": 1},
        "width": {"type": "integer", "minimum": 16, "maximum": 256, "default": 128},
        "height": {"type": "integer", "minimum": 16, "maximum": 256, "default": 96},
        "size": {"type": "integer", "minimum": 4, "maximum": 64, "default": 32},
        "seed": {"type": "integer", "default": 0},
        "include_images": {"type": "boolean", "default": True},
        "action_timeout_seconds": {"type": "number", "minimum": 1, "default": 180},
        "player_connect_timeout_seconds": {"type": "number", "minimum": 0, "default": 180},
    },
}

results_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["scores", "letters", "winner_slots", "rounds_won", "theme", "rounds", "player_names"],
    "properties": {
        "scores": {"type": "array", "minItems": 2, "maxItems": MAX_SEATS, "items": {"type": "number"}},
        "letters": {"type": "array", "items": {"type": "string"}},
        "winner_slots": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        "rounds_won": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        "theme": {"type": "string"},
        "rounds": {"type": "integer", "minimum": 0},
        "player_names": {"type": "array", "items": {"type": "string"}},
    },
}

manifest = {
    "$schema": "https://raw.githubusercontent.com/Metta-AI/coworld/main/src/coworld/coworld_manifest_schema.json",
    "tags": ["creative", "turn-based", "pixel-art", "multi-agent", "social"],
    "game": {
        "name": "our-story",
        "description": ("Our Story: agents that cannot talk take turns adding pixel-art pieces to one shared "
                        "canvas around a theme, rank each other's pieces with a one-sentence reason, and only "
                        "each round's winner stays, so the canvas becomes the story they chose together."),
        "owner": "Alessandro",
        "replay_viewer": {"bundle": "build/static-replay-viewer"},
        "runnable": {"type": "game", "image": "{{OUR_STORY_IMAGE}}",
                     "run": ["python", "-m", "ourstory.game.server"]},
        "config_schema": game_config_schema,
        "results_schema": results_schema,
        "protocols": {"player": text("PLAYER_PROTOCOL.md"), "global": text("GLOBAL_PROTOCOL.md")},
        "docs": {"readme": text("README.md")},
    },
    "player": [{
        "id": "robot-baseline",
        "name": "Robot Baseline",
        "type": "player",
        "image": "{{OUR_STORY_IMAGE}}",
        "run": ["python", "-m", "ourstory.player.baseline"],
        "description": ("Deterministic no-LLM baseline: draws a small robot head in its own spot each round "
                        "and ranks pieces by how many of their pixels are visible."),
    }],
    "variants": [
        {"id": "default", "name": "AI age, 6 players",
         "description": "Theme AI age, 128x96 canvas, 32x32 pieces, 5 rounds, top piece stays.",
         "game_config": {"theme": "AI age", "rounds": 5, "keep": 1, "width": 128, "height": 96, "size": 32,
                         "action_timeout_seconds": 180, "player_connect_timeout_seconds": 180,
                         "players": names(6)}},
        {"id": "quick-4", "name": "AI age, 4 players, 3 rounds",
         "description": "A shorter game for 4 players.",
         "game_config": {"theme": "AI age", "rounds": 3, "keep": 1, "width": 128, "height": 96, "size": 32,
                         "action_timeout_seconds": 180, "player_connect_timeout_seconds": 180,
                         "players": names(4)}},
    ],
    "certification": {
        "game_config": {"theme": "AI age", "rounds": 2, "keep": 1, "width": 128, "height": 96, "size": 32,
                        "seed": 1, "action_timeout_seconds": 30, "player_connect_timeout_seconds": 120,
                        "players": names(3)},
        "players": [{"player_id": "robot-baseline"}] * 3,
    },
}

(ROOT / "coworld_manifest_template.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("wrote coworld_manifest_template.json")
