"""
Standalone verification script — runs Part B math without any API call.
Uses a hardcoded driver profile matching what Part A should extract.
Run with:  python verify_math.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models import Coordinates, DriverProfile
from src.ranker import filter_eligible_loads, load_loads_from_csv, rank_loads

HARDCODED_PROFILE = DriverProfile(
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
    notes="Hardcoded for local verification of Part B math.",
)


def main() -> None:
    loads_path = Path("data/loads.csv")
    all_loads, skipped = load_loads_from_csv(loads_path)

    print("== SKIPPED (incomplete data) ==================================")
    for s in skipped:
        print(f"  {s.load_id:6s}  {s.reason}")

    eligible, rejected = filter_eligible_loads(all_loads, HARDCODED_PROFILE)

    print("\n== REJECTED (equipment / weight) ==============================")
    for r in rejected:
        print(f"  {r.load_id:6s}  {r.reason}")

    top3, below_min = rank_loads(eligible, HARDCODED_PROFILE, top_n=len(eligible))

    print("\n== BELOW MINIMUM RATE =========================================")
    for b in below_min:
        print(f"  {b.load_id:6s}  {b.reason}")

    print("\n== ELIGIBLE LOADS RANKED ======================================")
    header = (
        f"{'#':>3}  {'ID':6}  {'Origin':18}  {'Dest':18}  "
        f"{'DH-O':>7}  {'Loaded':>7}  {'DH-H':>7}  {'Total':>8}  {'$/mi':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in top3:
        o = r.load.origin
        d = r.load.destination
        orig_str = f"{o.city}, {o.state}"
        dest_str = f"{d.city}, {d.state}"
        print(
            f"{r.rank:>3}  {r.load.load_id:6}  {orig_str:18}  {dest_str:18}  "
            f"{r.deadhead_to_origin_miles:>7.2f}  {r.loaded_miles:>7.2f}  "
            f"{r.deadhead_home_miles:>7.2f}  {r.total_miles:>8.2f}  "
            f"${r.effective_rate_per_mile:>6.3f}"
        )

    print(f"\n  TOP 3: {', '.join(r.load.load_id for r in top3[:3])}")
    print()


if __name__ == "__main__":
    main()
