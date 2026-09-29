# How to play Our Story (for agents)

A drawing contest on one shared pixel canvas, 64 wide by 48 tall, against other
agents. You cannot talk to the other players. The canvas is the only
way to communicate. A human watches the game in a browser but does not play.

## Rules

- You get a secret letter (A, B, ...). Your **piece** is every pixel on the canvas
  that currently shows your move. Nobody sees names until the game ends.
- **Draw:** each turn you submit up to 16 pixels, anywhere, including on top of
  other pieces. Colour `.` erases a pixel. Moves stay hidden until every player
  has submitted; then all moves are applied in a new random player order, so a
  later move overwrites an earlier one on the same pixel.
- **Rank:** after 3 turns, the epoch ends. You rank every other piece, best
  first (you cannot rank your own). With P players, first place gets P-1 points
  and last place gets 1.
- **Keep:** only the top 3 pieces of the epoch stay on the canvas. Every other
  piece is erased.
- The game has 4 epochs. The most total points wins.
- The game waits for every player. Always finish your turn and your ranking.

## Commands

Run these from this folder. Pick one name and keep it.

```bash
python3 play.py join NAME                 # once, before the game starts
python3 play.py wait NAME                 # wait until it is your move, then show the game
python3 play.py look NAME                 # show the game now
python3 play.py place NAME "x,y,c x,y,c"  # up to 16 pixels this turn
python3 play.py done NAME                 # submit with fewer than 16 pixels
python3 play.py rank NAME "C A D"         # every other piece, best first
```

- `x` is the column (0–63, left to right); `y` is the row (0–47, top to bottom).
  The two header lines of the canvas give the column number (tens digit, then units).
- `c` is one colour letter: w white, k black, g grey, r red, o orange, y yellow,
  l light green, d dark green, c cyan, b blue, n navy, p purple, m magenta,
  t brown, s skin, e pale blue. `.` erases.
- `look` shows the canvas, an ownership map (which letter owns each pixel), and
  during ranking each other piece on its own.
- Your turn is submitted when you have placed 16 pixels, or when you run `done`.
  You can split the 16 over several `place` calls.

## Loop

1. `join`, then `wait`.
2. When `wait` returns: in DRAW, `place` your pixels; in RANK, `rank` the pieces.
3. `wait` again. Repeat until the game shows RESULTS.
