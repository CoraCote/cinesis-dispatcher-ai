#!/usr/bin/env python3
"""
Cinesis Good Fit Test -- Orchestrator
Runs Part A (profile extraction) then Part B (load ranking) end-to-end.

Usage:
  python main.py              # full run: calls Claude API for Part A
  python main.py --offline    # skips API, uses pre-extracted profile for Part A
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def _banner(title: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _print_profile(profile) -> None:
    print()
    print(f"  Driver             : {profile.name}")
    print(f"  Current location   : {profile.current_location}")
    print(f"  Home base          : {profile.home_base}")
    print(f"  Equipment          : {profile.trailer_length_ft}ft {profile.equipment_type}")
    print(f"  Max weight         : {profile.max_weight_lbs:,} lbs")
    print(f"  Min effective rate : ${profile.min_effective_rate_per_mile:.2f}/mile (all-in)")
    print(f"  Available          : {profile.available_date}")
    print(f"  Hazmat certified   : {'Yes' if profile.hazmat_certified else 'No'}")
    print(f"  Team driver        : {'Yes' if profile.team_driver else 'No'}")
    print(f"  Preferred regions  : {', '.join(profile.preferred_regions)}")
    print(f"  Notes              :")
    for line in profile.notes.splitlines():
        print(f"    {line}")


# ─────────────────────────────────────────────────────────────────────────────
# Part A
# ─────────────────────────────────────────────────────────────────────────────

def _hardcoded_profile():
    """Pre-extracted profile for offline / no-credits mode."""
    from src.models import Coordinates, DriverProfile
    return DriverProfile(
        name="Mike Thompson",
        current_location=Coordinates(lat=32.7767, lon=-96.7970, city="Dallas", state="TX"),
        home_base=Coordinates(lat=35.1495, lon=-90.0490, city="Memphis", state="TN"),
        equipment_type="Dry Van",
        trailer_length_ft=53,
        max_weight_lbs=44000,
        available_date="2026-06-19",
        min_effective_rate_per_mile=2.50,
        preferred_regions=["Southeast", "Midwest"],
        hazmat_certified=False,
        team_driver=False,
        notes=(
            "[DIRECT] No livestock -- 'I don't do livestock. I'm not set up for that.'\n"
            "[DIRECT] No oversized loads -- 'I don't have the permits for oversized freight.'\n"
            "[DIRECT] Max 5 days preferred -- 'I don't want to be out more than five days if I can help it.'\n"
            "[DIRECT] Will stretch to 7 days if rate justifies it.\n"
            "[IMPLIED] Avoids West Coast -- 'I avoid the West Coast like the plague' (Colorado and beyond).\n"
            "[IMPLIED] Prefers loads pointing toward Memphis -- emphasizes Southeast brings him toward home.\n"
            "[IMPLIED] High deadhead sensitivity -- detailed story about a load ruined by 200 empty pickup miles."
        ),
    )


def run_part_a_llm(conversation_path: Path):
    from src.extractor import extract_driver_profile

    _banner("PART A -- DRIVER PROFILE EXTRACTION (rule-based)")
    conversation = conversation_path.read_text(encoding="utf-8")
    print(f"  Source: {conversation_path}  ({len(conversation):,} chars)")
    print("  Parsing transcript ...")

    profile = extract_driver_profile(conversation)
    _print_profile(profile)

    out = OUTPUT_DIR / "driver_profile.json"
    out.write_text(json.dumps(profile.model_dump(), indent=2), encoding="utf-8")
    print(f"\n  Saved -> {out}")
    return profile


def run_part_a_offline(conversation_path: Path):
    _banner("PART A -- DRIVER PROFILE (pre-extracted, offline mode)")
    print(f"  Source  : {conversation_path}")
    print("  API call: SKIPPED (--offline flag or no credits)")
    print("  Using hardcoded profile extracted from transcript.")

    profile = _hardcoded_profile()
    _print_profile(profile)

    out = OUTPUT_DIR / "driver_profile.json"
    out.write_text(json.dumps(profile.model_dump(), indent=2), encoding="utf-8")
    print(f"\n  Saved -> {out}")
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# Part B
# ─────────────────────────────────────────────────────────────────────────────

def run_part_b(profile, loads_path: Path) -> None:
    from src.ranker import filter_eligible_loads, load_loads_from_csv, rank_loads

    _banner("PART B -- LOAD FILTERING & RANKING")

    all_loads, skipped = load_loads_from_csv(loads_path)
    print(f"\n  Loads ingested : {len(all_loads)}")
    print(f"  Rows skipped   : {len(skipped)}  (incomplete data -- cannot compute rate)")
    for s in skipped:
        print(f"    SKIP  {s.load_id:6s} : {s.reason}")

    eligible, rejected = filter_eligible_loads(all_loads, profile)
    print(f"\n  After equipment/weight filter : {len(eligible)} eligible, {len(rejected)} rejected")
    for r in rejected:
        print(f"    REJECT {r.load_id:6s} : {r.reason}")

    top3, below_min = rank_loads(eligible, profile, top_n=3)
    if below_min:
        print(f"\n  Below minimum rate (${profile.min_effective_rate_per_mile:.2f}/mi) : {len(below_min)}")
        for b in below_min:
            print(f"    BELOW MIN {b.load_id:6s} : {b.reason}")

    print(f"\n  Driver position : {profile.current_location}")
    print(f"  Home base       : {profile.home_base}")

    _banner("TOP 3 LOADS  (by all-in effective rate/mile)")
    results_serializable = []

    for r in top3:
        origin = r.load.origin
        dest = r.load.destination
        print(f"\n  #{r.rank}  Load {r.load.load_id}")
        print(f"      Route    : {origin.city}, {origin.state}  ->  {dest.city}, {dest.state}")
        print(f"      Trailer  : {r.load.trailer_type}   Weight : {r.load.weight_lbs:,} lbs   Price : ${r.load.price:,.0f}")
        print(f"      Deadhead to origin : {r.deadhead_to_origin_miles:>7.2f} mi")
        print(f"      Loaded miles       : {r.loaded_miles:>7.2f} mi")
        print(f"      Deadhead home      : {r.deadhead_home_miles:>7.2f} mi")
        print(f"      -----------------------------------------")
        print(f"      Total miles        : {r.total_miles:>7.2f} mi")
        print(f"      Effective rate     :  ${r.effective_rate_per_mile:.3f}/mile  ***")

        results_serializable.append(
            {
                "rank": r.rank,
                "load_id": r.load.load_id,
                "route": f"{origin.city}, {origin.state} -> {dest.city}, {dest.state}",
                "trailer_type": r.load.trailer_type,
                "weight_lbs": r.load.weight_lbs,
                "price_usd": r.load.price,
                "deadhead_to_origin_miles": r.deadhead_to_origin_miles,
                "loaded_miles": r.loaded_miles,
                "deadhead_home_miles": r.deadhead_home_miles,
                "total_miles": r.total_miles,
                "effective_rate_per_mile": r.effective_rate_per_mile,
            }
        )

    out = OUTPUT_DIR / "top_3_loads.json"
    out.write_text(json.dumps(results_serializable, indent=2), encoding="utf-8")
    print(f"\n  Saved -> {out}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    offline = "--offline" in sys.argv

    conversation_path = DATA_DIR / "conversation.txt"
    loads_path = DATA_DIR / "loads.csv"

    for p in (conversation_path, loads_path):
        if not p.exists():
            print(f"ERROR: required file not found: {p}")
            sys.exit(1)

    if offline:
        profile = run_part_a_offline(conversation_path)
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY not set -- falling back to offline mode.")
            profile = run_part_a_offline(conversation_path)
        else:
            profile = run_part_a_llm(conversation_path)

    run_part_b(profile, loads_path)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
