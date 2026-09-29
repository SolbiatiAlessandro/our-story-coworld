"""A stand-in for the Bedrock Converse endpoint, for testing the LLM player's plumbing offline."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        texts = " ".join(c.get("text", "") for m in body["messages"] for c in m["content"])
        images = sum("image" in c for m in body["messages"] for c in m["content"])
        m = re.search(r"Rank these pieces best first: ([A-Z, ]+)\.", texts)
        if m:
            action = {"ranking": [l.strip() for l in m.group(1).split(",")], "why": f"fake vote, saw {images} images"}
        else:
            action = {"piece": {"x": 60, "y": 40, "rows": ["yyyy", "y..y", "yyyy"]}, "why": f"fake piece, saw {images} images"}
        out = {"output": {"message": {"role": "assistant", "content": [{"text": json.dumps(action)}]}},
               "stopReason": "end_turn", "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
               "metrics": {"latencyMs": 1}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
