# Global protocol

Connect a websocket to `/global` to watch. The server sends a `state` snapshot on connect and after
every change; nothing you send is read. A snapshot has `phase`, `round`, `rounds`, `theme`, `width`,
`height`, `size`, `canvas` (rows of colour letters), `owner` (piece id per pixel, e.g. `2B`),
`pieces` (every painted piece with `rows`, `x`, `y`, `why`, `points`, `kept`; this round's pieces
are hidden until all are submitted), `history` (per round: `points`, `kept`, `paint_order`, and
`votes` with each letter's `ranking` and `why`), `totals` (per slot), `letters` (slot -> letter),
`player_names`, `step`, `acted`, `connected`, `done`. `GET /healthz` returns `{"ok": true}`.
The replay file holds the same snapshots as `frames`, one per phase change.
