"""
Restaurants Discovery Tool for TripPlanner Multi-Agent System

This tool discovers restaurants and dining options near specific POIs or in cities.
It provides comprehensive dining recommendations with cuisine types, locations,
and proximity information for trip planning.

Key features:
- Restaurant discovery using web search and AI analysis
- POI-based restaurant recommendations
- Cuisine type identification and classification
- Location-based proximity analysis
- AI-powered content extraction and structuring

The tool ensures comprehensive dining discovery, providing users with
detailed restaurant recommendations that complement their planned activities
and attractions.
"""

from __future__ import annotations

import os, re, json, time, textwrap
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from pydantic import BaseModel, Field

# External deps
from tavily import TavilyClient
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # required for extraction in this tool

OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------- Tunables (env-overridable) ----------------
DEFAULT_QUERY_TEMPLATE       = os.getenv("REST_QUERY_TEMPLATE", "best restaurants near {poi} {city}")
DEFAULT_MAX_RESULTS_PER_POI  = 6     # search returns a few; we'll only keep top 2 URLs
DEFAULT_MAX_POIS_PER_CITY    = int(os.getenv("REST_MAX_POIS", "5"))
DEFAULT_MAX_NAMES_PER_POI    = int(os.getenv("REST_MAX_NAMES", "30"))
DEFAULT_MAX_QUERY_VARIANTS   = 1     # **one** search per POI

# LLM context budgeting (applies to answer + snippets only; no extract pages)
DEFAULT_MAX_SNIPPET_CHARS    = int(os.getenv("REST_MAX_SNIPPET_CHARS", "400"))
DEFAULT_MAX_TOTAL_CHARS      = int(os.getenv("REST_MAX_TOTAL_CHARS", "8000"))
DEFAULT_MIN_KEEP_PER_CHUNK   = int(os.getenv("REST_MIN_KEEP", "500"))

# Concurrency knobs
REST_POI_WORKERS       = int(os.getenv("REST_POI_WORKERS", "6"))  # per city (POIs in parallel)
REST_QUERY_WORKERS     = 1  # exactly one search per POI

DEFAULT_BLOCKLIST = set(
    (os.getenv("REST_BLOCKLIST") or
     "reddit.com,pinterest.com,facebook.com,instagram.com,tiktok.com,tripadvisor.com").split(",")
)

# ---------------- Schemas ----------------
class RestaurantLinkOut(BaseModel):
    name: str
    url: str
    near_poi: str
    snippet: Optional[str] = None

class RestaurantNameOut(BaseModel):
    name: str
    url: Optional[str] = None  # explicit None allowed if official URL unclear
    source: str                # page where the name was found

class RestaurantsDiscoveryArgs(BaseModel):
    cities: List[str]

    # Provide POIs per city, or fall back to flat 'poi' = [{"city","name"}, ...]
    pois_by_city: Optional[Dict[str, List[Any]]] = None
    poi: Optional[List[Dict[str, Any]]] = None

    # Interpreter/user context → affects search & LLM ranking
    travelers: Optional[Dict[str, int]] = None  # {"adults":2,"children":1}
    musts: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)  # cuisines, dietary, price_tier, kid_friendly, accessibility, avoid, meal, language, rating_min

    # Search & LLM tunables
    query_template: str = DEFAULT_QUERY_TEMPLATE
    max_results_per_poi: int = DEFAULT_MAX_RESULTS_PER_POI
    max_pois_per_city: int = DEFAULT_MAX_POIS_PER_CITY
    max_names_per_poi: int = DEFAULT_MAX_NAMES_PER_POI
    domain_blocklist: Optional[List[str]] = None

    # LLM
    model: Optional[str] = None
    use_llm: Optional[bool] = None  # default: True iff OPENAI_API_KEY present

class RestaurantsDiscoveryResult(BaseModel):
    links_by_city: Dict[str, Dict[str, List[RestaurantLinkOut]]] = Field(default_factory=dict)
    names_by_city: Dict[str, Dict[str, List[RestaurantNameOut]]] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)

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

_TITLE_SPLIT = re.compile(r"\s[-–—|]\s")
def _clean_title(t: str) -> str:
    t = (t or "").strip()
    parts = _TITLE_SPLIT.split(t)
    if parts: t = parts[0]
    t = re.sub(r"\b(Best|Top \d+|Guide|Menu|Official Site)\b", "", t, flags=re.I)
    return t.strip(" -–—|").strip()

def _domain(u: str) -> str:
    try:
        host = urlparse(u).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " …"

@dataclass
class RestHit:
    name: str
    url: str
    near_poi: str
    snippet: Optional[str] = None

def _with_kids_flag(travelers: Optional[Dict[str,int]], preferences: Dict[str, Any]) -> bool:
    if isinstance(preferences, dict) and preferences.get("kid_friendly") is True:
        return True
    try:
        return int((travelers or {}).get("children", 0) or 0) > 0
    except Exception:
        return False

def _pref_language(preferences: Dict[str, Any]) -> Optional[str]:
    lang = None
    if isinstance(preferences, dict):
        lang = preferences.get("language")
    if isinstance(lang, str) and len(lang) <= 5:
        return lang
    return None

def _build_locale_query_suffix(language: Optional[str]) -> str:
    # Gentle hint to prefer a language (does not force)
    if language:
        return f" (prefer {language} official sources)"
    return ""

def _price_tokens(preferences: Dict[str, Any]) -> List[str]:
    tier = (preferences or {}).get("budget_tier") or (preferences or {}).get("price_tier")
    if not isinstance(tier, str): return []
    t = tier.lower()
    if t in ("budget","cheap","affordable","low","$$","$"):
        return ["cheap eats", "affordable", "inexpensive"]
    if t in ("mid","moderate","mid-range","$$$"):
        return ["moderate price", "mid-range"]
    if t in ("luxury","high","fine","$$$$","splurge","5-star"):
        return ["fine dining", "upscale"]
    return []

def _diet_tokens(preferences: Dict[str, Any]) -> List[str]:
    diet = preferences.get("dietary")
    tokens: List[str] = []
    if isinstance(diet, list):
        vals = [str(x).lower() for x in diet]
    elif isinstance(diet, str):
        vals = [diet.lower()]
    else:
        vals = []
    for v in vals:
        if "vegan" in v: tokens += ["vegan"]
        if "vegetarian" in v: tokens += ["vegetarian"]
        if "gluten" in v: tokens += ["gluten-free"]
        if "halal" in v: tokens += ["halal"]
        if "kosher" in v: tokens += ["kosher"]
    for k in ["vegan","vegetarian","gluten_free","halal","kosher"]:
        if preferences.get(k) is True:
            tokens.append(k.replace("_","-"))
    return list(dict.fromkeys(tokens))

def _cuisine_tokens(preferences: Dict[str, Any]) -> List[str]:
    cs = preferences.get("cuisines") or []
    if isinstance(cs, str): cs = [cs]
    return [str(x).strip() for x in cs if str(x).strip()]

def _access_tokens(preferences: Dict[str, Any]) -> List[str]:
    acc = preferences.get("accessibility") or {}
    toks = []
    if isinstance(acc, dict) and acc.get("wheelchair"):
        toks.append("wheelchair accessible")
    if isinstance(preferences, dict) and preferences.get("avoid_crowds"):
        toks.append("quiet ambience")
    return toks

def _kid_tokens(with_kids: bool) -> List[str]:
    return ["kid friendly", "family friendly", "high chairs"] if with_kids else []

def _meal_tokens(preferences: Dict[str, Any]) -> List[str]:
    meal = preferences.get("meal")
    if not isinstance(meal, str): return []
    m = meal.lower()
    if m in ("breakfast","brunch","lunch","dinner","late night"):
        return [m]
    return []

def _compose_search_query(city: str, poi: str, preferences: Dict[str, Any],
                          template: str, language: Optional[str]) -> str:
    base = (template or DEFAULT_QUERY_TEMPLATE).format(city=city, poi=poi)
    qlang = _build_locale_query_suffix(language)

    tokens: List[str] = []
    tokens += _cuisine_tokens(preferences)
    tokens += _diet_tokens(preferences)
    tokens += _price_tokens(preferences)
    tokens += _access_tokens(preferences)
    tokens += _meal_tokens(preferences)
    if _with_kids_flag(None, preferences):
        tokens += _kid_tokens(True)

    # Keep the query short but informative
    if tokens:
        base = base + " " + " ".join(tokens[:5])

    return base + qlang

# ---------------- Minimal Tavily search (no extract) ----------------
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}

def _search_minimal(tv: TavilyClient, query: str, rmax: int) -> Tuple[List[Dict[str,str]], Optional[str]]:
    """
    Single Tavily search call. Returns (top_results[:2], answer_text).
    Each result is a dict {url, title, content}.
    """
    if query in _SEARCH_CACHE:
        sr = _SEARCH_CACHE[query]
    else:
        sr = tv.search(
            query,
            include_answer=True,
            max_results=rmax,
            search_depth="basic",
            include_raw_content=False,
        ) or {}
        _SEARCH_CACHE[query] = sr

    results = []
    for r in (sr.get("results") or []):
        url = (r.get("url") or "").strip()
        title = _clean_title(r.get("title") or "")
        content = (r.get("content") or "").strip()
        if url and title:
            results.append({"url": url, "title": title, "content": content})
    # Prefer diverse domains; keep two only
    seen_dom, picked = set(), []
    for r in results:
        dom = _domain(r["url"])
        if not dom or dom in seen_dom: 
            continue
        seen_dom.add(dom)
        picked.append(r)
        if len(picked) >= 2:
            break

    return picked, (sr.get("answer") or None)

# ---------------- LLM parsing: from answer + snippets ONLY ----------------
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

def _llm_parse_names_from_snippets(
    oa: OpenAI,
    city: str,
    poi: str,
    answer_text: Optional[str],
    results: List[Dict[str, str]],   # at most 2 items
    max_names: int,
    model: str,
    preferences: Dict[str, Any],
    musts: List[str],
    travelers: Optional[Dict[str,int]],
) -> List[RestaurantNameOut]:
    with_kids = _with_kids_flag(travelers, preferences)
    cuisines = _cuisine_tokens(preferences)
    diet = _diet_tokens(preferences)
    price = _price_tokens(preferences)
    access = _access_tokens(preferences)
    meal = _meal_tokens(preferences)
    avoid = preferences.get("avoid") or []
    if isinstance(avoid, str): avoid = [avoid]

    schema = textwrap.dedent(f"""
    Return STRICT JSON:
    {{
      "city": "string",
      "poi": "string",
      "restaurants": [ {{"name": "string", "url": "string|null", "source": "string"}} ]
    }}
    Selection rules (soft filters; keep JSON strict):
    - Prioritize cuisines: {cuisines or []}
    - Dietary constraints: {diet or []}
    - Price bias: {price or []}
    - Kid/family friendly bias: {"enabled" if with_kids else "disabled"}
    - Accessibility bias: {access or []}
    - Meal focus: {meal or []}
    - Avoid: {avoid or []}
    - MUST-INCLUDE if present (exact/near): {musts or []}
    - Extract up to {max_names} ACTUAL restaurant names near the POI (no categories/hotels).
    - For 'url', prefer the official website; if unclear, set null and keep 'source'.
    - Deduplicate by name; strip emojis/site suffixes. Respond with JSON only.
    """)

    # Build tiny context: Tavily answer + up to 2 snippets
    chunks: List[Tuple[str,str]] = []
    if answer_text:
        chunks.append(("tavily:search:answer", _trim_text(answer_text, DEFAULT_MAX_SNIPPET_CHARS, DEFAULT_MIN_KEEP_PER_CHUNK)))
    for r in results:
        u = r["url"]
        snip = r.get("content") or r.get("title") or ""
        chunks.append((u, _trim_text(snip, DEFAULT_MAX_SNIPPET_CHARS, DEFAULT_MIN_KEEP_PER_CHUNK)))
    chunks = _cap_chunks(chunks, DEFAULT_MAX_TOTAL_CHARS, DEFAULT_MIN_KEEP_PER_CHUNK)

    parts = [f"City: {city}\nPOI: {poi}\n", "SOURCES:\n"]
    for i, (u, _) in enumerate(chunks, 1):
        parts.append(f"{i}. {u}")
    parts.append("\nEXCERPTS:\n")
    for i, (u, text) in enumerate(chunks, 1):
        parts.append(f"--- Source {i}: {u} ---\n{text}\n")

    resp = oa.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You extract restaurant names from short notes. Respond with strict JSON only."},
            {"role": "user", "content": schema + "\n\n" + "\n".join(parts)},
        ],
    )
    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{[\s\S]*\}\s*$", raw or "")
        data = json.loads(m.group(0)) if m else {"restaurants":[]}

    items = (data or {}).get("restaurants") or []
    out: List[RestaurantNameOut] = []
    seen = set()
    for it in items:
        name = (it.get("name") or "").strip()
        src  = (it.get("source") or "").strip()
        url  = (it.get("url") or "") or None
        if not name or not src:
            continue
        k = name.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(RestaurantNameOut(name=name, url=url, source=src))
        if len(out) >= max_names:
            break
    return out

# ---------------- Main Tool (search-only; no extracts) ----------------
def restaurants_discovery_tool(args: RestaurantsDiscoveryArgs) -> RestaurantsDiscoveryResult:
    logs: List[str] = []
    errors: List[Dict[str, str]] = []

    # Clients
    try:
        tv = _tavily()
    except Exception as e:
        errors.append({"stage": "init", "message": str(e)})
        return RestaurantsDiscoveryResult(logs=logs, errors=errors)

    ocli = _openai_or_none()
    use_llm = args.use_llm if args.use_llm is not None else True  # REQUIRE LLM by default per your ask
    model = (args.model or OPENAI_MODEL_DEFAULT)

    if use_llm and not ocli:
        errors.append({"stage": "init", "message": "OPENAI_API_KEY is not set or openai SDK unavailable"})
        return RestaurantsDiscoveryResult(logs=logs, errors=errors)

    blocklist = set(d.strip().lower() for d in (args.domain_blocklist or list(DEFAULT_BLOCKLIST)) if d.strip())

    cities = list(args.cities or [])
    if not cities:
        errors.append({"stage": "input", "message": "cities is required"})
        return RestaurantsDiscoveryResult(logs=logs, errors=errors)

    # Normalize POIs mapping
    pois_by_city: Dict[str, List[str]] = {}
    raw_map = dict(args.pois_by_city or {})

    # fallback from flat 'poi' if provided
    if not raw_map and args.poi:
        for p in args.poi or []:
            if isinstance(p, dict):
                c = (p.get("city") or "").strip()
                n = (p.get("name") or "").strip()
                if c and n:
                    pois_by_city.setdefault(c, []).append(n)
    # merge/override with provided map
    for c in cities:
        lst = raw_map.get(c) or pois_by_city.get(c) or []
        names: List[str] = []
        for x in lst:
            if isinstance(x, str) and x.strip():
                names.append(x.strip())
            elif isinstance(x, dict) and x.get("name"):
                names.append(str(x["name"]).strip())
        if not names:
            names = [f"{c} city center"]
        # dedupe and cap
        seen = set(); uniq = []
        for n in names:
            k = n.casefold()
            if k and k not in seen:
                seen.add(k); uniq.append(n)
        pois_by_city[c] = uniq[: args.max_pois_per_city]

    links_by_city: Dict[str, Dict[str, List[RestaurantLinkOut]]] = {}
    names_by_city: Dict[str, Dict[str, List[RestaurantNameOut]]] = {}

    language = _pref_language(args.preferences)

    def _process_city_poi(city: str, poi: str) -> Tuple[str, str, List[RestaurantLinkOut], List[RestaurantNameOut]]:
        # Build exactly ONE concise query; run one search
        query = _compose_search_query(city, poi, args.preferences, args.query_template, language)

        hits: List[RestHit] = []
        try:
            results, answer = _search_minimal(tv, query, args.max_results_per_poi)
        except Exception as e:
            logs.append(f"[TAVILY] search error {city}|{poi}: {e!r}")
            return city, poi, [], []

        # Filter results by blocklist/domain diversity (already handled in _search_minimal partly)
        picked: List[Dict[str,str]] = []
        seen_domains = set()
        for r in results:
            url = r["url"]; title = r["title"]; content = r.get("content") or ""
            dom = _domain(url)
            if not dom or dom in blocklist or dom in seen_domains:
                continue
            seen_domains.add(dom)
            snippet = _clip(content, 220) or None
            hits.append(RestHit(name=title, url=url, near_poi=poi, snippet=snippet))
            picked.append(r)

        # LLM parse from Tavily answer + up to two snippets
        names: List[RestaurantNameOut] = []
        if use_llm and ocli:
            try:
                names = _llm_parse_names_from_snippets(
                    ocli, city, poi, answer, picked, args.max_names_per_poi, model,
                    preferences=args.preferences, musts=args.musts, travelers=args.travelers
                )
            except Exception as e:
                logs.append(f"[LLM] parse error {city}|{poi}: {e!r}")

        link_payload = [RestaurantLinkOut(**asdict(h)) for h in hits]
        logs.append(f"Restaurants[{city} | {poi}]: 1 search call, answer={bool(answer)}, snippet_urls={len(picked)}, names={len(names)}")
        return city, poi, link_payload, names

    # Parallelize per city
    for city in cities:
        links_by_city[city] = {}
        names_by_city[city] = {}

        pois = pois_by_city.get(city, [])
        max_workers = min(REST_POI_WORKERS, len(pois) or 1)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_process_city_poi, city, poi): poi for poi in pois}
            for fut in as_completed(futures):
                c, poi, links, names = fut.result()
                links_by_city[c][poi] = links
                names_by_city[c][poi] = names

    return RestaurantsDiscoveryResult(
        links_by_city=links_by_city,
        names_by_city=names_by_city,
        logs=logs,
        errors=errors
    )

# ---------------- OpenAI tool schema (optional) ----------------
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "restaurants_discovery_tool",
        "description": "Discover restaurants near POIs using a single Tavily search (answer + up to two snippets) and OpenAI to parse clean names. Honors cuisines, dietary, price tier, kid-friendliness, accessibility, meal, language, and must-include names. No Tavily extract calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "cities": {"type": "array", "items": {"type": "string"}},
                "pois_by_city": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": {"anyOf":[{"type":"string"},{"type":"object"}]}}
                },
                "poi": {"type": "array", "items": {"type": "object"}},
                "travelers": {"type": "object", "additionalProperties": {"type":"integer"}},
                "musts": {"type": "array", "items": {"type": "string"}},
                "preferences": {"type": "object", "additionalProperties": True},
                "query_template": {"type": "string"},
                "max_results_per_poi": {"type": "integer", "minimum": 2, "maximum": 20},
                "max_pois_per_city": {"type": "integer", "minimum": 1, "maximum": 20},
                "max_names_per_poi": {"type": "integer", "minimum": 5, "maximum": 100},
                "domain_blocklist": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string"},
                "use_llm": {"type": "boolean"}
            },
            "required": ["cities"]
        }
    }
}

# ---------------- CLI tests ----------------
def _print_sample(out: RestaurantsDiscoveryResult, started: float, title: str):
    print(f"\n===== {title} =====")
    print(f"took: {time.time()-started:.2f}s")
    if out.errors:
        print("errors:", out.errors)
    for city, bypoi in out.links_by_city.items():
        for poi, links in bypoi.items():
            names = out.names_by_city.get(city, {}).get(poi, [])
            print(f"\n  {city} | POI: {poi}")
            print(f"    links: {len(links)} | names: {len(names)}")
            for n in names[:8]:
                print(f"      • {n.name}  ({n.url or '—'})  [src: {n.source}]")

if __name__ == "__main__":
    # Ensure env:
    # export TAVILY_API_KEY=...
    # export OPENAI_API_KEY=...
    tests = [
        {
            "title": "Tokyo (POIs: Skytree, Ueno Zoo)",
            "args": RestaurantsDiscoveryArgs(
                cities=["Tokyo"],
                pois_by_city={"Tokyo": ["Tokyo Skytree", "Ueno Zoo"]},
                preferences={"language":"en", "cuisines":["ramen","sushi"], "kid_friendly": True, "price_tier":"mid"},
                max_results_per_poi=DEFAULT_MAX_RESULTS_PER_POI,
                max_names_per_poi=25,
            ),
        },
        {
            "title": "Rome (POIs: Colosseum, Trastevere)",
            "args": RestaurantsDiscoveryArgs(
                cities=["Rome"],
                pois_by_city={"Rome": ["Colosseum", "Trastevere"]},
                preferences={"language":"en","cuisines":["roman","pizza"], "meal":"dinner", "price_tier":"mid"},
                max_results_per_poi=DEFAULT_MAX_RESULTS_PER_POI,
            ),
        },
    ]

    for t in tests:
        t0 = time.time()
        out = restaurants_discovery_tool(t["args"])
        _print_sample(out, t0, t["title"])
        # Debug logs:
        # for lg in out.logs: print("  log:", lg)
