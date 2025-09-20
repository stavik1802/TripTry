# Trip Planner with Reasoning Agent — PRD (MVP)

## 1) Summary
Build a multi-country trip planner that turns **free-text** requests (or a structured form) into a **day-by-day itinerary** with **inferred costs**—entries, intra-city transfers, inter-city hops, and lodging—plus time windows, route order, and transparent **source citations & confidence**.  
The system uses a **Reasoning Agent (LangGraph)** orchestrating **discovery → normalization → inference → verification → optimization**.

---

## 2) Users & Jobs-to-be-Done
- **Independent travelers** (solo/couples/small groups): “Give me a feasible, priced plan that fits my time and budget without me entering prices.”
- **Travel planners/ops**: “Create a shareable draft with transparent assumptions and sources.”

**Primary jobs**
- Plan multi-country itineraries that respect opening hours, travel times, and budgets.
- See a clear cost breakdown (Entries / Transfers / Lodging) with per-item sources.
- Get **Plan-B** for uncertain items or closures.

---

## 3) Scope & Goals
### In-scope (MVP)
- **Input**: free text in natural language **or** structured JSON form.
- **Multi-country**: countries (ordered/flexible), optional preferred cities per country.
- **Must-see POIs**, preferences (pace, mobility, time↔money, safety buffer, overnight/one-way rental, rail-pass consideration), budget caps (total/per day), target currency, optional passport/visa notes (soft checks).
- **Output**:
  - Itinerary grouped by **country → city → day**
  - **Inferred costs** for entry fees, transfers (legs), lodging (per night), inter-country hops
  - **Source chips + confidence** and “as of” timestamps
  - **Per-day and per-country subtotals**; overall totals in target currency
  - Cross-border legs with door-to-door time (incl. overheads)
  - **Plan-B** suggestions when uncertainty/closures exist
- **Optimization**: Honor time windows, must-sees, budget caps, start/end at lodging; minimize (weighted) time vs. money.

### Out-of-scope (MVP)
- Booking/ticketing, seat selection, live inventory.
- Real-time traffic predictions; navigation turn-by-turn.
- Legal visa advice (only surface official info with uncertainty labels).

---

## 4) Non-functional Requirements
- **Traceability**: Every numeric value is traceable to a source or inference method with confidence.
- **Performance**: End-to-end plan under **~90 seconds** on typical scenarios (soft target).  
- **Cost**: API/LLM budget cap per run (configurable default e.g., \$8). Early stopping rules.
- **Reliability**: No time overlaps; budget constraints respected (or clearly flagged with trade-offs).
- **i18n**: Free-text can be in any language; output in English (MVP), future toggle.

---

## 5) System Overview (high level)
A **LangGraph** Reasoning Agent coordinates nodes:

- **Country_Expander** → proposes city hubs per country (based on musts & distance).
- **HolidayCalendar_Discovery** → public holidays affecting dates.
- **FX_Oracle** → lock run-level FX rates; store native+converted amounts.
- **POI_Discovery / Lodging_Discovery / CityFares_Discovery / Intercity_Discovery** → find official pages & candidates.
- **Normalize_Enrich** → currency/time normalization, durations, geocoding.
- **Cost_Inference_Synthesizer** → infer missing prices, compute ranges, decide day-pass, estimate taxi/rental, one-way drop fees, vignettes/tolls.
- **Conflict_Checker ↔ Evidence_Booster** → detect/resolve discrepancies; require independent sources for high-impact items.
- **Timezone_Normalizer** → ensure local times across borders.
- **GeoCost_Assembler** → edge matrices (time/cost) for hotel↔POI↔POI and inter-city legs.
- **Itinerary_Optimizer** → TOPTW-style greedy + repair; enforce budget/time windows.
- **Tradeoff_Suggester** → alternatives when over budget/time or uncertain.
- **Writer_Report** → produce per-day plan, costs, citations, Plan-B.
- **Export** → JSON (UI), optional Markdown/PDF/Sheet.

---

## 6) Inputs & Parsing

### 6.1 Free-text (primary UX)
Examples:
> “Oct 10–20, two adults. Italy → Switzerland → France. Must: Colosseum, Uffizi, Louvre. Normal pace, prefer rail & transit, no overnight trains. Budget €2500 total.”

**Parser pipeline**
1. **Rule-based** extraction for dates, budgets (currency detection), travelers, modes, musts, countries/cities.
2. **Geocoding & disambiguation** (Paris FR vs. TX; Firenze=Florence).
3. **LLM finalize (optional)**: function-call to fill gaps and validate enum/booleans → strict PlanRequest JSON.
4. **Defaults**: if missing—dates=3 days starting 2 weeks out, pace=normal, mobility=[walk, transit, taxi], target_currency=EUR, rail_pass_consider=false.

### 6.2 Structured JSON (power users/API)
See API section for full schema.

---

## 7) Outputs
- **Daily itinerary** with items:
  - `lodging` (name, nightly total, confidence, sources)
  - sequence of POIs with `start/end`, `entry_fee{value, method, confidence, sources}`
  - **arrivals/legs** with `mode`, `time_min`, `cost`, `assumptions`, `sources`
- **Totals** per day & country, and trip totals:
  - `entries`, `transfers`, `lodging`, `grand_total` (native + converted)
- **Rail Pass decision** (if considered): worth?, savings, assumptions, sources
- **Conflicts** & **Plan-B** list
- **Trace**: tool calls & node transitions (no private chain-of-thought)

---

## 8) Cost Inference (core logic)
- **POI entry fees**: prefer official pages; if missing, triangulate 2–3 independent sources; seasonal/tiered → produce range; store `method`, `assumptions`, `confidence`.
- **Lodging**: sample 8–15 options in radius & rating; compute **trimmed mean** nightly total (rate+taxes+fees); apply month/weekend multipliers; select primary+fallback near POI centroid.
- **Intra-city**:
  - **Walk** cost=0; time=distance/pace.
  - **Transit**: single fare vs. **day-pass decision** (buy if expected rides × single ≥ 0.85 × pass).
  - **Taxi**: `base + per_km*d + per_min*t` (optionally surge range).
  - **Rental**: `fuel_per_km*d + parking + tolls` (daily rental cost tracked separately).
- **Inter-city**:
  - Rail/bus: per-km baselines adjusted by frequency; add border dwell if typical.
  - Flights: include airport overhead (check-in, security) in door-to-door time; baggage policy line item.
  - Rental: possible **one-way drop fee**, **vignette/toll** per country.
- **FX**: store native & converted using **run-snapshot FX**; display `CHF 8.2 → €8.5 (fx 1.04)`.

---

## 9) Optimization
- Model: **Team Orienteering / TOPTW** (greedy baseline + local repair).
- Constraints: time windows (opening hours), must-see inclusion, budget caps (entries + transfers + lodging), start/end at lodging, daily safety buffers, cross-border timezones.
- Objective: weighted **time vs. money** per user slider; minimize transfers where ties.

---

## 10) API Contracts

### 10.1 `POST /api/plan` — Free text
```json
{ "query": "Oct 10–20, two adults, Italy → Switzerland → France, must: Colosseum, Uffizi, Louvre, prefer rail, budget €2500." }
