"""Request hosted our-story episodes with our LLM policies, one seat each (no league needed).

  ./tools/coworld_python.sh tools/hosted_episode.py --episodes 1 --spend 3.0

Seats are the policies below in order; the variant is the manifest's first one ("default", 6 seats). Prints the experience request id; follow it with
`./tools/coworld.sh xp-request episodes xreq_...` and `./tools/coworld.sh replay-open ereq_...`.
"""

import argparse
import json

from coworld.api_client import CoworldApiClient

SERVER = "https://softmax.com/api"
COWORLD_ID = "cow_e277e070-2c91-4442-ac0b-da26f266bdfa"   # our-story 0.1.0, canonical
POLICIES = ["ourstory-claude-opus-5-5", "ourstory-claude-sonnet-5-5", "ourstory-claude-haiku-4-5",
            "ourstory-gpt-6-astra", "ourstory-gpt-5-6-terra", "ourstory-gpt-5-6-luna"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--spend", type=float, default=3.0, help="approximate LLM spend cap per episode, USD")
    args = ap.parse_args()
    with CoworldApiClient.from_login(server_url=SERVER) as client:
        roster = []
        for slot, name in enumerate(POLICIES):
            pv = client.lookup_policy_version(name=name, version=None)
            print(f"seat {slot}: {name} v{pv.version} {pv.id}")
            roster.append({"player": {"policy_ref": str(pv.id)}, "slot": slot})
        body = {"coworld_id": COWORLD_ID, "roster": roster, "num_episodes": args.episodes,
                "episode_player_llm_spend_limit_usd": args.spend}
        detail = client.create_experience_request(body)
        print("experience request:", detail.id)


if __name__ == "__main__":
    main()
