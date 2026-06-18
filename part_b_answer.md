# Part B Answer — Top 3 Eligible Loads

**Driver:** Mike Thompson  
**Current location:** Dallas, TX (32.7767, -96.7970)  
**Home base:** Memphis, TN (35.1495, -90.0490)  
**Effective rate formula:** `price / (deadhead_to_origin + loaded_miles + deadhead_home)` — all haversine straight-line miles

---

## Rank 1 — Load L002

| | |
|---|---|
| Route | Fort Worth, TX → Nashville, TN |
| Trailer | Dry Van |
| Weight | 42,000 lbs |
| Price | $3,200 |
| Deadhead to origin (Dallas → Fort Worth) | 31.05 mi |
| Loaded miles (Fort Worth → Nashville) | 645.00 mi |
| Deadhead home (Nashville → Memphis) | 196.33 mi |
| **Total miles** | **872.38 mi** |
| **Effective rate** | **$3.668/mile** |

---

## Rank 2 — Load L003

| | |
|---|---|
| Route | Dallas, TX → Atlanta, GA |
| Trailer | Dry Van |
| Weight | 39,500 lbs |
| Price | $3,800 |
| Deadhead to origin | 0.00 mi |
| Loaded miles (Dallas → Atlanta) | 719.62 mi |
| Deadhead home (Atlanta → Memphis) | 336.69 mi |
| **Total miles** | **1,056.31 mi** |
| **Effective rate** | **$3.597/mile** |

---

## Rank 3 — Load L010

| | |
|---|---|
| Route | Austin, TX → Memphis, TN |
| Trailer | Dry Van |
| Weight | 41,000 lbs |
| Price | $2,600 |
| Deadhead to origin (Dallas → Austin) | 182.12 mi |
| Loaded miles (Austin → Memphis) | 559.94 mi |
| Deadhead home (Memphis → Memphis) | **0.00 mi** |
| **Total miles** | **742.06 mi** |
| **Effective rate** | **$3.504/mile** |

> Note: L010 drops the driver at his home base (Memphis → Memphis = 0 deadhead). Despite a lower price tag ($2,600), the zero return-home leg makes it competitive.

---

## Loads Excluded and Why

| Load | Reason |
|------|--------|
| **L001** — Dallas → Chicago (Reefer, $5,500) | **Wrong trailer type.** Requires Reefer; driver runs Dry Van. Hypothetical rate would be $4.277/mi — the highest on the board. This is the trap. |
| **L006** — Dallas → Houston (Dry Van, 47,500 lbs) | **Overweight.** 47,500 lbs exceeds driver's 44,000-lb maximum. |
| **L009** — Dallas → Kansas City (Flatbed, $3,500) | **Wrong trailer type.** Requires Flatbed; driver runs Dry Van. |
| **L005** — Dallas → Denver (Dry Van, $2,200) | **Below minimum rate.** $2,200 / 1,540 total miles = $1.429/mi < $2.50 floor. Denver is 877 miles from Memphis — the dead-head home destroys the rate. |
| **L012** — Little Rock → Atlanta (Dry Van, $2,600) | **Below minimum rate.** $2,600 / 1,086 total miles = $2.395/mi < $2.50 floor. Also has 292 miles of deadhead just to get to origin in Little Rock. |
| **L007** — OKC → Memphis | **Skipped** — missing price; effective rate cannot be computed. |
| **L008** — Little Rock → (unknown) | **Skipped** — missing destination; two of three distance legs undefined. |
