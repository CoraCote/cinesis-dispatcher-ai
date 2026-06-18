"""Part B — Load filtering and ranking by all-in effective rate per mile."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.haversine import distance_between
from src.models import Coordinates, DriverProfile, Load, RankedLoad


# ──────────────────────────────────────────────────────────────────────────────
# CSV ingestion
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SkippedRow:
    load_id: str
    reason: str
    raw: dict


def load_loads_from_csv(filepath: Path) -> tuple[list[Load], list[SkippedRow]]:
    """
    Parse loads.csv into Load objects.

    Incomplete rows (missing price OR missing destination coordinates) are
    excluded from ranking because the effective rate cannot be computed without
    both legs of the haversine calculation.  They are returned separately so
    the caller can log them rather than silently dropping them.
    """
    loads: list[Load] = []
    skipped: list[SkippedRow] = []

    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lid = row.get("load_id", "?").strip()
            issues: list[str] = []

            # --- price ---
            raw_price = row.get("price", "").strip()
            price: Optional[float] = None
            if raw_price:
                try:
                    price = float(raw_price)
                except ValueError:
                    issues.append(f"unparseable price '{raw_price}'")
            else:
                issues.append("missing price")

            # --- destination ---
            dest_city = row.get("destination_city", "").strip()
            dest_state = row.get("destination_state", "").strip()
            raw_dest_lat = row.get("destination_lat", "").strip()
            raw_dest_lon = row.get("destination_lon", "").strip()

            destination: Optional[Coordinates] = None
            if dest_city and raw_dest_lat and raw_dest_lon:
                try:
                    destination = Coordinates(
                        lat=float(raw_dest_lat),
                        lon=float(raw_dest_lon),
                        city=dest_city,
                        state=dest_state,
                    )
                except ValueError:
                    issues.append("unparseable destination coordinates")
            else:
                issues.append("missing destination")

            if issues:
                skipped.append(SkippedRow(load_id=lid, reason="; ".join(issues), raw=dict(row)))
                continue

            # --- origin (required, crash-fast: data error if missing) ---
            origin = Coordinates(
                lat=float(row["origin_lat"]),
                lon=float(row["origin_lon"]),
                city=row["origin_city"].strip(),
                state=row["origin_state"].strip(),
            )

            loads.append(
                Load(
                    load_id=lid,
                    trailer_type=row["trailer_type"].strip(),
                    origin=origin,
                    destination=destination,
                    weight_lbs=int(row["weight_lbs"]),
                    price=price,
                    notes=row.get("notes", "").strip(),
                )
            )

    return loads, skipped


# ──────────────────────────────────────────────────────────────────────────────
# Eligibility filtering
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RejectedLoad:
    load_id: str
    reason: str


def filter_eligible_loads(
    loads: list[Load], profile: DriverProfile
) -> tuple[list[Load], list[RejectedLoad]]:
    """
    Apply hard-constraint filters derived from the driver profile.

    Filters applied (in order):
      1. Trailer type must match driver equipment.
      2. Load weight must not exceed driver capacity.

    Rate filtering is done later (in rank_loads) because it requires distance
    computation — keeping concerns separated makes each step independently testable.
    """
    eligible: list[Load] = []
    rejected: list[RejectedLoad] = []

    for load in loads:
        if load.trailer_type.lower() != profile.equipment_type.lower():
            rejected.append(
                RejectedLoad(
                    load_id=load.load_id,
                    reason=(
                        f"trailer mismatch — load requires {load.trailer_type}, "
                        f"driver has {profile.equipment_type}"
                    ),
                )
            )
            continue

        if load.weight_lbs > profile.max_weight_lbs:
            rejected.append(
                RejectedLoad(
                    load_id=load.load_id,
                    reason=(
                        f"overweight — load is {load.weight_lbs:,} lbs, "
                        f"driver max is {profile.max_weight_lbs:,} lbs"
                    ),
                )
            )
            continue

        eligible.append(load)

    return eligible, rejected


# ──────────────────────────────────────────────────────────────────────────────
# Ranking
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BelowMinRate:
    load_id: str
    reason: str


def rank_loads(
    loads: list[Load],
    profile: DriverProfile,
    top_n: int = 3,
) -> tuple[list[RankedLoad], list[BelowMinRate]]:
    """
    Compute effective rate for each load and return the top_n ranked by that rate.

    Effective rate formula (per spec):
        price / (deadhead_to_origin + loaded_miles + deadhead_home)

    All three legs use straight-line haversine distance.
      - deadhead_to_origin : profile.current_location  → load origin
      - loaded_miles       : load origin               → load destination
      - deadhead_home      : load destination          → profile.home_base

    Loads whose effective rate falls below profile.min_effective_rate_per_mile
    are filtered out and returned in the BelowMinRate list for transparency.
    """
    ranked: list[RankedLoad] = []
    below_min: list[BelowMinRate] = []

    for load in loads:
        dh_origin = distance_between(profile.current_location, load.origin)
        loaded = distance_between(load.origin, load.destination)
        dh_home = distance_between(load.destination, profile.home_base)
        total = dh_origin + loaded + dh_home

        effective_rate = load.price / total

        if effective_rate < profile.min_effective_rate_per_mile:
            shortfall = profile.min_effective_rate_per_mile - effective_rate
            below_min.append(
                BelowMinRate(
                    load_id=load.load_id,
                    reason=(
                        f"effective rate ${effective_rate:.3f}/mi < "
                        f"minimum ${profile.min_effective_rate_per_mile:.2f}/mi "
                        f"(shortfall ${shortfall:.3f}/mi) | "
                        f"${load.price:,.0f} / {total:.1f} mi total "
                        f"[DH-to-origin {dh_origin:.1f} + loaded {loaded:.1f} + DH-home {dh_home:.1f}]"
                    ),
                )
            )
            continue

        ranked.append(
            RankedLoad(
                load=load,
                deadhead_to_origin_miles=round(dh_origin, 2),
                loaded_miles=round(loaded, 2),
                deadhead_home_miles=round(dh_home, 2),
                total_miles=round(total, 2),
                effective_rate_per_mile=round(effective_rate, 3),
                rank=0,
            )
        )

    ranked.sort(key=lambda r: r.effective_rate_per_mile, reverse=True)
    for i, r in enumerate(ranked):
        r.rank = i + 1

    return ranked[:top_n], below_min
