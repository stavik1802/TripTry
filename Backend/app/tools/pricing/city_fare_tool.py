"""
City Fare Tool for TripPlanner Multi-Agent System

This tool discovers and calculates local transportation costs within cities,
including public transport, taxis, rideshares, and other local transit options.
It provides comprehensive fare information for budget planning.

Key features:
- Local transportation cost discovery using web search
- Multi-modal transportation options (bus, metro, taxi, rideshare)
- Parallel processing for multiple cities and transportation modes
- AI-powered data extraction and cost estimation
- Configurable search parameters for speed optimization

The tool ensures accurate local transportation cost estimates, enabling
realistic budget planning for daily travel within destinations.
"""

from __future__ import annotations

import os, re, json, textwrap, time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

# External deps
from tavily import TavilyClient
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # optional (LLM extraction if available)

# ---------- Config (tunable via ENV) ----------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Keep these small — biggest speed wins are here:
MAX_SEARCH_RESULTS = int(os.getenv("FARES_MAX_SEARCH_RESULTS", "5"))
MAX_URLS_PER_CITY  = int(os.getenv("FARES_MAX_URLS_PER_CITY", "4"))
MAX_QUERY_VARIANTS = int(os.getenv("FARES_MAX_QUERY_VARIANTS", "4"))

# Extraction budget
EXTRACT_DEPTH   = os.getenv("FARES_EXTRACT_DEPTH", "basic")  # "basic" is faster; set "advanced" if needed
EXTRACT_FORMAT  = os.getenv("FARES_EXTRACT_FORMAT", "markdown")
EXTRACT_TIMEOUT = int(os.getenv("FARES_EXTRACT_TIMEOUT", "18"))  # seconds

# LLM input trimming
MAX_DOC_CHARS   = int(os.getenv("FARES_MAX_DOC_CHARS", "3000"))   # per doc
MAX_TOTAL_CHARS = int(os.getenv("FARES_MAX_TOTAL_CHARS", "16000"))  # per city

# Parallelism
MAX_EXTRACT_WORKERS = int(os.getenv("FARES_MAX_EXTRACT_WORKERS", "4"))
MAX_CITY_WORKERS    = int(os.getenv("FARES_MAX_CITY_WORKERS", "6"))

# Search depth for Tavily.search (basic is faster)
SEARCH_DEPTH = os.getenv("FARES_SEARCH_DEPTH", "basic")  # "basic" or "advanced"

OFFICIAL_HINTS = (
    ".gov", ".gouv.", ".go.jp", ".govt.", ".edu", ".museum",
    "/transport", "/transit", "/metro", "/mta", "/rta", "/cta", "/tfl",
    "city.", "comune.", "municipio", "muni", "pref.", "prefecture",
    "pt.", "publictransport", "verkehr", "verkehrsverbund", "tariff", "fare"
)

# Baseline queries (we’ll enrich based on preferences/musts)
TRANSIT_QUERIES = [
    "official public transport ticket prices in {city}, {country}",
    "single ticket price and day pass price {city} public transport",
    "metro bus tram fares {city} {country}",
]
TAXI_QUERIES = [
    "official taxi fares {city} {country} base fare per km per minute",
    "taxi tariff {city} {country} per km waiting time fare",
]

# ---------- Pydantic Schemas ----------
class MoneyOut(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    note: Optional[str] = None  # we preserve LLM notes (zones/child policy/etc.)

class TransitFaresOut(BaseModel):
    single: Optional[MoneyOut] = None
    day_pass: Optional[MoneyOut] = None
    weekly_pass: Optional[MoneyOut] = None
    sources: List[str] = Field(default_factory=list)

class TaxiFaresOut(BaseModel):
    base: Optional[float] = None
    per_km: Optional[float] = None
    per_min: Optional[float] = None
    currency: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    note: Optional[str] = None

class CityFaresCityResult(BaseModel):
    transit: Optional[TransitFaresOut] = None
    taxi: Optional[TaxiFaresOut] = None
    # Optional mirrors in target currency (only if FX hints provided & mappable)
    transit_target: Optional[Dict[str, Optional[Dict[str, Any]]]] = None
    taxi_target: Optional[Dict[str, Optional[float]]] = None

class CityFaresArgs(BaseModel):
    """Inputs to the City Fares discovery tool."""
    cities: List[str]
    city_country_map: Dict[str, str]

    # carry interpreter/user context through search & LLM
    preferences: Dict[str, Any] = Field(default_factory=dict)   # {"language":"en","kid_friendly":True,"pass_names":[...]}
    travelers: Optional[Dict[str, int]] = None                  # {"adults":2,"children":1}
    musts: List[str] = Field(default_factory=list)              # pass/tariff names to prioritize

    # Optional FX hints:
    fx_target: Optional[str] = None
    fx_to_target: Optional[Dict[str, float]] = None

    # Overrides/tunables:
    max_urls_per_city: int = Field(default=MAX_URLS_PER_CITY, ge=2, le=12)
    model: Optional[str] = None  # override OPENAI_MODEL
    use_llm: Optional[bool] = None  # default: True if OPENAI_API_KEY present

class CityFaresResult(BaseModel):
    city_fares: Dict[str, CityFaresCityResult] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)


# ---------- Helpers ----------
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

def _is_official(url: str) -> bool:
    u = (url or "").lower()
    return any(h in u for h in OFFICIAL_HINTS)

def _sort_urls_official_first(urls: List[str]) -> List[str]:
    # Stable: official first, then everything else
    return sorted(dict.fromkeys(urls), key=lambda u: (0 if _is_official(u) else 1, u))

def _first_text(ex: Any) -> Optional[str]:
    if isinstance(ex, dict):
        # prefer largest result snippet
        best = None
        for r in (ex.get("results") or []):
            cand = r.get("raw_content") or r.get("content") or r.get("markdown") or r.get("text")
            if cand and len(cand) > (len(best) if best else 0):
                best = cand
        if best:
            return best
        return ex.get("raw_content") or ex.get("content") or ex.get("markdown") or ex.get("text")
    elif isinstance(ex, list):
        for item in ex:
            if isinstance(item, dict):
                cand = item.get("raw_content") or item.get("content") or item.get("markdown") or item.get("text")
                if cand:
                    return cand
            elif isinstance(item, str) and item.strip():
                return item
    elif isinstance(ex, str) and ex.strip():
        return ex
    return None

def _extract_pages(tv: TavilyClient, urls: List[str], logs: List[str]) -> List[Tuple[str, str]]:
    out: List[Tuple[str,str]] = []

    def _extract_one(u: str) -> Optional[Tuple[str, str]]:
        try:
            ex = tv.extract(
                u,
                extract_depth=EXTRACT_DEPTH,
                format=EXTRACT_FORMAT,
                timeout=EXTRACT_TIMEOUT,
                include_images=False,
                include_favicon=False,
            ) or {}
        except Exception as e:
            logs.append(f"extract error {u}: {e}")
            return None

        text = (_first_text(ex) or "").strip()
        if not text:
            logs.append(f"extract empty {u}")
            return None

        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS]
        return (u, text)

    max_workers = min(MAX_EXTRACT_WORKERS, len(urls) or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_extract_one, u): u for u in urls}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                out.append(res)
    return out

def _clip(s: str, limit: int) -> str:
    s = s.strip()
    return s if len(s) <= limit else (s[:limit] + "\n…[truncated]")

def _enforce_total_budget(pages: List[Tuple[str,str]], total_limit: int) -> List[Tuple[str,str]]:
    """Greedy keep in order while staying under total character budget."""
    kept, used = [], 0
    for u, t in pages:
        if used + len(t) <= total_limit:
            kept.append((u, t)); used += len(t)
        else:
            remain = total_limit - used
            if remain > 500:
                kept.append((u, t[:remain]))
                used = total_limit
            break
    return kept

def _with_kids(travelers: Optional[Dict[str,int]], preferences: Dict[str,Any]) -> bool:
    if preferences.get("kid_friendly") is True:
        return True
    try:
        return int((travelers or {}).get("children", 0) or 0) > 0
    except Exception:
        return False

def _pref_language(preferences: Dict[str,Any]) -> Optional[str]:
    lang = preferences.get("language")
    if isinstance(lang, str) and len(lang) <= 5:
        return lang
    return None

def _lang_suffix(language: Optional[str]) -> str:
    return f" (prefer {language} official sources)" if language else ""

def _compose_queries(
    city: str,
    country: str,
    base_templates: List[str],
    preferences: Dict[str,Any],
    travelers: Optional[Dict[str,int]],
    musts: List[str],
    language: Optional[str],
    max_variants: int,
) -> List[str]:
    """Build enriched query variants from preferences/musts without exploding search volume."""
    out: List[str] = []
    qlang = _lang_suffix(language)

    tokens: List[str] = []
    if _with_kids(travelers, preferences):
        tokens += ["child fare", "youth fare"]
    pass_names = []
    if isinstance(preferences.get("pass_names"), list):
        pass_names += [str(x) for x in preferences["pass_names"] if str(x).strip()]
    pass_names += [m for m in musts if len(m.split()) <= 4]
    pass_names = list(dict.fromkeys(pass_names))[:3]
    tokens += pass_names

    focus = [t for t in ["day pass", "weekly pass", "zone 1", "central zone"]]
    tokens += focus

    for tpl in base_templates:
        q = tpl.format(city=city, country=country) + qlang
        out.append(q)

    if tokens:
        chunks = [
            " ".join(tokens[:3]).strip(),
            " ".join(tokens[3:6]).strip(),
        ]
        for ch in chunks:
            if not ch: continue
            out.append(f"public transport fares {city} {country} {ch}{qlang}")

    # uniq + cap
    seen, uniq = set(), []
    for q in out:
        if q not in seen:
            seen.add(q); uniq.append(q)
        if len(uniq) >= max_variants:
            break
    return uniq

# ---------- LLM extraction ----------
def _llm_extract_fares(
    oa: OpenAI,
    model: str,
    city: str,
    country: str,
    docs: List[Tuple[str,str]],
    preferences: Dict[str, Any],
    travelers: Optional[Dict[str,int]],
    musts: List[str],
) -> Dict[str, Any]:
    """
    Single LLM call. Returns JSON dict with transit & taxi fares + sources.
    """
    with_kids = _with_kids(travelers, preferences)
    language = _pref_language(preferences)
    month_hint = preferences.get("month_hint") or preferences.get("date_hint")
    pass_names = preferences.get("pass_names") or []
    if isinstance(pass_names, str): pass_names = [pass_names]

    schema_hint = textwrap.dedent("""
    Return STRICT JSON with this shape:
    {
      "city": "string",
      "country": "string",
      "transit": {
        "single": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null, "note": "string|null"},
        "day_pass": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null, "note": "string|null"},
        "weekly_pass": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null, "note": "string|null"},
        "sources": ["string", ...]
      },
      "taxi": {
        "base": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null},
        "per_km": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null},
        "per_min": {"amount": number|null, "currency": "ISO3"|null, "source": "url"|null},
        "sources": ["string", ...],
        "note": "string|null"
      }
    }
    Rules:
    - Prefer OFFICIAL sources (gov/city/transit authority). Use those pages for 'source'.
    - Report the most common ADULT base fares. If child/youth/senior policies appear, summarize in 'note'.
    - If a pass isn't offered, set amount=null and currency=null.
    - If multiple zones exist, use central/zone-1 when clearly stated; summarize zone coverage in 'note'.
    - Currency must be ISO 4217 uppercase. Reply with JSON only.
    """)

    guidance = textwrap.dedent(f"""
    Context hints (soft, do not fabricate):
    - Preferred source language: {language or "none"} (English OK if unclear)
    - Children present: {"yes" if with_kids else "no"}
    - Month/season hint: {month_hint or "none"}
    - Prioritize if present: {list(dict.fromkeys((pass_names or []) + (musts or [])))[:6]}
    """)

    parts = [f"City: {city}, Country: {country}\n", guidance, "\nSOURCES:"]
    for i, (u, _) in enumerate(docs, 1):
        parts.append(f"{i}. {u}")
    parts.append("\nEXCERPTS:\n")
    for i, (u, text) in enumerate(docs, 1):
        parts.append(f"--- Source {i}: {u} ---\n{_clip(text, MAX_DOC_CHARS)}\n")

    messages = [
        {"role": "system", "content": "You extract transit & taxi fares from official pages. Respond with strict JSON only."},
        {"role": "user", "content": schema_hint + "\n\n" + "\n".join(parts)},
    ]

    resp = oa.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=messages,
    )
    raw = resp.choices[0].message.content
    return json.loads(raw)

# ---------- FX helpers ----------
def _convert_money(m: Optional[Dict[str, Any]], target: Optional[str], to_target: Optional[Dict[str, float]]) -> Optional[Dict[str, Any]]:
    if not m or not target or not to_target:
        return None
    amt = m.get("amount"); ccy = (m.get("currency") or "").upper() if m.get("currency") else None
    if amt is None or not ccy:
        return None
    rate = to_target.get(ccy)
    if not isinstance(rate, (int, float)):
        return None
    return {"amount": round(float(amt) * float(rate), 2), "currency": target}

def _merge_note(extracted_note: Optional[str], tag: str) -> Optional[str]:
    if extracted_note and tag:
        return f"{tag}; {extracted_note}"
    return extracted_note or tag or None

# ---------- Main Tool ----------
def cityfares_discovery_tool(args: CityFaresArgs) -> CityFaresResult:
    """
    LLM-first CityFares discovery (fast budgets).
    - Tavily search+extract (official-first URLs, enriched by preferences/musts)
    - Single LLM JSON pass per city (if OPENAI_API_KEY present and use_llm != False)
    - Optional FX mirror fields when fx_target + fx_to_target provided
    """
    logs: List[str] = []
    errors: List[Dict[str, str]] = []
    out_fares: Dict[str, CityFaresCityResult] = {}

    # Set up clients
    try:
        tv = _tavily()
    except Exception as e:
        errors.append({"stage": "init", "message": str(e)})
        return CityFaresResult(city_fares={}, logs=logs, errors=errors)

    oa = _openai_client_or_none()
    use_llm = args.use_llm if args.use_llm is not None else (oa is not None)
    model = (args.model or OPENAI_MODEL)

    cities = list(args.cities or [])
    city_country = dict(args.city_country_map or {})
    if not cities:
        errors.append({"stage": "input", "message": "cities is required"})
        return CityFaresResult(city_fares={}, logs=logs, errors=errors)

    language = _pref_language(args.preferences)

    def _search_urls_variant(tv: TavilyClient, base_queries: List[str], city: str, country: str) -> List[str]:
        urls: List[str] = []
        queries = _compose_queries(
            city=city,
            country=country,
            base_templates=base_queries,
            preferences=args.preferences,
            travelers=args.travelers,
            musts=args.musts,
            language=language,
            max_variants=MAX_QUERY_VARIANTS,
        )
        for q in queries:
            try:
                sr = tv.search(
                    q,
                    max_results=MAX_SEARCH_RESULTS,
                    include_answer=True,
                    search_depth=SEARCH_DEPTH,          # key speed lever
                    include_raw_content=False,          # keep light
                ) or {}
            except Exception:
                continue
            for r in (sr.get("results") or []):
                u = (r.get("url") or "").strip()
                if u:
                    urls.append(u)
        return _sort_urls_official_first(urls)

    def _process_city(city: str) -> Tuple[str, CityFaresCityResult, float]:
        t0 = time.time()
        country = city_country.get(city, "")

        urls_t = _search_urls_variant(tv, TRANSIT_QUERIES, city, country)[:args.max_urls_per_city]
        urls_x = _search_urls_variant(tv, TAXI_QUERIES, city, country)[:args.max_urls_per_city]
        urls = _sort_urls_official_first(urls_t + urls_x)[:args.max_urls_per_city]

        if not urls:
            logs.append(f"CityFares[{city}]: no URLs found")
            pages = []
        else:
            pages = _extract_pages(tv, urls, logs)
            if not pages:
                logs.append(f"CityFares[{city}]: extract empty")

        if pages and use_llm and oa:
            try:
                ext = _llm_extract_fares(
                    oa, model, city, country,
                    _enforce_total_budget(pages, MAX_TOTAL_CHARS),
                    args.preferences, args.travelers, args.musts
                )
            except Exception as e:
                logs.append(f"CityFares[{city}]: LLM error {e}; using sources-only stub")
                ext = None
        else:
            ext = None

        # If no LLM or error → sources-only stub
        if not ext:
            ext = {
                "city": city, "country": country,
                "transit": {
                    "single": {"amount": None, "currency": None, "source": None, "note": None},
                    "day_pass": {"amount": None, "currency": None, "source": None, "note": None},
                    "weekly_pass": {"amount": None, "currency": None, "source": None, "note": None},
                    "sources": urls[:12],
                },
                "taxi": {
                    "base": {"amount": None, "currency": None, "source": None},
                    "per_km": {"amount": None, "currency": None, "source": None},
                    "per_min": {"amount": None, "currency": None, "source": None},
                    "sources": urls[:12],
                    "note": None
                }
            }

        # Parse transit
        tr = ext.get("transit", {}) if isinstance(ext, dict) else {}
        single = tr.get("single") or {}
        day    = tr.get("day_pass") or {}
        week   = tr.get("weekly_pass") or {}

        transit_sources = list(dict.fromkeys(
            [single.get("source"), day.get("source"), week.get("source")] + (tr.get("sources") or []) + urls
        ))
        transit_sources = [u for u in transit_sources if u][:12]

        tag = "LLM extraction" if (pages and use_llm and oa) else "sources-only"
        single_note = _merge_note(single.get("note"), tag)
        day_note    = _merge_note(day.get("note"), tag)
        week_note   = _merge_note(week.get("note"), tag)

        transit = TransitFaresOut(
            single=MoneyOut(amount=(None if single.get("amount") is None else float(single["amount"])),
                            currency=(single.get("currency") or None),
                            note=single_note),
            day_pass=MoneyOut(amount=(None if day.get("amount") is None else float(day["amount"])),
                              currency=(day.get("currency") or None),
                              note=day_note),
            weekly_pass=MoneyOut(amount=(None if week.get("amount") is None else float(week["amount"])),
                                 currency=(week.get("currency") or None),
                                 note=week_note),
            sources=transit_sources,
        )

        # Parse taxi
        tx = ext.get("taxi") or {}
        base = (tx.get("base") or {}).get("amount")
        km   = (tx.get("per_km") or {}).get("amount")
        mins = (tx.get("per_min") or {}).get("amount")
        tccy = (tx.get("base") or {}).get("currency") or (tx.get("per_km") or {}).get("currency") or (tx.get("per_min") or {}).get("currency")

        taxi_sources = list(dict.fromkeys([
            (tx.get("base") or {}).get("source"),
            (tx.get("per_km") or {}).get("source"),
            (tx.get("per_min") or {}).get("source"),
            *((tx.get("sources") or [])),
            *urls
        ]))
        taxi_sources = [u for u in taxi_sources if u][:12]

        taxi = TaxiFaresOut(
            base=None if base is None else float(base),
            per_km=None if km is None else float(km),
            per_min=None if mins is None else float(mins),
            currency=(tccy or None),
            sources=taxi_sources,
            note=_merge_note(tx.get("note"), tag),
        )

        payload = CityFaresCityResult(transit=transit, taxi=taxi)

        # Optional FX mirrors
        if args.fx_target and args.fx_to_target:
            def _mk(mdict: Optional[MoneyOut]) -> Optional[Dict[str, Any]]:
                if not mdict: return None
                return {"amount": mdict.amount, "currency": mdict.currency}

            t_single_t = _convert_money(_mk(transit.single), args.fx_target, args.fx_to_target)
            t_day_t    = _convert_money(_mk(transit.day_pass), args.fx_target, args.fx_to_target)
            t_week_t   = _convert_money(_mk(transit.weekly_pass), args.fx_target, args.fx_to_target)

            # No top-level 'currency' string here (keeps type: Dict[str, Optional[Dict[str, Any]]])
            payload.transit_target = {
                "single": t_single_t,
                "day_pass": t_day_t,
                "weekly_pass": t_week_t,
            }

            rate = args.fx_to_target.get((taxi.currency or "").upper()) if taxi.currency else None
            if isinstance(rate, (int, float)):
                # Keep only numeric fields (type: Dict[str, Optional[float]])
                payload.taxi_target = {
                    "base": None if taxi.base is None else round(float(taxi.base) * float(rate), 2),
                    "per_km": None if taxi.per_km is None else round(float(taxi.per_km) * float(rate), 2),
                    "per_min": None if taxi.per_min is None else round(float(taxi.per_min) * float(rate), 2),
                }

        took = time.time() - t0
        logs.append(
            f"CityFares[{city}] {'LLM' if (pages and use_llm and oa) else 'sources'} "
            f"| urls={len(urls)} pages={len(pages)} | "
            f"transit(single={transit.single.amount if transit.single else None} {transit.single.currency if transit.single else None}, "
            f"day={transit.day_pass.amount if transit.day_pass else None} {transit.day_pass.currency if transit.day_pass else None}) "
            f"taxi(base={taxi.base}, km={taxi.per_km}, min={taxi.per_min} {taxi.currency}) | "
            f"{took:.2f}s"
        )
        return city, payload, took

    max_workers_cities = min(MAX_CITY_WORKERS, len(cities) or 1)
    with ThreadPoolExecutor(max_workers=max_workers_cities) as pool:
        futures = {pool.submit(_process_city, city): city for city in cities}
        for fut in as_completed(futures):
            city, payload, _ = fut.result()
            out_fares[city] = payload

    return CityFaresResult(city_fares=out_fares, logs=logs, errors=errors)


# ---------- OpenAI tool schema (optional) ----------
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "cityfares_discovery_tool",
        "description": "Discover public transit and taxi fares for given cities (official sources first). LLM extraction if OPENAI_API_KEY present; missing values remain None. Optional FX mirrors. Honors preferences/musts like pass names, kid policy, language.",
        "parameters": {
            "type": "object",
            "properties": {
                "cities": {"type": "array", "items": {"type": "string"}},
                "city_country_map": {"type": "object","additionalProperties": {"type": "string"}},
                "preferences": {"type": "object", "additionalProperties": True},
                "travelers": {"type": "object", "additionalProperties": {"type":"integer"}},
                "musts": {"type": "array", "items": {"type": "string"}},
                "fx_target": {"type": "string", "description": "Target currency code (ISO-4217) for mirrored amounts."},
                "fx_to_target": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                    "description": "Map CODE->multiplier (code to target) from the FX tool."
                },
                "max_urls_per_city": {"type": "integer"},
                "model": {"type": "string"},
                "use_llm": {"type": "boolean"}
            },
            "required": ["cities", "city_country_map"]
        }
    }
}


# ---------- CLI Tests ----------
def _print_city_result(city: str, r: CityFaresCityResult) -> None:
    print(f"\n== {city} ==")
    if r.transit:
        print("  Transit:")
        print(f"    Single:  {r.transit.single.amount if r.transit.single else None} {r.transit.single.currency if r.transit.single else ''}")
        print(f"    DayPass: {r.transit.day_pass.amount if r.transit.day_pass else None} {r.transit.day_pass.currency if r.transit.day_pass else ''}")
        print(f"    Weekly:  {r.transit.weekly_pass.amount if r.transit.weekly_pass else None} {r.transit.weekly_pass.currency if r.transit.weekly_pass else ''}")
        print(f"    Sources: {len(r.transit.sources)}")
    if r.taxi:
        print("  Taxi:")
        print(f"    Base:    {r.taxi.base} {r.taxi.currency or ''}")
        print(f"    per_km:  {r.taxi.per_km} {r.taxi.currency or ''}")
        print(f"    per_min: {r.taxi.per_min} {r.taxi.currency or ''}")
        print(f"    Sources: {len(r.taxi.sources)}")


if __name__ == "__main__":
    # Minimal smoke tests (kept small for speed)
    tests = [
        {
            "name": "NYC (EN, passes)",
            "args": CityFaresArgs(
                cities=["New York"],
                city_country_map={"New York": "United States"},
                preferences={"language": "en", "pass_names": ["OMNY", "MetroCard"]},
                travelers={"adults": 2, "children": 0},
                musts=[],
                max_urls_per_city=MAX_URLS_PER_CITY,
            ),
        },
        {
            "name": "Tokyo (EN, kid-friendly hint)",
            "args": CityFaresArgs(
                cities=["Tokyo"],
                city_country_map={"Tokyo": "Japan"},
                preferences={"language": "en", "kid_friendly": True},
                travelers={"adults": 2, "children": 1},
                musts=[],
                max_urls_per_city=MAX_URLS_PER_CITY,
            ),
        },
        {
            "name": "Paris+Rome (multi-city, EN)",
            "args": CityFaresArgs(
                cities=["Paris", "Rome"],
                city_country_map={"Paris": "France", "Rome": "Italy"},
                preferences={"language": "en", "pass_names": ["Navigo", "Roma Pass"]},
                travelers={"adults": 2, "children": 0},
                musts=["Navigo Découverte"],
                max_urls_per_city=MAX_URLS_PER_CITY,
            ),
        },
    ]

    for t in tests:
        print("\n" + "="*12, t["name"], "="*12)
        t0 = time.time()
        res = cityfares_discovery_tool(t["args"])
        took = time.time() - t0
        for lg in res.logs:
            print("  •", lg)
        for city, payload in res.city_fares.items():
            _print_city_result(city, payload)
        if res.errors:
            print("ERRORS:", res.errors)
        print(f"→ took: {took:.2f}s total")
