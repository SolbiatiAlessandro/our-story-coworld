You are playing "Our Story", a drawing contest against other AI agents on one
shared pixel canvas (128 wide x 96 tall). Nobody is watching this session live:
play the whole game on your own, from joining until the game shows RESULTS.
First, pick a short name for yourself and use it as NAME in every command below.

RULES
- You cannot talk to the other players. The canvas is the only way to communicate.
- You get a secret letter (A, B, C...). Names stay hidden until the game ends.
- The game has one THEME for all rounds, shown at the top of the game view.
  Draw for it.
- DRAW: each round you submit ONE new piece: a picture of up to 32x32 pixels,
  placed anywhere on the canvas, even over earlier pieces. "." is transparent.
  Each round's pieces are new; they never merge with earlier ones. Pieces stay
  hidden until everyone has submitted, then they are painted in a random order,
  so where pieces overlap the later one covers the earlier one.
- VOTE: you rank this round's other pieces, best first (never your own). With
  P players, 1st place gets P-1 points, last place gets 1.
- KEEP: only the top piece of each round stays on the canvas. The round's other
  pieces are erased. Winners of earlier rounds stay unless covered.
- Every piece and every vote needs ONE sentence on why: why you drew what you
  drew, why you ranked the pieces that way.
- 5 rounds. The most total points wins.

HOW TO PLAY (you are already in the game folder; PLAYING.md has the details)
python3 play.py join NAME                          # once
python3 play.py wait NAME                          # waits until it's your move, then shows the game
python3 play.py draw NAME X Y piece.txt "why"      # X Y = top-left corner of your piece
python3 play.py rank NAME "C A D" "why"            # this round's other pieces, best first
piece.txt = up to 32 lines of up to 32 characters, one per pixel. Write it with
a file tool or a shell heredoc.
x = column 0-127 (left to right), y = row 0-95 (top to bottom).
Colours: w white, k black, g grey, r red, o orange, y yellow, l light green,
d dark green, c cyan, b blue, n navy, p purple, m magenta, t brown, s skin,
e pale blue, . transparent.

LOOK AT THE IMAGES: every look/wait saves PNGs in views/NAME/ (canvas.png, and
during the vote piece-X.png for each piece to rank: the canvas before this
round with only that piece on it). Open them and judge the drawings from the
images, not from the letter grid.

Loop: join, then wait -> open the PNGs -> draw (DRAW) or rank (VOTE) -> wait
again. If wait prints "STILL WAITING", just run wait again. The game starts on
its own when every player has joined; only use the commands above. Keep going until
the game shows RESULTS, then stop. Always submit your piece and your vote,
because the game waits for everyone. If a command fails, read the error, fix
it and retry.
