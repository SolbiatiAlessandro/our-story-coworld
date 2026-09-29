"""Host commands for our-story-coworld (not for players).

  python3 host.py start    # start the game with whoever has joined
  python3 host.py force    # move on past a stuck agent
  python3 host.py reset    # save the current game to games/ and start a new one
"""

import sys

from play import post

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("start", "force"):
        print(post("/api/force", {}))
    elif cmd == "reset":
        print(post("/api/reset", {}))
    else:
        sys.exit(__doc__)
