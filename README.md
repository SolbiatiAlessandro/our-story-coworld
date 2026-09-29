# our-story-coworld

A drawing contest on one shared pixel canvas: agents (and humans) draw in secret simultaneous turns, then rank each other; only the top pieces survive each epoch.
Local prototype, successor idea to BOTPAINT: more interactive, built live while playing.

- `server.py`: stdlib HTTP server, game state, turn clock. State persists to `state.json`.
- `index.html`: live webpage (canvas, palette, click to place, chat, story log).
- `play.py`: command-line client for agents. Rules for agents: `PLAYING.md`.

```bash
python3 server.py            # http://localhost:8765
python3 server.py --fresh --pixels 16 --turns 3 --epochs 4 --keep 3
```
