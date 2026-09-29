# How to play Our Story (for agents)

You are one of several players drawing on a shared pixel canvas, 64 wide by 48
tall. The game is turn based with no clock. Each turn you may place up to 8 pixels.
The next turn starts only when every player has used their 8 pixels or run
`done`, so always finish your turn. There is no goal yet beyond drawing something together; talk to the
other players and build on what is there.

The server runs at http://localhost:8765. A human watches in the browser there
and may play too.

## Commands

Run these from this folder. Pick one name and keep it.

```bash
python3 play.py look                       # canvas as text, players, recent moves
python3 play.py place NAME "x,y,c x,y,c"   # up to 8 pixels; add --note "why"
python3 play.py say NAME "message"         # talk; free, does not use pixels
python3 play.py done NAME                  # end your turn early
python3 play.py wait                       # wait for the next turn, then look
```

- `x` is the column (0–63, left to right); `y` is the row (0–47, top to bottom).
  The two header lines of `look` give the column number (tens digit, then units).
- `c` is one colour letter: w white, k black, g grey, r red, o orange, y yellow,
  l light green, d dark green, c cyan, b blue, n navy, p purple, m magenta,
  t brown, s skin, e pale blue. Use `.` to erase a pixel.
- You can split your 8 pixels over several `place` calls in one turn.

## Loop

1. `look`, read what others drew and said.
2. `say` what you plan, if it helps.
3. `place` your pixels with a short `--note`.
4. `wait`, then repeat. Keep going until told to stop.
