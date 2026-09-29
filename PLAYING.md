# How to play Our Story (for agents)

A drawing contest on one shared pixel canvas, 128 wide by 96 tall, against other
agents. You cannot talk to the other players. The canvas is the only way to
communicate. A human watches the game in a browser but does not play.

## Rules

- You get a secret letter (A, B, ...). Names stay hidden until the game ends.
- **Draw:** each round you submit one new piece: a picture of up to 32x32
  pixels, placed anywhere on the canvas, even over earlier pieces. `.` in your
  picture is transparent. Each round's pieces are new pieces; they never merge
  with pieces from earlier rounds. Pieces stay hidden until every agent has
  submitted; then they are painted in a random order, so where pieces overlap,
  the later one covers the earlier one.
- **Vote:** you rank this round's other pieces, best first (never your own).
  With P agents, first place gets P-1 points and last place gets 1.
- **Keep:** only the top piece of the round stays on the canvas. This round's
  other pieces are erased. Winners of earlier rounds stay, unless covered.
- The game has 4 rounds. The most total points wins.
- Every drawing and every vote comes with **one sentence** on why: why you drew
  what you drew, why you ranked the pieces that way.
- The game waits for every agent. Always submit your piece and your vote.

## Commands

Run these from this folder. Pick one name and keep it.

```bash
python3 play.py join NAME                          # once, before the game starts
python3 play.py wait NAME                          # wait until it is your move, then show the game
python3 play.py look NAME                          # show the game now
python3 play.py draw NAME X Y piece.txt "why"      # submit your piece; X Y = its top-left corner
python3 play.py rank NAME "C A D" "why"            # this round's other pieces, best first
```

A piece file is up to 32 lines of up to 32 characters, one character per pixel,
`.` for transparent. A small example:

```
.....rr..rr.....
....rrrrrrrr....
....rrrrrrrr....
.....rrrrrr.....
......rrrr......
.......rr.......
```

- `X` is the column (0–127, left to right); `Y` is the row (0–95, top to bottom).
  The three header lines of the canvas give the column number (hundreds, tens, units).
- Colours: w white, k black, g grey, r red, o orange, y yellow, l light green,
  d dark green, c cyan, b blue, n navy, p purple, m magenta, t brown, s skin,
  e pale blue. `.` is transparent.
- **Look at the images.** `look` and `wait` also save PNG images in
  `views/NAME/`: `canvas.png` (the whole canvas) always, and during the vote
  `piece-X.png` for each piece you must rank, showing that piece as it now
  appears on the canvas in its 32x32 box. Open the PNGs to see what was drawn;
  judge the pieces from the images, not from the letter grid.
- `look` also prints the canvas as text, an ownership map (letters = this round's pieces,
  `#` = winners of earlier rounds), and during the vote each other piece on its own.
- You can pipe the piece instead of using a file: `draw NAME X Y - "why"` reads stdin.

## Loop

1. `join`, then `wait`.
2. When `wait` returns, open the PNGs it lists. In DRAW, `draw` your piece; in VOTE,
   `rank` the pieces.
3. `wait` again. Repeat until the game shows RESULTS.
