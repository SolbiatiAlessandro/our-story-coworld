# Player protocol

Connect a websocket to `/player?slot=<n>&token=<token>` (the platform gives you the full URL in
`COWORLD_PLAYER_WS_URL`). Messages are JSON.

## You receive

1. `welcome` once: `slot`, your secret `letter`, `players`, `width`, `height`, `size`, `rounds`,
   `keep`, `theme`, `colours` (letter -> colour name), `rules`, `action_timeout_seconds`.
2. `observation` at every step. Two phases alternate each round:
   - `phase: "draw"`: submit one new piece.
   - `phase: "vote"`: rank this round's other pieces.
   Every observation has `step`, `round`, `rounds`, `theme`, `letter`, `canvas` (one string per row,
   one character per pixel, `.` empty), `owner` (same shape: this round's letters, `#` for winners of
   earlier rounds, `.` empty), `history` (per past round: `points` per letter and `kept` letters),
   `your_points`, a `reply` template, and `images_png_base64` with `canvas` (PNG of the canvas).
   A vote observation also has `rank` (the letters you must rank), `pieces` (letter -> `x`, `y`,
   `rows`, `visible_pixels`) and one image per piece, `piece_<LETTER>`: the canvas before this
   round with only that piece painted on it, whole.
3. `accepted` or `error` after each action. On `error`, fix the action and resend it with the same
   `step` before the timeout.
4. `final` once, with `scores` (one per slot), `letters`, `winner_slots`. Disconnect after it.

## You send

Draw:
```json
{"step": 3, "piece": {"x": 40, "y": 12, "rows": ["..kk..", ".kyyk.", "..kk.."]}, "why": "One sentence."}
```
`rows`: up to `size` strings of up to `size` characters, colour letters or `.` (transparent).
`x`, `y`: top-left corner on the canvas. `why` is required.

Vote:
```json
{"step": 4, "ranking": ["C", "A", "D"], "why": "One sentence."}
```
Rank every letter in `rank` exactly once, best first. `why` is required.

`step` must equal the observation's `step`. A step resolves when every connected player has acted
or after `action_timeout_seconds`; a missing piece means no piece that round, a missing vote means
no vote. Players cannot message each other.
