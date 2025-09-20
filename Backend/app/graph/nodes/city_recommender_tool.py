# app/tools/city_recommender_tool.py  — v4 (ULTRA-FAST: single Tavily search/country; no extract)
from __future__ import annotations
import os, re, json, math, textwrap, time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.graph.state import AppState  # optional back-compat
except Exception:
    @dataclass
    class AppState:
        request: Dict[str, Any]
        logs: List[str] = None
        meta: Dict[str, Any] = None

from pydantic import BaseModel, Field, field_validator, ValidationError
from concurrent.futures import ThreadPoolExecutor, as_completed

# External deps
from tavily import TavilyClient
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ======================= Config (tunable via ENV) =======================
PACE_TO_DAYS = {"slow": 4.0, "normal": 3.0, "fast": 2.0}
HOP_OVERHEAD_DAYS = 0.5
MAX_CITY_CANDIDATES = 25

# Tavily usage — keep it tiny
SEARCH_DEPTH             = os.getenv("CITYREC_SEARCH_DEPTH", "basic")  # basic is cheaper
MAX_RESULTS_PER_COUNTRY  = int(os.getenv("CITYREC_MAX_RESULTS_PER_COUNTRY", "6"))  # we'll keep 2
MAX_COUNTRY_SNIPPETS     = 2  # <= 2 URLs fed to LLM
SEARCH_TIMEOUT_SEC       = float(os.getenv("CITYREC_SEARCH_TIMEOUT_SEC", "7"))

# Prompt budgets (for Tavily answer + snippets only)
MAX_SNIPPET_CHARS        = int(os.getenv("CITYREC_MAX_SNIPPET_CHARS", "1200"))
MIN_KEEP_PER_CHUNK       = int(os.getenv("CITYREC_MIN_KEEP_PER_CHUNK", "500"))
MAX_TOTAL_CHARS_PROMPT   = int(os.getenv("CITYREC_MAX_TOTAL_CHARS", "16000"))

OPENAI_MODEL_DEFAULT     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE              = 0.0

OFFICIAL_HINTS = (".gov", ".gouv.", ".edu", ".tourism", "visit", "comune.", "city.", ".go.jp", ".govt")


# ======================= Schema =======================
class CountryArg(BaseModel):
    country: Optional[str] = None
    name: Optional[str] = None
    cities: List[str] = Field(default_factory=list)
    @property
    def norm_country(self) -> Optional[str]:
        return (self.country or self.name or "").strip() or None

class CityRecommenderArgs(BaseModel):
    countries: List[CountryArg]
    dates: Optional[Dict[str, str]] = None
    travelers: Dict[str, int] = Field(default_factory=lambda: {"adults":1, "children":0})
    musts: List[str] = Field(default_factory=list)
    preferred_cities: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    default_recommend_count: int = Field(default=5, ge=1, le=20)
    max_candidates: int = Field(default=12, ge=5, le=40)
    model: Optional[str] = None

    @field_validator("dates")
    @classmethod
    def _validate_dates(cls, v):
        if not v:
            return v
        try:
            s, e = v.get("start"), v.get("end")
            datetime.strptime(s[:10], "%Y-%m-%d")
            datetime.strptime(e[:10], "%Y-%m-%d")
        except Exception:
            raise ValueError("dates.start/end must be ISO YYYY-MM-DD")
        return v

class CityCandidate(BaseModel):
    city: str
    country: str
    score: float
    sources: List[str] = Field(default_factory=list)
    family_hits: Optional[int] = None

class CityRecommenderResult(BaseModel):
    cities: List[str]
    city_country_map: Dict[str, str]
    recommended_city_count: int
    city_candidates: List[CityCandidate]
    stats: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)


# ======================= Helpers =======================
def _trip_days(ds: str, de: str) -> int:
    s = datetime.strptime(ds[:10], "%Y-%m-%d").date()
    e = datetime.strptime(de[:10], "%Y-%m-%d").date()
    return (e - s).days + 1

def _recommend_city_count(trip_days: int, pace: str, must_cities: int) -> int:
    tpc = PACE_TO_DAYS.get(pace, 3.0)
    C = 1
    while True:
        usable = trip_days - HOP_OVERHEAD_DAYS * max(0, C - 1)
        need   = C * tpc
        if usable >= need:
            C += 1
            if C > 20: break
        else:
            C -= 1
            break
    C = max(1, C)
    return max(C, must_cities)

def _unique_domains(urls: List[str]) -> int:
    doms = set()
    for u in urls or []:
        if "://" in u:
            doms.add(u.split("/")[2])
    return len(doms)

def _is_official(url: Optional[str]) -> bool:
    if not url: return False
    low = url.lower()
    return any(h in low for h in OFFICIAL_HINTS)

def _clean_city_name(tok: str) -> Optional[str]:
    tok = (tok or "").strip(" .:;–—-()[]")
    if not tok or len(tok) < 2:
        return None
    if not re.match(r"^[A-ZÀ-Ý][A-Za-zÀ-ÿ'’ -]{1,}$", tok):
        return None
    if len(tok.split()) > 3:
        return None
    return tok

def _score_city(row, with_kids: bool, musts: List[str], preferred: List[str]) -> float:
    s = 0.0
    if row.get("is_capital"): s += 0.35
    if with_kids and row.get("family_hint"): s += 0.15
    urls = (row.get("evidence_urls") or []) + (row.get("sources_seed") or [])
    dom_div = _unique_domains(urls)
    s += 0.35 * min(1.0, dom_div / 3.0)
    nm = (row.get("name") or "").lower()
    if any(nm == m.lower() or nm in m.lower() for m in musts): s += 0.3
    if any(nm == p.lower() or nm in p.lower() for p in preferred): s += 0.1
    if any(_is_official(u) for u in urls): s += 0.05
    return round(s, 3)

def _tavily() -> TavilyClient:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)

def _openai_client_or_none() -> Optional[OpenAI]:
    if OpenAI is None:
        return None
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None


# ======================= Search-only acquisition (1 search/country) =======================
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}

def _country_query(country: str, with_kids: bool) -> str:
    kid = " family friendly" if with_kids else ""
    # single concise query; ask for official leaning
    return f"best cities to visit in {country}{kid}. Prefer official tourism websites."

def _search_minimal_for_country(tv: TavilyClient, country: str, with_kids: bool) -> Tuple[List[Dict[str,str]], Optional[str]]:
    """
    Single Tavily search call per country.
    Returns (picked_results[:2], answer_text).
    Each result: {url,title,content}
    """
    q = _country_query(country, with_kids)
    if q in _SEARCH_CACHE:
        sr = _SEARCH_CACHE[q]
    else:
        sr = tv.search(
            q,
            include_answer=True,
            search_depth=SEARCH_DEPTH,
            max_results=MAX_RESULTS_PER_COUNTRY,
            include_raw_content=False,
            timeout=SEARCH_TIMEOUT_SEC,
        ) or {}
        _SEARCH_CACHE[q] = sr

    # Collect results
    all_results: List[Dict[str,str]] = []
    for r in (sr.get("results") or []):
        url = (r.get("url") or "").strip()
        title = (r.get("title") or "").strip()
        content = (r.get("content") or "").strip()
        if url and title:
            all_results.append({"url": url, "title": title, "content": content})

    # Prefer official-first, then diverse domains; keep at most 2
    def is_off(u: str) -> bool:
        return _is_official(u)
    # stable sort: official first
    all_results.sort(key=lambda d: (0 if is_off(d["url"]) else 1, d["url"]))
    picked: List[Dict[str,str]] = []
    seen_domains = set()
    for r in all_results:
        dom = r["url"].split("/")[2] if "://" in r["url"] else r["url"]
        if dom in seen_domains:
            continue
        seen_domains.add(dom)
        picked.append(r)
        if len(picked) >= MAX_COUNTRY_SNIPPETS:
            break

    return picked, (sr.get("answer") or None)


# ======================= LLM parsing =======================
def _trim_text(s: str, per_chunk: int, min_keep: int) -> str:
    s = (s or "").strip()
    if not s: return s
    s = re.sub(r"\s+", " ", s)
    allow = max(min_keep, per_chunk)
    return s[:allow]

def _cap_chunks(chunks: List[Tuple[str,str]], total_cap: int, min_keep: int) -> List[Tuple[str,str]]:
    if not chunks: return chunks
    total = sum(len(t) for _, t in chunks)
    if total <= total_cap: return chunks
    ratio = max(0.05, float(total_cap) / float(total))
    out = []
    for (u, t) in chunks:
        allow = max(min_keep, int(len(t) * ratio))
        out.append((u, t[:allow]))
    return out

def _build_city_prompt_from_snippets(
    country: str,
    with_kids: bool,
    answer_text: Optional[str],
    results: List[Dict[str,str]],
    given_cities: List[str],
    musts: List[str],
    preferred: List[str],
) -> Tuple[str, List[str]]:
    header = f"""
    Extract city recommendations for short trips in {country} from the notes below.
    Return STRICT JSON:
    {{
      "cities": [
        {{
          "name": "...",
          "is_capital": true|false|null,
          "family_hint": true|false|null,
          "evidence_urls": ["...", "..."]
        }}
      ]
    }}
    Rules:
    - Prefer well-known tourist cities; avoid regions/islands/counties/lakes/coasts.
    - If kids are present, give weight to mentions of zoos, aquariums, science museums, parks, kid attractions.
    - Cap at most {MAX_CITY_CANDIDATES} items.
    - Include user-provided and MUST/Preferred when plausible:
      * Provided (keep unless clearly unsuitable): {given_cities or []}
      * MUST: {musts or []}
      * Preferred: {preferred or []}
    - JSON only.
    """
    kid_line = ("Children present; lean slightly kid-friendly." if with_kids
                else "Adults only; no special kid focus.")

    chunks: List[Tuple[str,str]] = []
    sources: List[str] = []

    if answer_text:
        chunks.append(("tavily:search:answer", _trim_text(answer_text, MAX_SNIPPET_CHARS, MIN_KEEP_PER_CHUNK)))
        sources.append("tavily:search:answer")

    for r in results:
        u = r["url"]
        snip = r.get("content") or r.get("title") or ""
        chunks.append((u, _trim_text(snip, MAX_SNIPPET_CHARS, MIN_KEEP_PER_CHUNK)))
        sources.append(u)

    chunks = _cap_chunks(chunks, MAX_TOTAL_CHARS_PROMPT, MIN_KEEP_PER_CHUNK)

    parts = [textwrap.dedent(header), kid_line, "\n\n"]
    for (u, t) in chunks:
        parts.append(f"[SOURCE] {u}\n[TEXT]\n{t}\n\n")

    return "".join(parts), sources

def _extract_cities_with_llm(ocli: OpenAI, model: str, prompt: str) -> Dict[str, Any]:
    resp = ocli.chat.completions.create(
        model=model,
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a precise information extractor. Reply with strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    txt = resp.choices[0].message.content  # type: ignore
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{[\s\S]*\}\s*$", txt or "")
        return json.loads(m.group(0)) if m else {"cities": []}


# ======================= Tool (pure) =======================
class _Stats(dict): pass

def city_recommender_tool(args: CityRecommenderArgs) -> CityRecommenderResult:
    logs: List[str] = []
    tv = _tavily()
    ocli = _openai_client_or_none()
    if ocli is None:
        raise RuntimeError("OPENAI_API_KEY not set or openai SDK unavailable")

    countries = [c.norm_country for c in (args.countries or []) if c.norm_country]
    if not countries:
        raise ValueError("countries is required (list of {country|name}).")

    with_kids = int((args.travelers or {}).get("children", 0) or 0) > 0
    pace = (args.preferences or {}).get("pace", "normal").lower()
    model = args.model or OPENAI_MODEL_DEFAULT

    # Collect user-provided cities
    given_cities_set = set()
    given_city_country: Dict[str, Optional[str]] = {}
    for c in (args.countries or []):
        cn = c.norm_country
        for city in (c.cities or []):
            name = _clean_city_name(city)
            if not name:
                continue
            given_cities_set.add(name)
            if cn:
                given_city_country[name] = cn
    for city in (args.preferred_cities or []):
        name = _clean_city_name(city)
        if not name:
            continue
        given_cities_set.add(name)
        given_city_country.setdefault(name, None)
    given_cities = sorted(given_cities_set)

    # Decide recommended count C
    if args.dates and args.dates.get("start") and args.dates.get("end"):
        tripdays = _trip_days(args.dates["start"], args.dates["end"])
        provisional_C = max(1, min(20, math.ceil(tripdays / PACE_TO_DAYS.get(pace, 3.0))))
    else:
        tripdays = None
        provisional_C = args.default_recommend_count

    # Search (ULTRA-FAST) → LLM per country
    rows: List[Dict[str, Any]] = []
    per_country_stats: Dict[str, Dict[str,int]] = {}

    for country in countries:
        results, answer = _search_minimal_for_country(tv, country, with_kids)
        seeds = [r["url"] for r in results]
        if not (answer or results):
            logs.append(f"City_Recommender[{country}]: empty search (answer/results)")
            per_country_stats[country] = _Stats(seeds=0, pages=0, extracted=0, kept=0)
            continue

        given_for_country = [gc for gc in given_cities if (given_city_country.get(gc) in (None, country))]
        prompt, sources_used = _build_city_prompt_from_snippets(
            country=country,
            with_kids=with_kids,
            answer_text=answer,
            results=results,
            given_cities=given_for_country,
            musts=args.musts,
            preferred=args.preferred_cities,
        )
        data = _extract_cities_with_llm(ocli, model, prompt)
        raw = (data or {}).get("cities") or []

        kept = 0
        seen = set()
        for item in raw:
            name = _clean_city_name(item.get("name") or "")
            if not name:
                continue
            kl = (name.lower(), country.lower())
            if kl in seen:
                continue
            seen.add(kl)
            rows.append({
                "name": name,
                "country": country,
                "is_capital": item.get("is_capital") if isinstance(item.get("is_capital"), bool) else None,
                "family_hint": item.get("family_hint") if isinstance(item.get("family_hint"), bool) else None,
                "evidence_urls": [u for u in (item.get("evidence_urls") or []) if isinstance(u, str) and u.strip()],
                "sources_seed": seeds[:],
            })
            kept += 1

        # Ensure user-provided cities present
        for gc in given_for_country:
            if not any(r["name"].lower() == gc.lower() and r["country"].lower() == country.lower() for r in rows):
                rows.append({
                    "name": gc,
                    "country": country,
                    "is_capital": None,
                    "family_hint": None,
                    "evidence_urls": [],
                    "sources_seed": seeds[:],
                })
                kept += 1

        per_country_stats[country] = _Stats(seeds=len(seeds), pages=len(results), extracted=len(raw), kept=kept)
        logs.append(
            f"City_Recommender[{country}]: 1 search call, answer={bool(answer)}, snippet_urls={len(results)}, kept={kept}"
        )

    if not rows:
        raise RuntimeError("No cities found for the given countries. Try different inputs.")

    # Score & rank
    for r in rows:
        r["score"] = _score_city(r, with_kids, args.musts, args.preferred_cities)
    rows.sort(key=lambda r: (-r["score"], r["country"], r["name"]))

    # Decide final C
    must_cities = [r["name"] for r in rows if any(r["name"].lower() == m.lower() or r["name"].lower() in m.lower() for m in args.musts)]
    if tripdays is not None:
        C = _recommend_city_count(tripdays, pace, len(must_cities))
    else:
        C = max(provisional_C, len(must_cities))

    picked: List[str] = []
    city_country_map: Dict[str, str] = {}

    # A) include musts first (respect ranking)
    for r in rows:
        if r["name"] in must_cities and r["name"] not in picked:
            picked.append(r["name"]); city_country_map[r["name"]] = r["country"]
        if len(picked) >= C:
            break

    # B) ensure coverage for multi-country
    if len(countries) > 1 and len(picked) < C:
        covered = {city_country_map[c] for c in picked}
        for country in countries:
            if country in covered:
                continue
            for r in rows:
                if r["country"] == country and r["name"] not in picked:
                    picked.append(r["name"]); city_country_map[r["name"]] = r["country"]
                    break
            if len(picked) >= C:
                break

    # C) fill remaining by global rank
    if len(picked) < C:
        for r in rows:
            if r["name"] not in picked:
                picked.append(r["name"]); city_country_map[r["name"]] = r["country"]
            if len(picked) >= C:
                break

    # Candidates payload
    cand_payload: List[CityCandidate] = []
    with_kids_flag = with_kids
    for r in rows[: min(args.max_candidates, len(rows))]:
        base = {
            "city": r["name"],
            "country": r["country"],
            "score": round(float(r["score"]), 2),
            "sources": list(dict.fromkeys((r.get("evidence_urls") or []) + (r.get("sources_seed") or []))),
        }
        if with_kids_flag:
            base["family_hits"] = 1 if r.get("family_hint") else 0
        cand_payload.append(CityCandidate(**base))

    return CityRecommenderResult(
        cities=picked,
        city_country_map=city_country_map,
        recommended_city_count=C,
        city_candidates=cand_payload,
        stats=per_country_stats,
        logs=logs,
    )


# ======================= Back-compat wrapper =======================
def run_city_recommender_as_state(state: AppState) -> AppState:
    req = state.request
    logs = state.logs or []
    state.meta = state.meta or {}
    try:
        args = CityRecommenderArgs(
            countries=[CountryArg(**(c if isinstance(c, dict) else {"country": c}))
                       for c in (req.get("countries") or [])],
            dates=req.get("dates"),
            travelers=req.get("travelers") or {"adults":1,"children":0},
            musts=req.get("musts") or [],
            preferred_cities=req.get("preferred_cities") or [],
            preferences=req.get("preferences") or {},
            default_recommend_count=int(req.get("default_recommend_count", 5)),
            max_candidates=int(req.get("max_candidates", 12)),
            model=req.get("openai_model") or None,
        )
    except ValidationError as e:
        state.meta["requires_input"] = {"field": "args", "message": f"validation error: {e}"}
        return state

    try:
        out = city_recommender_tool(args)
    except Exception as e:
        state.meta["requires_input"] = {"field": "runtime", "message": str(e)}
        return state

    req["cities"] = out.cities
    req["city_country_map"] = out.city_country_map
    req["recommended_city_count"] = out.recommended_city_count
    req["city_candidates"] = [c.model_dump() for c in out.city_candidates]

    logs.extend(out.logs)
    req.setdefault("stats", {})["city_recommender"] = out.stats

    state.request, state.logs = req, logs
    return state


# ======================= OpenAI tool schema (optional) =======================
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "city_recommender_tool",
        "description": "Recommend trip-friendly cities for one or more countries. ULTRA-FAST: one Tavily search per country (answer + up to two snippets), then LLM.",
        "parameters": {
            "type": "object",
            "properties": {
                "countries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string"},
                            "name": {"type": "string"},
                            "cities": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "dates": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "YYYY-MM-DD"},
                        "end": {"type": "string", "description": "YYYY-MM-DD"}
                    },
                    "additionalProperties": False
                },
                "travelers": {
                    "type": "object",
                    "properties": {"adults": {"type": "integer"}, "children": {"type": "integer"}},
                    "additionalProperties": False
                },
                "musts": {"type": "array", "items": {"type": "string"}},
                "preferred_cities": {"type": "array", "items": {"type": "string"}},
                "preferences": {"type": "object"},
                "default_recommend_count": {"type": "integer"},
                "max_candidates": {"type": "integer"},
                "model": {"type": "string"}
            },
            "required": ["countries"]
        }
    }
}


if __name__ == "__main__":
    """
    Quick manual test runner for city_recommender_tool (search-only version).
    Requires:
      export TAVILY_API_KEY=...
      export OPENAI_API_KEY=...
    """
    import sys
    import time

    def _print_result(title: str, res: CityRecommenderResult, started: float):
        took = time.time() - started
        print(f"\n===== {title} =====")
        print(f"took: {took:.2f}s")
        print("\nTop picks:")
        for i, c in enumerate(res.cities, 1):
            cc = res.city_country_map.get(c, "?")
            print(f"  {i:>2}. {c}  —  {cc}")

        # Show a few candidates with scores and 1–2 sources
        print("\nCandidates (first 10):")
        for cand in res.city_candidates[:10]:
            srcs = (cand.sources or [])[:2]
            print(f"  • {cand.city:20s} | {cand.country:12s} | score={cand.score:.2f} | srcs={len(cand.sources)}")
            for s in srcs:
                print(f"      - {s}")

        # Per-country stats summary
        if res.stats:
            print("\nStats:")
            for country, st in res.stats.items():
                print(f"  {country}: {st}")

        # Optional logs (first few)
        if res.logs:
            print("\nLogs (first 8):")
            for ln in res.logs[:8]:
                print("  ", ln)

    tests = [
        {
            "title": "Japan (kids, normal pace, 7 days)",
            "args": CityRecommenderArgs(
                countries=[CountryArg(country="Japan", cities=["Tokyo", "Kyoto"])],
                dates={"start": "2025-10-05", "end": "2025-10-11"},
                travelers={"adults": 2, "children": 1},
                musts=["Tokyo"],
                preferred_cities=["Osaka"],
                preferences={"pace": "normal"},
                model=OPENAI_MODEL_DEFAULT,
            ),
        },
        {
            "title": "Italy + Spain (adults only, fast pace, 9 days)",
            "args": CityRecommenderArgs(
                countries=[CountryArg(country="Italy"), CountryArg(country="Spain")],
                dates={"start": "2025-05-10", "end": "2025-05-18"},
                travelers={"adults": 2, "children": 0},
                musts=["Rome"],
                preferred_cities=["Seville", "Florence"],
                preferences={"pace": "fast"},
                model=OPENAI_MODEL_DEFAULT,
            ),
        },
    ]

    for t in tests:
        t0 = time.time()
        try:
            out = city_recommender_tool(t["args"])
            _print_result(t["title"], out, t0)
        except Exception as e:
            print(f"\n===== {t['title']} =====")
            print("Error:", e)
            sys.exit(1)

