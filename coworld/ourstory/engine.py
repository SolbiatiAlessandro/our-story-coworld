"""Our Story rules, independent of any transport.

Seats are slots 0..P-1. Each slot gets an anonymous letter (A, B, ...), assigned by a
seeded shuffle so a letter does not reveal seat order. Every round:

  draw  each slot submits one new piece: up to size x size characters placed at (x, y),
        '.' transparent, plus one sentence on why. Pieces are painted in a seeded random
        order; where they overlap, the later one covers the earlier one.
  vote  each slot ranks this round's other pieces, best first, plus one sentence on why.
        Borda points: with P pieces, first place gets P-1, last gets 1.
  keep  the top `keep` pieces of the round stay; this round's other pieces are erased.
        Winners of earlier rounds stay unless covered.

A slot that submits nothing simply has no piece that round (or casts no vote).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

LETTERS = "ABCDEFGHIJKLMNOP"
EMPTY = "."
PALETTE = {
    "w": "#ffffff", "k": "#1a1a1a", "g": "#8a8a8a", "r": "#e23b3b",
    "o": "#f28c28", "y": "#f5d33b", "l": "#7ed957", "d": "#2e8b3d",
    "c": "#4fd1e0", "b": "#2f6fdf", "n": "#1f2f7a", "p": "#9b5de5",
    "m": "#f15bb5", "t": "#8b5a2b", "s": "#f2c9a0", "e": "#c9e7ff",
}
COLOUR_NAMES = dict(zip(PALETTE, "white black grey red orange yellow light-green dark-green "
                                 "cyan blue navy purple magenta brown skin pale-blue".split()))


class InvalidAction(ValueError):
    """An action the player can fix and resend."""


@dataclass
class Piece:
    round: int
    letter: str
    x: int
    y: int
    rows: list[str]
    why: str
    points: int | None = None
    kept: bool | None = None

    @property
    def id(self) -> str:
        return f"{self.round}{self.letter}"

    def to_json(self) -> dict:
        return {"id": self.id, "round": self.round, "letter": self.letter, "x": self.x, "y": self.y,
                "rows": self.rows, "why": self.why, "points": self.points, "kept": self.kept}


@dataclass
class Game:
    players: int
    width: int = 128
    height: int = 96
    size: int = 32
    rounds: int = 5
    keep: int = 1
    theme: str = "AI age"
    seed: int = 0
    round: int = 0
    phase: str = "lobby"   # lobby, draw, vote, done
    grid: list[list[str]] = field(default_factory=list)
    owner: list[list[str]] = field(default_factory=list)   # piece id per pixel, "" if none
    pieces: dict[str, Piece] = field(default_factory=dict)
    votes: dict[int, tuple[list[str], str]] = field(default_factory=dict)   # this round only
    history: list[dict] = field(default_factory=list)
    totals: list[int] = field(default_factory=list)
    paint_order: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        order = list(LETTERS[: self.players])
        self.rng.shuffle(order)
        self.letters = order                      # slot -> letter
        self.slot_of = {l: s for s, l in enumerate(order)}
        self.grid = [[EMPTY] * self.width for _ in range(self.height)]
        self.owner = [[""] * self.width for _ in range(self.height)]
        self.totals = [0] * self.players

    # ---- phases -------------------------------------------------------------

    def start(self) -> None:
        self.round, self.phase = 1, "draw"

    def piece_of(self, slot: int, rnd: int | None = None) -> Piece | None:
        return self.pieces.get(f"{rnd or self.round}{self.letters[slot]}")

    def submit_piece(self, slot: int, x, y, rows, why) -> None:
        if self.phase != "draw":
            raise InvalidAction(f"cannot draw during the {self.phase} phase")
        if self.piece_of(slot):
            raise InvalidAction("you already submitted your piece this round")
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            raise InvalidAction("x and y must be integers") from None
        if isinstance(rows, str):
            rows = rows.split("\n")
        if not isinstance(rows, list) or not all(isinstance(r, str) for r in rows):
            raise InvalidAction("rows must be a list of strings")
        rows = [r.rstrip() for r in rows]
        while rows and not rows[-1]:
            rows.pop()
        n = self.size
        if not rows or len(rows) > n or any(len(r) > n for r in rows):
            raise InvalidAction(f"a piece is at most {n} rows of at most {n} characters")
        bad = {c for r in rows for c in r if c not in PALETTE and c != EMPTY}
        if bad:
            raise InvalidAction(f"unknown colours {sorted(bad)}; use {''.join(PALETTE)} or '.' for transparent")
        if not any(c != EMPTY for r in rows for c in r):
            raise InvalidAction("your piece is empty")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise InvalidAction(f"top-left corner must be on the canvas: x 0-{self.width - 1}, y 0-{self.height - 1}")
        why = _sentence(why, "you drew this")
        p = Piece(self.round, self.letters[slot], x, y, rows, why)
        self.pieces[p.id] = p

    def round_pieces(self) -> list[Piece]:
        return [p for p in self.pieces.values() if p.round == self.round]

    def paint(self) -> None:
        """Paint this round's pieces in a seeded random order and open the vote."""
        mine = sorted(self.round_pieces(), key=lambda p: p.letter)
        self.rng.shuffle(mine)
        self.paint_order = [p.letter for p in mine]
        self.base_grid = [row[:] for row in self.grid]   # the canvas before this round
        for p in mine:
            for dy, row in enumerate(p.rows):
                for dx, c in enumerate(row):
                    x, y = p.x + dx, p.y + dy
                    if c != EMPTY and 0 <= x < self.width and 0 <= y < self.height:
                        self.grid[y][x] = c
                        self.owner[y][x] = p.id
        self.votes = {}
        self.phase = "vote"

    def rankable(self, slot: int) -> list[str]:
        return sorted(p.letter for p in self.round_pieces() if p.letter != self.letters[slot])

    def submit_vote(self, slot: int, ranking, why) -> None:
        if self.phase != "vote":
            raise InvalidAction(f"cannot vote during the {self.phase} phase")
        if slot in self.votes:
            raise InvalidAction("you already voted this round")
        if isinstance(ranking, str):
            ranking = ranking.replace(",", " ").split()
        if not isinstance(ranking, list):
            raise InvalidAction("ranking must be a list of letters")
        ranking = [str(r).strip().upper() for r in ranking]
        expected = self.rankable(slot)
        if sorted(ranking) != expected:
            raise InvalidAction(f"rank each of {' '.join(expected)} exactly once, best first "
                                f"(your own piece {self.letters[slot]} is excluded)")
        self.votes[slot] = (ranking, _sentence(why, "you voted this way"))

    def end_round(self) -> None:
        pieces = self.round_pieces()
        points = {p.letter: 0 for p in pieces}
        for ranking, _ in self.votes.values():
            for i, l in enumerate(ranking):
                points[l] += len(pieces) - 1 - i
        best = sorted(points, key=lambda l: (-points[l], l))
        kept: list[str] = []
        if best:
            cutoff = points[best[min(self.keep, len(best)) - 1]]
            kept = [l for l in best if points[l] >= cutoff]   # ties at the cutoff all stay
        for p in pieces:
            p.points, p.kept = points[p.letter], p.letter in kept
            self.totals[self.slot_of[p.letter]] += points[p.letter]
        losers = {p.id for p in pieces if not p.kept}
        for y in range(self.height):
            for x in range(self.width):
                if self.owner[y][x] in losers:
                    self.grid[y][x], self.owner[y][x] = EMPTY, ""
        self.history.append({
            "round": self.round, "points": points, "kept": kept, "paint_order": self.paint_order,
            "votes": {self.letters[s]: {"ranking": r, "why": w} for s, (r, w) in sorted(self.votes.items())},
        })
        if self.round >= self.rounds:
            self.phase = "done"
        else:
            self.round += 1
            self.phase = "draw"

    # ---- views --------------------------------------------------------------

    def canvas_rows(self, grid=None) -> list[str]:
        return ["".join(r) for r in (grid or self.grid)]

    def owner_rows(self) -> list[str]:
        """One character per pixel: this round's letter, '#' for earlier winners, '.' empty."""
        cur = str(self.round)
        return ["".join(o[-1] if o and o[:-1] == cur else ("#" if o else EMPTY) for o in row)
                for row in self.owner]

    def visible(self, piece_id: str) -> int:
        return sum(row.count(piece_id) for row in self.owner)

    def piece_alone_grid(self, letter: str) -> list[list[str]]:
        """The canvas before this round with only this piece painted on it, whole."""
        p = self.pieces[f"{self.round}{letter}"]
        grid = [row[:] for row in getattr(self, "base_grid", self.grid)]
        for dy, row in enumerate(p.rows):
            for dx, c in enumerate(row):
                x, y = p.x + dx, p.y + dy
                if c != EMPTY and 0 <= x < self.width and 0 <= y < self.height:
                    grid[y][x] = c
        return grid

    def results(self, player_names: list[str]) -> dict:
        top = max(self.totals) if self.totals else 0
        return {
            "scores": [float(t) for t in self.totals],
            "letters": self.letters,
            "winner_slots": [s for s, t in enumerate(self.totals) if t == top],
            "rounds_won": [sum(self.letters[s] in h["kept"] for h in self.history) for s in range(self.players)],
            "theme": self.theme,
            "rounds": len(self.history),
            "player_names": player_names,
        }


def _sentence(text, what: str) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        raise InvalidAction(f"add one sentence on why {what}")
    return text[:300]
