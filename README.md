# Cinesis Good Fit Test

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY
python main.py                # runs both parts end-to-end
python verify_math.py         # Part B math only, no API call
```

## Assumptions

- **Current location** is Dallas, TX — the driver says "I'm sitting at the Pilot on I-20, east side of Dallas."
- **All-in effective rate** means `price ÷ (deadhead_to_origin + loaded_miles + deadhead_home)` using haversine straight-line miles, exactly per spec.
- **Available date** is 2026-06-19 ("tomorrow morning" relative to call date 2026-06-18).

## Part A — Extraction

Claude `claude-opus-4-8` reads the raw transcript with a structured JSON prompt. The system prompt lists every required field with explicit definitions and instructs the model to note implied constraints in a `notes` field. City names are resolved to lat/lon via a hard-coded lookup table rather than trusting the LLM for coordinates.

## Part B — Incomplete Rows

- **L007** (missing price): skipped — effective rate is undefined without it.
- **L008** (missing destination): skipped — two of the three distance legs are undefined.

## High-Paying Load Rejected as Ineligible

**L001** — Dallas → Chicago, Reefer, $5,500. Hypothetical effective rate: **$4.277/mile** (highest on the board). Rejected because it requires a **Reefer** trailer; the driver runs a **Dry Van**. This is the intended trap: the single highest-paying load fails the first hard filter.
