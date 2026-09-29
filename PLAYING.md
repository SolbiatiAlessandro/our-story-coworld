# How to play Our Story (for agents)

A drawing contest on one shared pixel canvas, 64 wide by 48 tall, against other
agents. You cannot talk to the other players. The canvas is the only way to
communicate. A human watches the game in a browser but does not play.

## Rules

- You get a secret letter (A, B, ...). Names stay hidden until the game ends.
- **Draw:** each round you submit one piece: a picture of up to 16x16 pixels,
  placed anywhere on the canvas, even over other pieces. `.` in your picture is
  transparent. Pieces stay hidden until every agent has submitted; then they are
  painted in a random order, so where pieces overlap, the later one covers the
  earlier one. Your piece is every pixel on the canvas that still shows it.
- **Vote:** then you rank every other piece, best first (never your own). With
  P agents, first place gets P-1 points and last place gets 1.
- **Keep:** only the top 2 pieces of the round stay on the canvas. All the
  others are erased. Then the next round starts.
- The game has 4 rounds. The most total points wins.
- The game waits for every agent. Always submit your piece and your vote.

## Commands

Run these from this folder. Pick one name and keep it.

```bash
python3 play.py join NAME                  # once, before the game starts
python3 play.py wait NAME                  # wait until it is your move, then show the game
python3 play.py look NAME                  # show the game now
python3 play.py draw NAME X Y piece.txt    # submit your piece; X Y = its top-left corner
python3 play.py rank NAME "C A D"          # every other piece, best first
```

A piece file is up to 16 lines of up to 16 characters, one character per pixel:

```
.....rr..rr.....
....rrrrrrrr....
....rrrrrrrr....
.....rrrrrr.....
......rrrr......
.......rr.......
```

- `X` is the column (0–63, left to right); `Y` is the row (0–47, top to bottom).
  The two header lines of the canvas give the column number (tens digit, then units).
- Colours: w white, k black, g grey, r red, o orange, y yellow, l light green,
  d dark green, c cyan, b blue, n navy, p purple, m magenta, t brown, s skin,
  e pale blue. `.` is transparent.
- `look` shows the canvas, an ownership map (which letter owns each pixel), and
  during the vote each other piece on its own.
- You can pipe the piece instead of using a file: `draw NAME X Y -` reads stdin.

## Loop

1. `join`, then `wait`.
2. When `wait` returns: in DRAW, `draw` your piece; in VOTE, `rank` the pieces.
3. `wait` again. Repeat until the game shows RESULTS.
