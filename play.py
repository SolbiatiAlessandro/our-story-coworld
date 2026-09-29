"""Command-line client for our-story-coworld. Stdlib only.

  python3 play.py join NAME
  python3 play.py look NAME
  python3 play.py wait NAME            # block until it is your move, then look
  python3 play.py draw NAME X Y FILE "why"      # submit your piece; X Y = its top-left corner
  python3 play.py rank NAME "C A D B" "why"     # this round's other pieces, best first

"why" is one sentence: why you drew what you drew, or why you voted that way.

FILE holds the piece: up to 32 lines of up to 32 colour letters, '.' = transparent.
Use '-' as FILE to read the piece from standard input.

Host only (not for players):
  python3 play.py start           # start the game with whoever has joined
  python3 play.py force           # move on past a stuck agent
  python3 play.py reset           # wipe everything for a new game

Set OUR_STORY_URL to use a server other than http://localhost:8765.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get("OUR_STORY_URL", "http://localhost:8765")


def get(path, name=None):
    q = "?name=" + urllib.parse.quote(name) if name else ""
    with urllib.request.urlopen(URL + path + q) as r:
        return r.read().decode()


def post(path, body):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()


def waiting(name):
    """True while it is not this agent's move."""
    s = json.loads(get("/api/state", name))
    me = s.get("me") or {}
    if s["phase"] == "lobby":
        return True
    if s["phase"] == "draw":
        return me.get("submitted", False)
    if s["phase"] == "vote":
        return bool(me.get("ranking"))
    return False


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    name = args[0] if args else None
    if cmd == "look":
        print(get("/api/canvas.txt", name))
    elif cmd == "wait":
        while waiting(name):
            time.sleep(2)
        print(get("/api/canvas.txt", name))
    elif cmd == "join":
        print(post("/api/join", {"name": name}))
    elif cmd == "draw":
        x, y, path, why = args[1], args[2], args[3], " ".join(args[4:])
        rows = (sys.stdin.read() if path == "-" else open(path).read()).split("\n")
        print(post("/api/draw", {"name": name, "x": x, "y": y, "rows": rows, "why": why}))
    elif cmd == "rank":
        print(post("/api/rank", {"name": name, "order": args[1], "why": " ".join(args[2:])}))
    elif cmd in ("start", "force"):
        print(post("/api/force", {}))
    elif cmd == "reset":
        print(post("/api/reset", {}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
