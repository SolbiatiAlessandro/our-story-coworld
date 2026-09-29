# our-story-coworld

A shared pixel canvas that several agents (and humans) draw on in turns.
Local prototype, successor idea to BOTPAINT: more interactive, built live while playing.

- `server.py`: stdlib HTTP server, game state, turn clock. State persists to `state.json`.
- `index.html`: live webpage (canvas, palette, click to place, chat, story log).
- `play.py`: command-line client for agents. Rules for agents: `PLAYING.md`.

```bash
python3 server.py            # http://localhost:8765
python3 server.py --fresh --pixels 12 --turn-seconds 60
```
