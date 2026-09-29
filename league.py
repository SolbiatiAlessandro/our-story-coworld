"""Overnight league runner: plays game after game with Claude and Codex agents, one model each.

  python3 league.py                      # until 07:30 local time, at most 12 games
  python3 league.py --until 06:00 --games 3
  python3 league.py --roster claude:claude-haiku-4-5-20251001 codex:gpt-5.6-luna   # smaller test

Each agent is a headless CLI session (`claude -p` or `codex exec`) that joins with a
name it picks, plays the whole game, and exits. The runner tags each player with its
model (hidden from the other agents), starts the game when everyone has joined, moves
past agents that stall, restarts agents that crash, and lets the server archive every
finished game into games/. Standings: the League panel on the webpage, or /api/league.
Logs: runs/<game>/<model>.log and runs/league.log.
"""

import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
URL = os.environ.get("OUR_STORY_URL", "http://localhost:8765")
RUNS = ROOT / "runs"

ROSTER = [
    "claude:claude-opus-5-5",
    "claude:claude-sonnet-5-5",
    "claude:claude-haiku-4-5-20251001",
    "codex:gpt-6-astra",
    "codex:gpt-5.6-terra",
    "codex:gpt-5.6-luna",
]

JOIN_TIMEOUT = 15 * 60      # everyone must join within this
STALL_TIMEOUT = 20 * 60     # no progress for this long: force the phase on
GAME_TIMEOUT = 4 * 3600     # hard cap per game
MAX_RESTARTS = 4            # per agent per game


def api(path, body=None):
    req = urllib.request.Request(URL + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(RUNS / "league.log", "a") as f:
        f.write(line + "\n")


def prompt(resume_name=None):
    text = (ROOT / "AGENT_PROMPT.md").read_text()
    if resume_name:
        text += (f"\n\nIMPORTANT: you already joined this game as {resume_name} and your session was "
                 f"restarted. Do not join again. Use {resume_name} as NAME and continue from "
                 f"`python3 play.py wait {resume_name}`.\n")
    return text


def command(kind, model, text):
    if kind == "claude":
        # stream-json keeps every tool call in the log, not only the final message.
        return ["claude", "-p", text, "--model", model, "--output-format", "stream-json", "--verbose",
                "--allowedTools", "Bash", "Read", "Write", "Edit"]
    return ["codex", "exec", "--skip-git-repo-check", "-m", model, "-s", "workspace-write",
            "-c", "sandbox_workspace_write.network_access=true", "-C", str(ROOT), text]


class Agent:
    def __init__(self, spec, game_dir):
        self.kind, self.model = spec.split(":", 1)
        self.game_dir = game_dir
        self.proc = None
        self.restarts = 0

    def start(self, resume_name=None):
        env = dict(os.environ, OUR_STORY_MODEL=self.model, OUR_STORY_URL=URL)
        out = open(self.game_dir / f"{self.model}.log", "a")
        out.write(f"\n===== {datetime.now():%H:%M:%S} start{' (resume as ' + resume_name + ')' if resume_name else ''}\n")
        out.flush()
        self.proc = subprocess.Popen(command(self.kind, self.model, prompt(resume_name)), cwd=ROOT, env=env,
                                     stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)

    def alive(self):
        return self.proc and self.proc.poll() is None

    def stop(self):
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def name_of(model):
    """Which name this model joined under. Read from the server's state file, because the
    API hides models from agents until the game is over."""
    try:
        players = json.loads((ROOT / "state.json").read_text())["players"]
    except (OSError, json.JSONDecodeError, KeyError):
        return None
    return next((n for n, p in players.items() if p.get("model") == model), None)


def play_game(n, roster):
    game_dir = RUNS / f"{datetime.now():%Y%m%d-%H%M%S}-game{n}"
    game_dir.mkdir(parents=True)
    api("/api/reset", {})
    agents = [Agent(spec, game_dir) for spec in roster]
    for a in agents:
        a.start()
    log(f"game {n}: started {len(agents)} agents, logs in {game_dir.name}")

    t0 = time.time()
    while time.time() - t0 < JOIN_TIMEOUT:
        s = api("/api/state")
        alive = sum(a.alive() for a in agents)
        # Start once every agent that is still running has joined (a crashed CLI never will).
        if len(s["players"]) >= len(agents) or (len(s["players"]) >= max(2, alive) and time.time() - t0 > 60):
            break
        time.sleep(5)
    for a in agents:
        if not a.alive() and name_of(a.model) is None:
            log(f"game {n}: {a.model} exited before joining; see its log")
    s = api("/api/state")
    if len(s["players"]) < 2:
        log(f"game {n}: only {len(s['players'])} joined; giving up on this game")
        for a in agents:
            a.stop()
        return
    api("/api/force", {})
    log(f"game {n}: {len(s['players'])} joined, game started")

    last_key, last_change = None, time.time()
    while True:
        time.sleep(10)
        s = api("/api/state")
        key = (s["phase"], s["round"], tuple(p["status"] for p in s["players"]))
        if key != last_key:
            last_key, last_change = key, time.time()
            log(f"game {n}: {s['phase']} round {s['round']} " +
                " ".join(f"{p['name']}={p['status']}" for p in s["players"]))
        if s["phase"] == "results":
            break
        if time.time() - t0 > GAME_TIMEOUT:
            log(f"game {n}: hit the game time cap, forcing to the end")
            while api("/api/state")["phase"] != "results":
                api("/api/force", {})
            break
        if time.time() - last_change > STALL_TIMEOUT:
            stuck = [p["name"] for p in s["players"] if p["status"] in ("drawing", "voting")]
            log(f"game {n}: no progress for {STALL_TIMEOUT // 60} min, forcing past {', '.join(stuck)}")
            api("/api/force", {})
            last_change = time.time()
        # Restart agents that exited before the game ended.
        for a in agents:
            if not a.alive() and a.restarts < MAX_RESTARTS:
                name = name_of(a.model)
                if name is None and s["phase"] != "lobby":
                    continue   # never joined; it cannot join a started game
                a.restarts += 1
                log(f"game {n}: {a.model} exited, restart {a.restarts} as {name}")
                a.start(resume_name=name)

    final = api("/api/state")
    ranking = sorted(final["players"], key=lambda p: -p["total"])
    log(f"game {n}: finished. " + ", ".join(f"{p['name']} ({p.get('model')}) {p['total']}" for p in ranking))
    deadline = time.time() + 300   # let agents finish their last turn and exit
    while any(a.alive() for a in agents) and time.time() < deadline:
        time.sleep(5)
    for a in agents:
        a.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="07:30", help="local time to stop starting new games (HH:MM)")
    ap.add_argument("--games", type=int, default=12, help="maximum number of games")
    ap.add_argument("--roster", nargs="+", default=ROSTER, help="kind:model entries")
    args = ap.parse_args()
    RUNS.mkdir(exist_ok=True)
    hh, mm = map(int, args.until.split(":"))
    stop = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if stop <= datetime.now():
        stop += timedelta(days=1)
    log(f"league starts: up to {args.games} games until {stop:%Y-%m-%d %H:%M}, roster {' '.join(args.roster)}")
    for n in range(1, args.games + 1):
        if datetime.now() >= stop:
            break
        try:
            play_game(n, args.roster)
        except Exception as e:   # keep the night going; the log says what broke
            log(f"game {n}: runner error {e!r}")
            time.sleep(60)
    log("league done")


if __name__ == "__main__":
    main()
