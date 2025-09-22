"""
POI Discovery Tool for TripPlanner Multi-Agent System

This tool discovers Points of Interest (POIs) such as attractions, landmarks,
museums, and activities in specified cities. It uses web search and AI to find
comprehensive lists of must-see and recommended attractions.

Key features:
- POI discovery using web search and AI analysis
- Must-see attraction identification and prioritization
- Category-based POI classification and filtering
- Parallel processing for multiple cities
- AI-powered content extraction and structuring

The tool ensures comprehensive attraction discovery, providing users with
detailed information about things to see and do in their chosen destinations.
"""

from __future__ import annotations

import os, re, json, textwrap, time
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

# External deps
from tavily import TavilyClient
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # optional

# ============================ Global speed knobs (ENV) ============================
# Tavily usage stays minimal: exactly ONE general search per city; NO extract calls.
POI_SEARCH_DEPTH       = "basic"
POI_INCLUDE_RAW        = False
POI_QUERY_WORKERS      = 1
POI_CITY_WORKERS       = 4  # parallelize across cities safely

# Extra micro-searches for MUST POIs (tight budget)
POI_MUST_SEARCHES_PER_CITY_MAX = int(os.getenv("POI_MUST_SEARCHES_PER_CITY_MAX", "4"))
POI_MUST_RESULTS_PER_QUERY     = int(os.getenv("POI_MUST_RESULTS_PER_QUERY", "1"))

# ---------------- Config (target ~15 POIs/city) ----------------
DEFAULT_POI_TARGET_PER_CITY = 15

# Keep Tavily usage tiny:
DEFAULT_MAX_SEED_RESULTS_PER_QUERY = 6   # we’ll keep only top 2 after official-first sort
DEFAULT_MAX_SEED_QUERIES_PER_CITY  = 1   # single query per city
DEFAULT_MAX_PAGES_PER_CITY         = 0   # no extract pages (kept for compatibility)

# LLM context budgeting (applies to answer+snippets only)
DEFAULT_MAX_CHARS_PER_PAGE       = int(os.getenv("POI_MAX_CHARS_PER_PAGE", "8000"))
DEFAULT_MAX_TOTAL_CHARS_PER_CITY = int(os.getenv("POI_MAX_TOTAL_CHARS", "16000"))
DEFAULT_MIN_KEEP_PER_PAGE        = int(os.getenv("POI_MIN_KEEP_PER_PAGE", "800"))

OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = 0.0

OFFICIAL_HINTS = (".gov", ".gouv.", ".edu", ".museum", "tourism", "visit", "comune.", "city.", "go.jp", ".govt")

# ---------------- Pydantic Schemas ----------------
class PriceOut(BaseModel):
    adult: Optional[float] = None
    child: Optional[float] = None
    currency: Optional[str] = None  # keep native currency if present

class CoordsOut(BaseModel):
    lat: float
    lon: float

class POIOut(BaseModel):
    city: str
    name: str
    category: Optional[str] = None
    official_url: Optional[str] = None
    other_urls: Optional[List[str]] = None
    hours: Optional[Dict[str, Optional[str]]] = None  # {"Mon":"09:00–18:00"|None, ...}
    price: Optional[PriceOut] = None                  # None OR {adult, child, currency}
    coords: Optional[CoordsOut] = None
    source_urls: Optional[List[str]] = None
    source_note: Optional[str] = None
    score: float = 0.0

class POICityResult(BaseModel):
    pois: List[POIOut] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

class POIDiscoveryArgs(BaseModel):
    cities: List[str]
    city_country_map: Dict[str, str]
    poi_target_per_city: int = DEFAULT_POI_TARGET_PER_CITY

    # Kids preference (either supply this directly or via travelers)
    with_kids: Optional[bool] = None
    travelers: Optional[Dict[str, int]] = None  # e.g., {"adults":2,"children":1}

    # Carry interpreter/user context to the LLM so nothing is lost
    musts: List[str] = Field(default_factory=list)            # exact/near POI names to include if possible
    preferences: Dict[str, Any] = Field(default_factory=dict) # themes, budget_tier/price_tier, month_hint/date_hint, accessibility, avoid, language, pace, etc.

    # Budgets/tunables (kept for API compatibility)
    max_seed_results_per_query: int = DEFAULT_MAX_SEED_RESULTS_PER_QUERY
    max_seed_queries_per_city: int  = DEFAULT_MAX_SEED_QUERIES_PER_CITY
    max_pages_per_city: int         = DEFAULT_MAX_PAGES_PER_CITY
    max_chars_per_page: int         = DEFAULT_MAX_CHARS_PER_PAGE
    max_total_chars_per_city: int   = DEFAULT_MAX_TOTAL_CHARS_PER_CITY
    min_keep_per_page: int          = DEFAULT_MIN_KEEP_PER_PAGE

    # LLM options
    model: Optional[str] = None
    use_llm: Optional[bool] = None  # default: True iff OPENAI_API_KEY present

class POIDiscoveryResult(BaseModel):
    poi_by_city: Dict[str, POICityResult] = Field(default_factory=dict)
    poi_flat: List[POIOut] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)

# ---------------- Simple in-process cache ----------------
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}

# ---------------- Internal helpers ----------------
def _tavily() -> TavilyClient:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)

def _openai_or_none() -> Optional[OpenAI]:
    if OpenAI is None:
        return None
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None

def _is_official(url: Optional[str]) -> bool:
    if not url: return False
    low = url.lower()
    return any(h in low for h in OFFICIAL_HINTS)

def _sort_urls_official_first(urls: List[str]) -> List[str]:
    # Stable: official first, then alphabetical for determinism
    return sorted(dict.fromkeys(urls), key=lambda u: (0 if _is_official(u) else 1, u))

_WS = re.compile(r"\s+")
def _squeeze_ws(s: str) -> str:
    return _WS.sub(" ", (s or "")).strip()

def _trim_text(text: str, per_page_limit: int, min_keep: int) -> str:
    lines = (text or "").splitlines()
    bullets = [ln for ln in lines if ln.strip().startswith(("#","-","*","•"))]
    head = "\n".join(bullets[:60])  # cap bullet count
    body = "\n".join(lines)[:max(per_page_limit, min_keep)]
    merged = (head + "\n\n" + body) if head else body
    merged = _squeeze_ws(merged)
    return merged[:max(per_page_limit, min_keep)]

def _cap_total_chunks(chunks: List[Tuple[str,str]], total_cap: int, min_keep: int) -> List[Tuple[str,str]]:
    if not chunks:
        return chunks
    total = sum(len(t) for _, t in chunks)
    if total <= total_cap:
        return chunks
    ratio = max(0.05, float(total_cap) / float(total))
    trimmed: List[Tuple[str,str]] = []
    for (u, t) in chunks:
        allow = max(min_keep, int(len(t) * ratio))
        trimmed.append((u, t[:allow]))
    return trimmed

# ---------------- Normalizers (FX-ready, no conversion) ----------------
_DAYS = ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")
_NUM_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)")

def _to_float_or_none(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None

def _canon_price(obj: Any) -> Optional[PriceOut]:
    """Return {adult, child, currency} with None where missing; NO FX conversion."""
    if not isinstance(obj, dict):
        return None
    adult = _to_float_or_none(obj.get("adult"))
    child = _to_float_or_none(obj.get("child"))
    cur = obj.get("currency")
    currency = None
    if isinstance(cur, str) and cur.strip():
        c = cur.strip().upper()
        currency = c[:3] if 2 < len(c) <= 4 else c
    if adult is None and child is None and currency is None:
        return None
    return PriceOut(adult=adult, child=child, currency=currency)

def _canon_hours(obj: Any) -> Optional[Dict[str, Optional[str]]]:
    if not isinstance(obj, dict):
        return None
    out: Dict[str, Optional[str]] = {}
    for d in _DAYS:
        v = obj.get(d)
        out[d] = (str(v).strip() if isinstance(v, str) and v.strip() else None)
    if all(v is None for v in out.values()):
        return None
    return out

def _canon_coords(obj: Any) -> Optional[CoordsOut]:
    if not isinstance(obj, dict):
        return None
    lat = _to_float_or_none(obj.get("lat"))
    lon = _to_float_or_none(obj.get("lon")) or _to_float_or_none(obj.get("lng"))
    if lat is None or lon is None:
        return None
    return CoordsOut(lat=lat, lon=lon)

# ---------------- Minimal Tavily search (no extract) ----------------
def _build_locale_query_suffix(language: Optional[str]) -> str:
    if language and isinstance(language, str) and len(language) <= 5:
        return f" (prefer {language} official sources)"
    return ""

def _search_minimal(tv: TavilyClient, city: str, country: str, with_kids: bool,
                    rmax: int, language: Optional[str]) -> Tuple[List[str], Optional[str], Dict[str, str]]:
    """
    Returns (top_urls[:2], answer_text, snippets_by_url).
    Exactly one Tavily search call; no extract.
    """
    kid = " with kids" if with_kids else ""
    qlang = _build_locale_query_suffix(language)
    query = f"top attractions{kid} in {city}, {country}{qlang}. Prefer official tourism websites."

    if query in _SEARCH_CACHE:
        sr = _SEARCH_CACHE[query]
    else:
        sr = tv.search(
            query,
            include_answer=True,
            max_results=rmax,
            search_depth=POI_SEARCH_DEPTH,
            include_raw_content=False,
            include_domains=[
                "visit", "tourism", ".gov", ".gouv.", ".go.jp", ".museum", ".edu", "city."
            ],
        ) or {}
        _SEARCH_CACHE[query] = sr

    results = (sr.get("results") or [])
    urls: List[str] = []
    snippets: Dict[str, str] = {}
    for r in results:
        u = (r.get("url") or "").strip()
        if not u:
            continue
        urls.append(u)
        snip = (r.get("content") or r.get("title") or "").strip()
        if snip:
            snippets[u] = snip[:400]  # keep tiny

    urls = _sort_urls_official_first(urls)[:2]  # <= TWO URLs ONLY
    return urls, (sr.get("answer") or None), {u: snippets.get(u, "") for u in urls}

# ---------------- Minimal per-must search (no extract) ----------------
def _search_must_one(
    tv: TavilyClient,
    city: str,
    country: str,
    poi_name: str,
    language: Optional[str],
    rmax: int = POI_MUST_RESULTS_PER_QUERY,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (top_url_or_none, snippet_or_empty). Exactly one search per must, 1 result.
    """
    qlang = _build_locale_query_suffix(language)
    # steer to official pages first if possible
    query = f'official site or tourism page for "{poi_name}" in {city}, {country}{qlang}'
    if query in _SEARCH_CACHE:
        sr = _SEARCH_CACHE[query]
    else:
        sr = tv.search(
            query,
            include_answer=False,
            max_results=max(1, rmax),
            search_depth="basic",
            include_raw_content=False,
            include_domains=["visit", "tourism", ".gov", ".gouv.", ".go.jp", ".museum", ".edu", "city."],
        ) or {}
        _SEARCH_CACHE[query] = sr
    results = (sr.get("results") or [])
    if not results:
        return None, None
    r0 = results[0]
    return (r0.get("url") or None), ((r0.get("content") or r0.get("title") or "")[:400] or None)

# ---------------- LLM prompt & call (answer + snippets only) ----------------
def _build_snippet_prompt(
    city: str,
    country: str,
    with_kids: bool,
    answer_text: Optional[str],
    url_snippets: Dict[str, str],
    target_n: int,
    travelers: Optional[Dict[str,int]],
    musts: List[str],
    preferences: Dict[str, Any],
    per_page_limit: int,
    min_keep: int,
    total_cap: int,
) -> Tuple[str, List[Tuple[str,str]]]:
    adults = int((travelers or {}).get("adults", 1) or 1)
    children = int((travelers or {}).get("children", 0) or 0)

    themes = preferences.get("themes", []) or []
    month_hint = preferences.get("month_hint") or preferences.get("date_hint")
    budget_tier = preferences.get("budget_tier") or preferences.get("price_tier")
    accessibility = preferences.get("accessibility")
    avoid = preferences.get("avoid") or []
    pace = preferences.get("pace")

    header = f"""
Extract Points of Interest (POIs) for {city}, {country} from the short notes below.
Return STRICT JSON ONLY:
{{
  "poi": [
    {{
      "name": "...",
      "category": "...",
      "official_url": "...",
      "other_urls": ["..."],
      "hours": {{"Mon":"HH:MM–HH:MM"|null, "Tue":..., "Wed":..., "Thu":..., "Fri":..., "Sat":..., "Sun":...}},
      "price": {{"adult": number|null, "child": number|null, "currency": "ISO3"|null}},
      "coords": {{"lat": number|null, "lon": number|null}}
    }}
  ]
}}
Hard rules:
- Output at most {min(18, max(12, target_n+2))} items.
- Prefer OFFICIAL websites (.gov, .museum, .edu, 'tourism'/'visit', city.*) when present.
- If hours/price/coords are absent in notes, set null. Do NOT invent or browse.
- Keep native currency; do NOT convert.
Context:
- Travelers: adults={adults}, children={children}; {"include kid-friendly options" if with_kids or children>0 else "prioritize iconic/essential sights"}.
- Themes: {themes if themes else "none"}.
- Budget: {budget_tier if budget_tier else "unspecified"}.
- Season/Month hint: {month_hint if month_hint else "none"}.
- Accessibility: {accessibility if accessibility else "none"}.
- Avoid: {avoid if avoid else "none"}.
- Pace: {pace if pace else "normal"}.
- MUST-INCLUDE if visible (exact/near names): {musts if musts else "[]"}.
"""

    chunks: List[Tuple[str,str]] = []
    if answer_text:
        chunks.append(("tavily:search:answer", _trim_text(answer_text, per_page_limit, min_keep)))
    for u, snip in url_snippets.items():
        if snip:
            chunks.append((u, _trim_text(snip, per_page_limit, min_keep)))

    chunks = _cap_total_chunks(chunks, total_cap, min_keep)

    parts = []
    for (u, t) in chunks:
        parts.append(f"[SOURCE] {u}\n[TEXT] {t}\n")

    prompt = textwrap.dedent(header + "\n" + "\n".join(parts))
    return prompt, chunks

def _extract_with_llm(ocli: OpenAI, model: str, prompt: str) -> Dict[str, Any]:
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
        return json.loads(m.group(0)) if m else {"poi":[]}

# ---------------- Rank & trim (to ~target) ----------------
def _rank_and_trim(with_kids: bool, rows: List[POIOut], target_n: int,
                   musts: Optional[List[str]] = None,
                   preferences: Optional[Dict[str, Any]] = None) -> List[POIOut]:
    musts = [m.lower() for m in (musts or [])]
    budget = (preferences or {}).get("budget_tier") or (preferences or {}).get("price_tier")
    accessibility = (preferences or {}).get("accessibility") or {}
    avoid = set([(a or "").lower() for a in ((preferences or {}).get("avoid") or [])])

    def score(p: POIOut) -> float:
        s = 0.0
        nm = (p.name or "").lower()
        cat = (p.category or "").lower()
        if any(m in nm for m in musts): s += 0.60  # strong boost for musts
        if _is_official(p.official_url): s += 0.35
        if with_kids and cat in (
            "zoo", "aquarium", "park", "garden", "science museum", "theme park", "interactive museum"
        ): s += 0.15
        if p.hours: s += 0.05
        if p.price and (p.price.adult is not None): s += 0.05
        if p.coords: s += 0.02
        if budget == "budget" and (p.price and ((p.price.adult or 0) <= 15)): s += 0.05
        if accessibility.get("wheelchair"): s += 0.02
        if cat in avoid: s -= 0.05
        return s

    scored = [(round(score(p),3), p) for p in rows]
    scored.sort(key=lambda t: (-t[0], (t[1].category or "zzz"), t[1].name))
    out = []
    for sc, p in scored:
        p.score = sc
        out.append(p)
        if len(out) >= max(1, target_n):
            break
    return out

# ---------------- Main Tool (LLM-only from search) ----------------
def poi_discovery_tool(args: POIDiscoveryArgs) -> POIDiscoveryResult:
    logs: List[str] = []
    errors: List[Dict[str, str]] = []
    result_by_city: Dict[str, POICityResult] = {}
    flat: List[POIOut] = []

    # Clients
    try:
        tv = _tavily()
    except Exception as e:
        errors.append({"stage": "init", "message": str(e)})
        return POIDiscoveryResult(poi_by_city={}, poi_flat=[], logs=logs, errors=errors)

    ocli = _openai_or_none()
    use_llm = args.use_llm if args.use_llm is not None else (ocli is not None)
    model = (args.model or OPENAI_MODEL_DEFAULT)

    # with_kids logic
    with_kids = bool(args.with_kids)
    if args.with_kids is None and args.travelers:
        try:
            with_kids = int(args.travelers.get("children", 0) or 0) > 0
        except Exception:
            with_kids = False

    language = None
    if isinstance(args.preferences, dict):
        language = args.preferences.get("language")

    cities = list(args.cities or [])
    city_country = dict(args.city_country_map or {})
    if not cities:
        errors.append({"stage":"input","message":"cities is required"})
        return POIDiscoveryResult(poi_by_city={}, poi_flat=[], logs=logs, errors=errors)

    def _process_city(city: str) -> Tuple[str, POICityResult]:
        country = city_country.get(city, "")

        # 1) Exactly one general search; maybe use the answer directly + up to 2 snippets
        urls, answer, snippets = _search_minimal(
            tv, city, country, with_kids,
            args.max_seed_results_per_query,
            language
        )

        # 1b) Minimal per-must searches (tight cap) to ensure we have sources for asked-for POIs
        must_list = [m for m in (args.musts or []) if isinstance(m, str) and m.strip()]
        must_hits = 0
        if must_list and POI_MUST_SEARCHES_PER_CITY_MAX > 0:
            for poi_name in must_list:
                if must_hits >= POI_MUST_SEARCHES_PER_CITY_MAX:
                    break
                try:
                    mu, msnip = _search_must_one(tv, city, country, poi_name.strip(), language)
                except Exception:
                    mu, msnip = None, None
                if mu:
                    # Avoid duplicates, keep official-first behavior later
                    if mu not in urls:
                        urls.append(mu)
                    # Merge into snippets for prompt construction
                    if msnip and mu not in snippets:
                        snippets[mu] = msnip
                    must_hits += 1

        if not (use_llm and ocli):
            logs.append(f"POI_Discovery[{city}]: LLM unavailable/disabled; sources={len(urls)}")
            return city, POICityResult(pois=[], sources=urls)

        if not answer and not any(snippets.values()):
            logs.append(f"POI_Discovery[{city}]: no answer/snippets; sources={len(urls)}")
            return city, POICityResult(pois=[], sources=urls)

        # 2) Build the tiny prompt from answer + snippets (no extract pages)
        prompt, chunks = _build_snippet_prompt(
            city, country, with_kids, answer, snippets,
            args.poi_target_per_city, args.travelers, args.musts, args.preferences,
            args.max_chars_per_page, args.min_keep_per_page, args.max_total_chars_per_city
        )

        # 3) LLM JSON extract
        try:
            data = _extract_with_llm(ocli, model, prompt)
        except Exception as e:
            logs.append(f"POI_Discovery[{city}]: LLM error {e}")
            return city, POICityResult(pois=[], sources=urls)

        raw = (data or {}).get("poi") or []
        # prefer URLs that actually made it into the prompt chunks; fall back to merged url list
        base_sources = _sort_urls_official_first([u for (u, _) in chunks if isinstance(u, str) and u.startswith("http")] or urls)

        rows: List[POIOut] = []
        for item in raw:
            name = (item.get("name") or "").strip()
            if not name:
                continue

            hours  = _canon_hours(item.get("hours"))
            price  = _canon_price(item.get("price"))
            coords = _canon_coords(item.get("coords"))

            other = item.get("other_urls") or []
            merged_sources = _sort_urls_official_first([*base_sources, *other])[:2]  # cap to 2

            rows.append(POIOut(
                city=city,
                name=name[:150],
                category=item.get("category") or None,
                official_url=item.get("official_url") or None,
                other_urls=(other if other else None),
                hours=hours,
                price=price,
                coords=coords,
                source_urls=merged_sources,
                source_note="tavily:search(answer+snippets)",
            ))

        kept = _rank_and_trim(with_kids, rows, args.poi_target_per_city, args.musts, args.preferences)
        logs.append(f"POI_Discovery[{city}]: 1 general search + {must_hits} must-searches, used_answer={bool(answer)}, snippet_urls={len(base_sources)}, kept={len(kept)}")
        return city, POICityResult(pois=kept, sources=base_sources or urls)

    max_workers_cities = min(POI_CITY_WORKERS, len(cities) or 1)
    with ThreadPoolExecutor(max_workers=max_workers_cities) as pool:
        futures = {pool.submit(_process_city, city): city for city in cities}
        for fut in as_completed(futures):
            city, payload = fut.result()
            result_by_city[city] = payload
            flat.extend(payload.pois or [])

    return POIDiscoveryResult(poi_by_city=result_by_city, poi_flat=flat, logs=logs, errors=errors)

# ---------------- OpenAI tool schema (optional) ----------------
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "poi_discovery_tool",
        "description": "Discover POIs for cities via a single Tavily Search (answer+snippets) + one OpenAI JSON extract. Adds up to a few micro-searches for explicit MUST POIs. Returns native-currency prices when present; missing fields remain None. No Tavily Extract calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "cities": {"type":"array","items":{"type":"string"}},
                "city_country_map": {"type":"object","additionalProperties":{"type":"string"}},
                "poi_target_per_city": {"type":"integer","minimum":1,"maximum":40},
                "with_kids": {"type":"boolean"},
                "travelers": {"type":"object","additionalProperties":{"type":"integer"}},
                "musts": {"type":"array","items":{"type":"string"}},
                "preferences": {"type":"object","additionalProperties": True},
                "max_seed_results_per_query": {"type":"integer","minimum":2,"maximum":20},
                "max_seed_queries_per_city": {"type":"integer","minimum":1,"maximum":1},   # fixed to 1 internally
                "max_pages_per_city": {"type":"integer","minimum":0,"maximum":0},         # no extracts
                "max_chars_per_page": {"type":"integer","minimum":500,"maximum":50000},
                "max_total_chars_per_city": {"type":"integer","minimum":2000,"maximum":200000},
                "min_keep_per_page": {"type":"integer","minimum":200,"maximum":20000},
                "model": {"type":"string"},
                "use_llm": {"type":"boolean"}
            },
            "required": ["cities","city_country_map"]
        }
    }
}

# ============================ CLI tests ============================
def _pp_price(p: Optional[PriceOut]) -> str:
    if not p: return "—"
    bits = []
    if p.adult is not None: bits.append(f"adult={p.adult}")
    if p.child is not None: bits.append(f"child={p.child}")
    if p.currency: bits.append(p.currency)
    return " ".join(bits) if bits else "—"

def _print_sample(city: str, res: POICityResult, k: int = 5):
    print(f"\n  {city}: {len(res.pois)} POIs  |  sources: {len(res.sources)}")
    for poi in res.pois[:k]:
        print(f"   • {poi.name} [{poi.category or 'misc'}] | price: {_pp_price(poi.price)} | official: {poi.official_url or '—'}")

if __name__ == "__main__":
    # Minimal usage: ONE Tavily search per city; optional micro-searches for musts; no extracts; LLM does the rest.
    tests = [
        {
            "name": "Tokyo (kids & museums bias)",
            "args": POIDiscoveryArgs(
                cities=["Tokyo"],
                city_country_map={"Tokyo":"Japan"},
                poi_target_per_city=15,
                travelers={"adults":2, "children":1},
                preferences={"themes":["museums","parks"], "language":"en", "budget_tier":"budget"},
                musts=["Tokyo Skytree","Ueno Zoo","teamLab Borderless"],
            ),
        },
        {
            "name": "Rome + Florence (adult iconic)",
            "args": POIDiscoveryArgs(
                cities=["Rome","Florence"],
                city_country_map={"Rome":"Italy","Florence":"Italy"},
                preferences={"themes":["history","landmarks"], "language":"en"},
                musts=["Colosseum","Vatican Museums","Uffizi"],
            ),
        },
    ]

    for t in tests:
        t0 = time.time()
        out = poi_discovery_tool(t["args"])
        took = time.time() - t0
        print(f"\n===== {t['name']} =====")
        print(f"took: {took:.2f}s")
        if out.errors: print("errors:", out.errors)
        for city, res in out.poi_by_city.items():
            _print_sample(city, res, k=7)
        if out.logs:
            print("\n  logs:")
            for ln in out.logs[:6]:
                print("   ", ln)
