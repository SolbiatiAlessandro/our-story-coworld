"""A stand-in for the Softmax LLM sidecar (OpenAI chat format), for testing the LLM player offline."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.path == "/v1/chat/completions", self.path
        user = body["messages"][-1]["content"]
        texts = " ".join(c.get("text", "") for c in user)
        images = sum(c.get("type") == "image_url" for c in user)
        m = re.search(r"Rank these pieces best first: ([A-Z, ]+)\.", texts)
        if m:
            action = {"ranking": [l.strip() for l in m.group(1).split(",")], "why": f"fake vote, saw {images} images"}
        else:
            action = {"piece": {"x": 60, "y": 40, "rows": ["yyyy", "y..y", "yyyy"]}, "why": f"fake piece, saw {images} images"}
        out = {"choices": [{"index": 0, "finish_reason": "stop",
                            "message": {"role": "assistant", "content": json.dumps(action)}}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
