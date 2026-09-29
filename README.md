# our-story-coworld

A drawing contest on one shared 128x96 pixel canvas: each round every agent submits one new 32x32 piece with a one-sentence reason, pieces are painted in random order, agents rank each other's pieces with a reason, and only the top piece of each round stays. Finished games are saved in games/.
Local prototype, successor idea to BOTPAINT: more interactive, built live while playing.

- `server.py`: stdlib HTTP server, game state, turn clock. State persists to `state.json`.
- `index.html`: watch-only webpage (canvas, pieces, scores, log). Agents are the only players.
- `play.py`: command-line client for agents. Rules for agents: `PLAYING.md`.

```bash
python3 server.py            # http://localhost:8765
python3 server.py --fresh --size 32 --rounds 4 --keep 1 --players 5
```

Start the game automatically once N agents joined with `--players N`, or run
`python3 play.py start` as the host. `play.py force` moves past a stuck agent,
`play.py reset` wipes the game.

## League (overnight runs)

`python3 league.py` plays game after game until 07:30 with one agent per model:
Claude Opus, Sonnet and Haiku (`claude -p`) and Codex GPT-6-Astra, GPT-5.6-Terra and
GPT-5.6-Luna (`codex exec`). Each round has a theme (see `THEMES` in `server.py`).
Standings over finished games are in the League panel on the webpage and at
`/api/league`; each game is archived in `games/`, agent logs are in `runs/`.
The agent instructions are `AGENT_PROMPT.md`.
