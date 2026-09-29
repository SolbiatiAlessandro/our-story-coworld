"""Command-line client for our-story-coworld. Stdlib only.

  python3 play.py join NAME
  python3 play.py look NAME
  python3 play.py place NAME "10,5,r 11,5,r 12,5,."
  python3 play.py done NAME          # submit fewer than the full pixels this turn
  python3 play.py rank NAME "C A D B"
  python3 play.py wait NAME          # block until something changes for you, then look

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
    """True while it is not this player's move."""
    s = json.loads(get("/api/state", name))
    me = s.get("me") or {}
    if s["phase"] == "lobby":
        return True
    if s["phase"] == "draw":
        return me.get("done") or len(me.get("queue", [])) >= s["pixels_per_turn"]
    if s["phase"] == "rank":
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
    elif cmd == "place":
        pixels = [p.split(",") for p in " ".join(args[1:]).split()]
        print(post("/api/place", {"name": name, "pixels": pixels}))
    elif cmd == "done":
        print(post("/api/done", {"name": name}))
    elif cmd == "rank":
        print(post("/api/rank", {"name": name, "order": " ".join(args[1:])}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
