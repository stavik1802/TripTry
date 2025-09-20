# app/tools/intercity_discovery_tool.py — v3
from __future__ import annotations

import os, re, time
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field, field_validator
from tavily import TavilyClient

# ===================== Global speed knobs (ENV) =====================
INTERCITY_SEARCH_DEPTH      = os.getenv("INTERCITY_SEARCH_DEPTH", "basic")  # "basic" | "advanced"
INTERCITY_INCLUDE_RAW       = os.getenv("INTERCITY_INCLUDE_RAW", "false").lower() == "true"
INTERCITY_QUERY_WORKERS     = int(os.getenv("INTERCITY_QUERY_WORKERS", "4"))   # per-mode variant fan-out
INTERCITY_HOP_WORKERS       = int(os.getenv("INTERCITY_HOP_WORKERS", "6"))     # across hops
INTERCITY_RESULTS_PER_QUERY = int(os.getenv("INTERCITY_RESULTS_PER_QUERY", "3"))

# ===================== duration parsing (tiny & robust) =====================
_HOUR_WORDS = r"(?:hours?|hrs?|hr)"
_MIN_WORDS  = r"(?:minutes?|mins?|min)"

_PATTERNS_DUR = {
    "HM_words":   re.compile(rf"(?<!\d)(\d{{1,2}})\s*{_HOUR_WORDS}\s*(?:and\s*)?(\d{{1,2}})\s*{_MIN_WORDS}\b", re.I),
    "HM_compact": re.compile(r"(?<!\d)(\d{1,2})\s*h\s*(\d{1,2})\s*m\b", re.I),
    "HM_sticky":  re.compile(r"(?<!\d)(\d{1,2})h(\d{1,2})\b", re.I),
    "H_words_dec":re.compile(rf"(?<!\d)(\d{{1,2}}(?:[.,]\d+)?)\s*{_HOUR_WORDS}\b", re.I),
    "H_compact":  re.compile(r"(?<!\d)(\d{1,2})\s*h(?![a-z])\b", re.I),
    "M_words":    re.compile(rf"(?<!\d)(\d{{1,3}})\s*{_MIN_WORDS}\b", re.I),
    "M_compact":  re.compile(r"(?<!\d)(\d{1,3})\s*m(?![a-z])\b", re.I),
    "H_colon_M":  re.compile(r"(?<!\d)(\d{1,2})\s*:\s*(\d{2})\s*h\b", re.I),
}

def _gather_minutes(text: str) -> Tuple[List[int], List[int], List[int]]:
    if not text: return [], [], []
    hm: List[int] = []; hh: List[int] = []; mm: List[int] = []

    for pat in ("HM_words","HM_compact","HM_sticky","H_colon_M"):
        for m in _PATTERNS_DUR[pat].finditer(text):
            hm.append(int(m.group(1))*60 + int(m.group(2)))

    for m in _PATTERNS_DUR["H_words_dec"].finditer(text):
        val = float(m.group(1).replace(",", "."))
        hh.append(int(round(val * 60)))
    for m in _PATTERNS_DUR["H_compact"].finditer(text):
        hh.append(int(m.group(1)) * 60)

    for pat in ("M_words","M_compact"):
        for m in _PATTERNS_DUR[pat].finditer(text):
            mm.append(int(m.group(1)))

    ok = lambda x: 10 <= x <= 24*60
    return [x for x in hm if ok(x)], [x for x in hh if ok(x)], [x for x in mm if ok(x)]

def _parse_best_duration_minutes(text: str) -> Optional[int]:
    HM, H, M = _gather_minutes(text or "")
    if HM: return min(HM)
    if H:  return min(H)
    if M:  return min(M)
    return None

# ===================== price parsing (site-agnostic) =====================
_SYM = {"€":"EUR","£":"GBP","¥":"JPY","₩":"KRW","₪":"ILS","₺":"TRY","₽":"RUB"}
_ISO_WORDS = {"usd":"USD","eur":"EUR","gbp":"GBP","jpy":"JPY","cad":"CAD","aud":"AUD",
              "nzd":"NZD","chf":"CHF","cny":"CNY","inr":"INR","try":"TRY","ils":"ILS","sgd":"SGD"}
_WORDS = {"euro":"EUR","euros":"EUR","pound":"GBP","pounds":"GBP","dollar":"USD","dollars":"USD",
          "yen":"JPY","shekel":"ILS","shekels":"ILS","rupee":"INR","rupees":"INR"}

_PATTERNS_PRICE = {
    "symbol": re.compile(r"(?:(C\$|A\$)|([$€£¥₩₪₺₽]))\s?(\d{1,7}(?:[.,]\d{1,2})?)"),
    "iso_pre": re.compile(r"\b([A-Z]{3})\s?(\d{1,7}(?:[.,]\d{1,2})?)\b"),
    "word_after": re.compile(r"(\d{1,7}(?:[.,]\d{1,2})?)\s*(euros?|pounds?|dollars?|yen|shekels?|rupees?)", re.I),
    "iso_after": re.compile(r"(\d{1,7}(?:[.,]\d{1,2})?)\s*(usd|eur|gbp|jpy|cad|aud|nzd|chf|cny|inr|try|ils|sgd)\b", re.I),
}
_THOUSANDS_GROUP = re.compile(r"^\d{1,3}(?:,\d{3})+$")

def _to_float(num: str) -> float:
    s = num.strip()
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if _THOUSANDS_GROUP.fullmatch(s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    return float(s)

def _gather_prices(text: str, default_dollar: str) -> List[Tuple[float,str]]:
    if not text: return []
    out: List[Tuple[float,str]] = []

    for m in _PATTERNS_PRICE["symbol"].finditer(text):
        symA, symB, amt = m.group(1), m.group(2), m.group(3)
        if symA in ("C$","A$"):
            ccy = "CAD" if symA == "C$" else "AUD"
        elif symB:
            ccy = _SYM.get(symB, "USD" if symB == "$" else None) or default_dollar
        else:
            ccy = default_dollar
        out.append((_to_float(amt), ccy))

    for m in _PATTERNS_PRICE["iso_pre"].finditer(text):
        out.append((_to_float(m.group(2)), m.group(1).upper()))

    for m in _PATTERNS_PRICE["word_after"].finditer(text):
        ccy = _WORDS.get(m.group(2).lower(), None) or default_dollar
        out.append((_to_float(m.group(1)), ccy))

    for m in _PATTERNS_PRICE["iso_after"].finditer(text):
        out.append((_to_float(m.group(1)), _ISO_WORDS[m.group(2).lower()]))

    return [(a,c) for (a,c) in out if a >= 1]

def _parse_lowest_price(text: str, default_dollar: str) -> Optional[Dict[str, Any]]:
    prices = _gather_prices(text or "", default_dollar)
    if not prices: return None
    amt, ccy = min(prices, key=lambda t: t[0])
    return {"amount": round(amt, 2), "currency": ccy}

# ===================== FX helpers =====================
def _preferred_dollar(city_country_map: Dict[str,str], fx_meta_currency_by_country: Dict[str,str], city_a: str, city_b: str) -> str:
    for city in (city_a, city_b):
        ctry = (city_country_map or {}).get(city, "")
        ccy = (fx_meta_currency_by_country or {}).get(ctry)
        if ccy in ("USD","CAD","AUD","NZD","SGD"):
            return ccy
    return "USD"

def _convert_to_target(price: Optional[Dict[str, Any]], fx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not price or not fx:
        return None
    code = price.get("currency")
    amt  = price.get("amount")
    to_t = (fx.get("to_target") or {}).get(code)
    tgt  = fx.get("target")
    if to_t is None or tgt is None or amt is None:
        return None
    return {"amount": round(float(amt) * float(to_t), 2), "currency": tgt}

# ===================== Intent passthrough helpers =====================
def _pref_language(prefs: Dict[str, Any]) -> Optional[str]:
    lang = (prefs or {}).get("language")
    if isinstance(lang, str) and 1 <= len(lang) <= 10:
        return lang
    return None

def _lang_hint(lang: Optional[str]) -> str:
    return f" (prefer {lang} sources)" if lang else ""

def _with_kids(travelers: Optional[Dict[str,int]], prefs: Dict[str,Any]) -> bool:
    if prefs.get("kid_friendly") is True:
        return True
    try:
        return int((travelers or {}).get("children", 0) or 0) > 0
    except Exception:
        return False

def _tokens_from_prefs(mode: str, prefs: Dict[str, Any], musts: List[str], travelers: Optional[Dict[str,int]]) -> List[str]:
    toks: List[str] = []
    direct_only = bool(prefs.get("direct_only"))
    avoid_overnight = bool(prefs.get("avoid_overnight"))
    night_train = bool(prefs.get("night_train"))
    seat_class = (prefs.get("seat_class") or "").lower()
    baggage = prefs.get("baggage")
    month_hint = prefs.get("month_hint") or prefs.get("date_hint")
    language = _pref_language(prefs)
    kids = _with_kids(travelers, prefs)

    if month_hint: toks.append(str(month_hint))
    if language: toks.append(language)
    if kids: toks += ["family", "child fare"]

    if mode == "rail":
        ops = prefs.get("operators") or []
        if isinstance(ops, str): ops = [ops]
        tokens_ops = [str(x) for x in ops if str(x).strip()]
        toks += tokens_ops[:4]
        toks += ["high speed", "express", "fast"]
        if direct_only: toks.append("direct")
        if night_train and not avoid_overnight: toks += ["night train", "sleeper"]
        if seat_class: toks.append(seat_class)
    elif mode == "bus":
        lines = prefs.get("bus_lines") or []
        if isinstance(lines, str): lines = [lines]
        toks += [str(x) for x in lines if str(x).strip()][:4]
        if direct_only: toks.append("direct")
        if avoid_overnight: toks.append("no overnight")
        if seat_class: toks.append(seat_class)
    elif mode == "flight":
        airlines = prefs.get("airlines") or []
        if isinstance(airlines, str): airlines = [airlines]
        toks += [str(x) for x in airlines if str(x).strip()][:4]
        if direct_only: toks.append("nonstop")
        if baggage: toks.append("baggage included")
        if seat_class: toks.append(seat_class)

    toks += [m for m in musts if isinstance(m, str) and len(m.split()) <= 4]
    seen, out = set(), []
    for t in [x for x in toks if str(x).strip()]:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def _compose_queries_for_mode(a: str, b: str, mode: str, prefs: Dict[str,Any], musts: List[str],
                              travelers: Optional[Dict[str,int]], language: Optional[str],
                              max_variants: int) -> List[str]:
    base = {
        "rail":   f"train duration and price {a} to {b}",
        "bus":    f"bus duration and price {a} to {b}",
        "flight": f"flight duration and price {a} to {b}",
    }[mode]
    tok = _tokens_from_prefs(mode, prefs, musts, travelers)
    lang = _lang_hint(language)

    variants = [base + lang]
    if tok:
        chunks = [
            " ".join(tok[:4]).strip(),
            " ".join(tok[4:8]).strip(),
            " ".join(tok[8:12]).strip(),
        ]
        for ch in chunks:
            if ch:
                variants.append(f"{base} {ch}{lang}")

    seen, out = set(), []
    for q in variants:
        if q not in seen:
            seen.add(q); out.append(q)
        if len(out) >= max_variants:
            break
    return out

# ===================== API models =====================
class Money(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None

class ModeResult(BaseModel):
    duration_min: Optional[int] = None
    price: Optional[Money] = None
    price_target: Optional[Money] = None
    summary: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    note: Optional[str] = None

class HopResult(BaseModel):
    rail: ModeResult = Field(default_factory=ModeResult)
    bus: ModeResult = Field(default_factory=ModeResult)
    flight: ModeResult = Field(default_factory=ModeResult)
    recommended: Optional[str] = None

class IntercityDiscoveryArgs(BaseModel):
    cities: List[str]
    city_country_map: Optional[Dict[str, str]] = None

    fx: Optional[Dict[str, Any]] = None
    fx_target: Optional[str] = None
    fx_to_target: Optional[Dict[str, float]] = None

    preferences: Dict[str, Any] = Field(default_factory=dict)
    travelers: Optional[Dict[str, int]] = None
    musts: List[str] = Field(default_factory=list)
    modes_allow: Optional[List[str]] = None
    modes_deny: Optional[List[str]] = None

    max_results_per_query: int = Field(default=INTERCITY_RESULTS_PER_QUERY, ge=1, le=10)
    include_answer: bool = True
    max_query_variants: int = Field(default=int(os.getenv("INTERCITY_MAX_QUERY_VARIANTS", "4")), ge=1, le=8)
    sources_per_mode: int = Field(default=int(os.getenv("INTERCITY_SOURCES_PER_MODE", "4")), ge=1, le=10)

    longhaul_minutes: int = 300
    max_workers: int = Field(default=INTERCITY_HOP_WORKERS, ge=1, le=12)

    @field_validator("cities")
    @classmethod
    def _need_two(cls, v):
        if not v or len(v) < 2:
            raise ValueError("need at least 2 cities")
        return v

class IntercityDiscoveryResult(BaseModel):
    hops: Dict[str, HopResult] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)

# ===================== Tavily wrappers =====================
def _tavily() -> TavilyClient:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)

def _merge_answers_and_results(sr: Dict[str, Any], include_answer: bool) -> Tuple[str, List[str]]:
    answer = (sr.get("answer") or "") if include_answer else ""
    urls: List[str] = []
    for r in (sr.get("results") or []):
        u = (r.get("url") or "").strip()
        if u:
            urls.append(u)
    return (answer or ""), urls

def _search_and_collect(tv: TavilyClient, queries: List[str], max_results: int, include_answer: bool) -> Tuple[str, List[str], List[str]]:
    """
    Run several variant queries in PARALLEL; return combined answers text, combined snippets (titles+contents),
    and a de-duped URL list (in order).
    """
    answers: List[str] = []
    snippets: List[str] = []
    urls: List[str] = []
    seen_urls = set()

    def _run(q: str) -> Dict[str, Any]:
        return tv.search(
            q,
            max_results=max_results,
            include_answer=include_answer,
            search_depth=INTERCITY_SEARCH_DEPTH,
            include_raw_content=INTERCITY_INCLUDE_RAW,
        ) or {}

    with ThreadPoolExecutor(max_workers=min(INTERCITY_QUERY_WORKERS, max(1, len(queries)))) as pool:
        futs = {pool.submit(_run, q): q for q in queries}
        for fut in as_completed(futs):
            sr = fut.result()
            ans, ulist = _merge_answers_and_results(sr, include_answer)
            if ans: answers.append(ans)

            for u in ulist:
                if u not in seen_urls:
                    seen_urls.add(u); urls.append(u)

            for r in (sr.get("results") or []):
                title = (r.get("title") or "").strip()
                content = (r.get("content") or "").strip()
                if title: snippets.append(title)
                if content: snippets.append(content)

    return ("  ".join(answers).strip()), snippets, urls

def _parse_mode_from_blobs(answer_text: str, snippets: List[str], default_dollar: str) -> Tuple[Optional[int], Optional[Dict[str,Any]], Optional[str]]:
    dur = _parse_best_duration_minutes(answer_text)
    price = _parse_lowest_price(answer_text, default_dollar)
    if dur is None or price is None:
        blob = "  ".join([answer_text] + snippets)
        if dur is None:
            dur = _parse_best_duration_minutes(blob)
        if price is None:
            price = _parse_lowest_price(blob, default_dollar)
    summary = (answer_text[:240] or None) if answer_text else None
    return dur, price, summary

# Soft prioritization of “officialish” transport sources
_OFFICIALISH_TOKENS = (
    "gov", "gouv", "go.jp", "rail", "metro", "transport", "transit", "tram",
    "airlines", "airport", "trenitalia", "italo", "sncf", "db", "renfe", "jr-",
    "jrpass", "jrrail", "amtrak", "eurostar", "tfl", "rta", "mta", "cta", "sbb",
    "nre", "bahn", "renfe", "via-rail"
)
def _officialish(u: str) -> bool:
    lo = (u or "").lower()
    return any(tok in lo for tok in _OFFICIALISH_TOKENS)

# ===================== Main tool =====================
def intercity_discovery_tool(args: IntercityDiscoveryArgs) -> IntercityDiscoveryResult:
    logs: List[str] = []
    errors: List[Dict[str, str]] = []

    try:
        tv = _tavily()
    except Exception as e:
        errors.append({"stage": "init", "message": str(e)})
        return IntercityDiscoveryResult(logs=logs, errors=errors)

    fx = args.fx or {}
    if (not fx) and (args.fx_target and args.fx_to_target):
        fx = {"target": args.fx_target, "to_target": args.fx_to_target}

    all_modes = ["rail","bus","flight"]
    allow = set([m for m in (args.modes_allow or all_modes) if m in all_modes])
    deny  = set([m for m in (args.modes_deny  or []) if m in all_modes])
    run_modes = [m for m in all_modes if (m in allow) and (m not in deny)]

    cities = list(args.cities)
    hops = [(cities[i], cities[i+1]) for i in range(len(cities)-1)]
    out: Dict[str, HopResult] = {}

    language = _pref_language(args.preferences)

    def _process_hop(a: str, b: str) -> Tuple[str, HopResult]:
        hop_key = f"{a} -> {b}"
        res = HopResult()
        dollar_ccy = _preferred_dollar(args.city_country_map or {}, (fx.get("currency_by_country") or (args.fx or {}).get("currency_by_country") or {}), a, b)

        def _run_mode(mode: str) -> ModeResult:
            queries = _compose_queries_for_mode(
                a=a, b=b, mode=mode, prefs=args.preferences, musts=args.musts,
                travelers=args.travelers, language=language, max_variants=args.max_query_variants
            )
            answer_text, snippets, urls = _search_and_collect(
                tv, queries, max_results=args.max_results_per_query, include_answer=args.include_answer
            )

            # Prioritize officialish sources before trimming to N
            urls = sorted(dict.fromkeys(urls), key=lambda u: (0 if _officialish(u) else 1, u))
            urls = urls[: args.sources_per_mode]

            dur, price_native, summary = _parse_mode_from_blobs(answer_text, snippets, dollar_ccy)
            price_target = _convert_to_target(price_native, fx) if price_native else None

            note_bits = ["tavily.search multi-variant"]
            if args.preferences.get("direct_only"): note_bits.append("direct_only")
            if args.preferences.get("night_train"): note_bits.append("night_train")
            if args.preferences.get("avoid_overnight"): note_bits.append("avoid_overnight")
            if language: note_bits.append(f"lang:{language}")

            return ModeResult(
                duration_min=dur,
                price=(None if price_native is None else Money(**price_native)),
                price_target=(None if price_target is None else Money(**price_target)),
                summary=summary,
                sources=urls,
                note="; ".join(note_bits)
            )

        mode_payloads: Dict[str, ModeResult] = {}
        with ThreadPoolExecutor(max_workers=min(3, len(run_modes) or 1)) as pool:
            futs = {pool.submit(_run_mode, m): m for m in run_modes}
            for fut in as_completed(futs):
                m = futs[fut]
                try:
                    mode_payloads[m] = fut.result()
                except Exception as e:
                    logs.append(f"Intercity[{hop_key}] mode={m} error: {e}")
                    mode_payloads[m] = ModeResult(note="error")

        if "rail"   in mode_payloads: res.rail   = mode_payloads["rail"]
        if "bus"    in mode_payloads: res.bus    = mode_payloads["bus"]
        if "flight" in mode_payloads: res.flight = mode_payloads["flight"]

        best_mode = None
        best_dur = None
        for mode_name, mode_res in (("rail",res.rail),("bus",res.bus),("flight",res.flight)):
            if mode_res.duration_min is not None and (best_dur is None or mode_res.duration_min < best_dur):
                best_dur, best_mode = mode_res.duration_min, mode_name

        flight_dur = res.flight.duration_min if "flight" in run_modes else None
        is_longhaul = (flight_dur is not None and flight_dur >= int(args.longhaul_minutes))
        if is_longhaul:
            if "rail" in run_modes:
                res.rail   = ModeResult(summary="Suppressed on long-haul hop; use flight.", note="suppressed_long_haul")
            if "bus" in run_modes:
                res.bus    = ModeResult(summary="Suppressed on long-haul hop; use flight.", note="suppressed_long_haul")
            best_mode = "flight"

        res.recommended = best_mode or ("flight" if is_longhaul else "unknown")
        logs.append(
            f"Intercity[{hop_key}]: rail={res.rail.duration_min}m, "
            f"bus={res.bus.duration_min}m, flight={res.flight.duration_min}m → {res.recommended}"
            + (" (long-haul)" if is_longhaul else "")
        )
        return hop_key, res

    max_workers = min(int(args.max_workers), len(hops) or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_process_hop, a, b): (a, b) for a, b in hops}
        for fut in as_completed(futs):
            hop_key, payload = fut.result()
            out[hop_key] = payload

    return IntercityDiscoveryResult(hops=out, logs=logs, errors=errors)

# ===================== OpenAI tool schema (optional) =====================
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "intercity_discovery_tool",
        "description": "Discover rail/bus/flight duration and prices between consecutive cities using Tavily only. Honors preferences (direct/ops/lines/airlines/night-train/language) and musts via multi-variant search.",
        "parameters": {
            "type": "object",
            "properties": {
                "cities": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Ordered list of cities; consecutive pairs form hops."
                },
                "city_country_map": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Map city -> country (used to disambiguate '$' currency)."
                },
                "fx": {"type": "object"},
                "fx_target": {"type": "string"},
                "fx_to_target": {"type": "object", "additionalProperties": {"type": "number"}},
                "preferences": {"type": "object", "additionalProperties": True},
                "travelers": {"type": "object", "additionalProperties": {"type":"integer"}},
                "musts": {"type": "array", "items": {"type": "string"}},
                "modes_allow": {"type": "array", "items": {"type": "string"}},
                "modes_deny": {"type": "array", "items": {"type": "string"}},
                "max_results_per_query": {"type": "integer", "minimum": 1, "maximum": 10},
                "include_answer": {"type": "boolean"},
                "max_query_variants": {"type": "integer", "minimum": 1, "maximum": 8},
                "sources_per_mode": {"type": "integer", "minimum": 1, "maximum": 10},
                "longhaul_minutes": {"type": "integer", "minimum": 60, "maximum": 1440},
                "max_workers": {"type": "integer", "minimum": 1, "maximum": 12}
            },
            "required": ["cities"]
        }
    }
}

# ===================== CLI tests =====================
def _pp_money(m: Optional[Money]) -> str:
    if not m or m.amount is None: return "—"
    return f"{m.amount:.2f} {m.currency or ''}".strip()

def _print_result(name: str, out: IntercityDiscoveryResult, t0: float) -> None:
    took = time.time() - t0
    print(f"\n===== {name} =====")
    print(f"took: {took:.2f}s")
    if out.errors:
        print("errors:", out.errors)
    for hop, res in out.hops.items():
        print(f"\n  {hop}")
        print(f"    rail:   {res.rail.duration_min} min | price: {_pp_money(res.rail.price)} | target: {_pp_money(res.rail.price_target)}")
        print(f"            sources: {res.rail.sources}")
        print(f"    bus:    {res.bus.duration_min} min | price: {_pp_money(res.bus.price)} | target: {_pp_money(res.bus.price_target)}")
        print(f"            sources: {res.bus.sources}")
        print(f"    flight: {res.flight.duration_min} min | price: {_pp_money(res.flight.price)} | target: {_pp_money(res.flight.price_target)}")
        print(f"            sources: {res.flight.sources}")
        print(f"    → recommended: {res.recommended}")

if __name__ == "__main__":
    tests = [
        {
            "name": "Rome → Florence (rail/bus/flight)",
            "args": IntercityDiscoveryArgs(
                cities=["Rome", "Florence"],
                city_country_map={"Rome":"Italy","Florence":"Italy"},
                preferences={"language":"en","operators":["Trenitalia","Italo"], "direct_only": True},
                max_results_per_query=INTERCITY_RESULTS_PER_QUERY,
                include_answer=True,
            ),
        },
        {
            "name": "Tokyo → Kyoto (rail focus)",
            "args": IntercityDiscoveryArgs(
                cities=["Tokyo", "Kyoto"],
                city_country_map={"Tokyo":"Japan","Kyoto":"Japan"},
                preferences={"language":"en","operators":["JR"], "seat_class":"economy"},
                modes_allow=["rail","flight"],
                max_results_per_query=INTERCITY_RESULTS_PER_QUERY,
            ),
        },
        {
            "name": "London → Paris (rail/flight)",
            "args": IntercityDiscoveryArgs(
                cities=["London","Paris"],
                city_country_map={"London":"United Kingdom","Paris":"France"},
                preferences={"language":"en","operators":["Eurostar"], "direct_only": True},
                modes_allow=["rail","flight"],
            ),
        },
        {
            "name": "Los Angeles → San Francisco (all modes)",
            "args": IntercityDiscoveryArgs(
                cities=["Los Angeles","San Francisco"],
                city_country_map={"Los Angeles":"United States","San Francisco":"United States"},
                preferences={"language":"en"},
            ),
        },
    ]

    for t in tests:
        start = time.time()
        result = intercity_discovery_tool(t["args"])
        _print_result(t["name"], result, start)
