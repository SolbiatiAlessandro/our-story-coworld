"""Command-line client for our-story-coworld. Stdlib only.

  python3 play.py look
  python3 play.py place NAME "10,5,r 11,5,r 12,5,o" --note "a sunset starts"
  python3 play.py say NAME "I'm drawing a house at the bottom left"
  python3 play.py done NAME
  python3 play.py wait            # block until the next turn starts, then look

Set OUR_STORY_URL to use a server other than http://localhost:8765.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ.get("OUR_STORY_URL", "http://localhost:8765")


def get(path):
    with urllib.request.urlopen(URL + path) as r:
        return r.read().decode()


def post(path, body):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    note = ""
    if "--note" in args:
        i = args.index("--note")
        note = args[i + 1]
        args = args[:i] + args[i + 2:]
    if cmd == "look":
        print(get("/api/canvas.txt"))
    elif cmd == "wait":
        turn = json.loads(get("/api/state"))["turn"]
        while json.loads(get("/api/state"))["turn"] == turn:
            time.sleep(2)
        print(get("/api/canvas.txt"))
    elif cmd == "place":
        name, spec = args[0], " ".join(args[1:])
        pixels = [p.split(",") for p in spec.split()]
        print(post("/api/place", {"name": name, "pixels": pixels, "note": note}))
    elif cmd == "say":
        print(post("/api/say", {"name": args[0], "text": " ".join(args[1:])}))
    elif cmd == "done":
        print(post("/api/done", {"name": args[0]}))
    elif cmd == "join":
        print(post("/api/join", {"name": args[0]}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
