"""Set up the our-story platform ladder league as its Coworld owner (docs: PLATFORM_LADDER_LEAGUE.md).

  ./tools/coworld_python.sh tools/league_setup.py LEAGUE_ID [--enable] [--trigger]

Declares one Competition division, writes the ladder settings (disabled unless --enable), and with
--trigger unpauses rounds and starts one. Uses the logged-in Softmax user credential through the
Coworld client; the token is never printed.
"""

import argparse
import json

from coworld.api_client import CoworldApiClient

SERVER = "https://softmax.com/api"


def call(client, method, path, body=None):
    response = client._http_client.request(method, path, headers=client._headers(), json=body)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    print(f"{method} {path} -> {response.status_code}")
    if response.status_code >= 400:
        print(json.dumps(data, indent=1)[:1500])
        raise SystemExit(1)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("league_id")
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--trigger", action="store_true")
    ap.add_argument("--round-interval-minutes", type=int, default=60)
    args = ap.parse_args()
    lid = args.league_id

    with CoworldApiClient.from_login(server_url=SERVER) as client:
        call(client, "PUT", f"/v2/leagues/{lid}/divisions",
             {"divisions": [{"name": "Competition", "level": 1, "type": "competition", "hidden": False}]})
        divisions = client._http_client.get("/v2/divisions", params={"league_id": lid},
                                            headers=client._headers()).json()
        entries = divisions.get("entries", divisions) if isinstance(divisions, dict) else divisions
        comp = [d for d in entries if d.get("name") == "Competition"]
        print("divisions:", [(d.get("id") or d.get("division_id"), d.get("name")) for d in entries])
        div_id = comp[0].get("id") or comp[0].get("division_id")

        current = call(client, "GET", f"/v2/leagues/{lid}/settings")
        settings = dict(current.get("settings") or {})
        settings["round_interval_minutes"] = args.round_interval_minutes
        settings["ladder"] = {
            "enabled": args.enable,
            "scheduler": {"strategy": "swiss_neighbor", "insufficient_players": "multiple_seats",
                          "min_episodes_per_entrant": 2},
            "fulfillment": {"allowed_failures": 0.1, "retry_times": 2},
            "ranking": {"algorithm": "score", "round_scoring_rule": "mean", "standing_aggregation": "ewma",
                        "half_life_hours": 48, "initial_standing": 0.0},
            "divisions": [{"division_id": div_id, "name": "Competition",
                           "disqualify_after_consecutive_failures": 3}],
        }
        call(client, "POST", f"/v2/leagues/{lid}/settings", settings)
        after = call(client, "GET", f"/v2/leagues/{lid}/settings")
        print("effective ladder:", json.dumps(after.get("effective_ladder_config"), indent=1)[:1200])

        if args.trigger:
            call(client, "POST", f"/v2/leagues/{lid}/rounds-paused", {"paused": False})
            call(client, "POST", f"/v2/leagues/{lid}/trigger-round", {})


if __name__ == "__main__":
    main()
