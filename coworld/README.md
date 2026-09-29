# our-story coworld

The Our Story game packaged as a Softmax coworld (`game.name: our-story`). Rules: `ourstory/docs/README.md`.

- `ourstory/engine.py` — rules, no transport. `ourstory/render.py` — PNG images (stdlib).
- `ourstory/game/server.py` — FastAPI websocket game server (Coworld runtime contract).
- `ourstory/player/baseline.py` — deterministic no-LLM baseline used for certification.
- `ourstory/game/client/viewer.html` — replay viewer and live spectator page.
- `tools/make_manifest.py` — writes `coworld_manifest_template.json` from `ourstory/docs/`.

```bash
python3 tools/make_manifest.py
./tools/coworld.sh build --project . --version 0.1.0
./tools/coworld.sh certify dist/coworld_manifest.json --no-open-report   # 10/10 on 2026-09-28
./tools/coworld.sh run-episode dist/coworld_manifest.json --variant quick-4
```

`coworld build` needs a git `origin`; until a GitHub repo exists, `origin` points at the local
checkout. Uploading (`coworld upload-coworld`) needs a Softmax login and has not been done.
