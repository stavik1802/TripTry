"""
Currency Tool for TripPlanner Multi-Agent System

This tool provides real-time currency exchange rates and conversion capabilities
for international trip planning. It fetches current exchange rates and enables
accurate cost calculations across different currencies.

Key features:
- Real-time currency exchange rate fetching
- Multi-currency support with parallel processing
- Country-to-currency mapping
- Exchange rate validation and normalization
- Configurable search parameters for speed optimization

The tool ensures accurate currency conversions for international trips,
enabling realistic budget planning across different countries and currencies.
"""

from __future__ import annotations
import os, re, time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

# External deps
from tavily import TavilyClient
try:
    from openai import OpenAI  # not used (kept for parity/future)
except Exception:
    OpenAI = None


# ========================== Config ==========================
BASE = os.getenv("FX_BASE", "USD")  # spot lookups are BASE->CODE (default USD)

# Tavily knobs (set for speed; override via ENV if needed)
FX_SEARCH_MAX_RESULTS   = int(os.getenv("FX_SEARCH_MAX_RESULTS", "3"))
FX_SEARCH_DEPTH         = os.getenv("FX_SEARCH_DEPTH", "basic")  # "basic" or "advanced"
FX_INCLUDE_RAW_CONTENT  = os.getenv("FX_INCLUDE_RAW_CONTENT", "false").lower() == "true"

# Parallelism
FX_COUNTRY_WORKERS      = int(os.getenv("FX_COUNTRY_WORKERS", "8"))
FX_RATE_WORKERS         = int(os.getenv("FX_RATE_WORKERS", "8"))

# ========================== Regex helpers ==========================
DEC  = re.compile(r"\b\d+\.\d+\b")     # decimal like 147.68
CAP3 = re.compile(r"\b[A-Z]{3}\b")     # 3-letter all caps
STOPWORDS3 = {"THE","AND","ARE","FOR","HAS","WAS","ITS","YOU","NOT","BUT","HER","HIS","SHE","HIM","OUR","ONE"}


# ========================== Pydantic schemas ==========================
class CountryArg(BaseModel):
    """Accepts {'country': 'Japan'} or {'name': 'Japan'}; cities ignored."""
    country: Optional[str] = None
    name: Optional[str] = None

    @property
    def norm_country(self) -> Optional[str]:
        return (self.country or self.name or "").strip() or None

class FxOracleArgs(BaseModel):
    """Inputs to the FX tool."""
    countries: List[CountryArg] = Field(
        default_factory=list,
        description="Countries to infer native currencies from."
    )
    city_country_map: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional {city: country} map to augment country set."
    )
    target_currency: Optional[str] = Field(
        default=None,
        description="If provided and looks like ISO-4217 (AAA), use it as display currency."
    )
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            'May include {"currency":"USD","language":"en",'
            '"rates_for":["JPY","EUR"], "include_codes":["CHF"], "extra_codes":["AUD"], "fx_codes":["CAD"]}.'
        )
    )
    musts: List[str] = Field(default_factory=list)

class FxOracleResult(BaseModel):
    """
    Output of the FX tool. Fields may be None when missing/ambiguous.
    """
    provider: Optional[str] = None
    as_of: Optional[str] = None
    base: Optional[str] = None
    target: Optional[str] = None
    rates: Optional[Dict[str, float]] = None      # {CODE: base_to_code}
    to_target: Optional[Dict[str, float]] = None  # {CODE: code_to_target}
    note: Optional[str] = None
    currency_by_country: Optional[Dict[str, str]] = None
    errors: List[Dict[str, str]] = Field(default_factory=list)

    def ok(self) -> bool:
        return bool(self.rates) and bool(self.to_target) and not self.errors


# ========================== Small utils ==========================
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _tavily() -> TavilyClient:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)

def _countries_from_args(args: FxOracleArgs) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in args.countries or []:
        nm = c.norm_country
        if nm and nm not in seen:
            seen.add(nm); out.append(nm)
    for nm in (args.city_country_map or {}).values():
        nm = (nm or "").strip()
        if nm and nm not in seen:
            seen.add(nm); out.append(nm)
    return out

def _valid_iso3(tok: str) -> bool:
    return bool(tok) and CAP3.fullmatch(tok.upper()) is not None

def _pref_language(prefs: Dict[str, Any]) -> Optional[str]:
    lang = (prefs or {}).get("language")
    if isinstance(lang, str) and 1 <= len(lang) <= 10:
        return lang
    return None

def _tavily_answer(tv: TavilyClient, q: str) -> str:
    sr = tv.search(
        q,
        max_results=FX_SEARCH_MAX_RESULTS,
        include_answer=True,
        search_depth=FX_SEARCH_DEPTH,
        include_raw_content=FX_INCLUDE_RAW_CONTENT,
    ) or {}
    return (sr.get("answer") or "").strip()

def _pick_iso3_from_text(text: str) -> str:
    """
    Heuristic ISO-4217 code picker (no whitelist).
    """
    if not text:
        raise ValueError("empty answer")
    up = text.upper()

    candidates: List[Tuple[str, int]] = [(m.group(0), m.start()) for m in CAP3.finditer(up)]
    if not candidates:
        raise ValueError("no ALL-CAPS 3-letter tokens found")

    def _poses(pattern: str) -> List[int]:
        return [m.start() for m in re.finditer(pattern, up)]

    pos_iso  = _poses(r"\bISO\b|\b4217\b")
    pos_code = _poses(r"\bCODE\b")
    pos_curr = _poses(r"\bCURRENCY\b|\bOFFICIAL\b")

    best_tok, best_score, best_idx = None, -1e9, 10**9
    for tok, idx in candidates:
        score = 0.0
        if idx > 0 and idx+3 < len(up) and up[idx-1] == "(" and up[idx+3:idx+4] == ")":
            score += 3.0
        if any(0 <= idx - p <= 40 for p in pos_iso):  score += 3.0
        if any(0 <= idx - p <= 30 for p in pos_code): score += 2.0
        if any(0 <= idx - p <= 30 for p in pos_curr): score += 1.0
        if tok in STOPWORDS3: score -= 2.0
        if score > best_score or (score == best_score and idx < best_idx):
            best_tok, best_score, best_idx = tok, score, idx

    if best_tok is None or best_score < -1.0:
        raise ValueError("could not confidently select ISO code")
    return best_tok

def _parse_float_base_to_code(text: str, code: str) -> float:
    """
    Parse BASE->CODE rate from Tavily answer text.
    Requires a decimal with period. Rejects 1.0 for non-BASE codes.
    """
    m = DEC.search((text or "").strip())
    if not m:
        raise ValueError("no decimal number with a period found in answer")
    val = float(m.group(0))
    if code != BASE and abs(val - 1.0) < 1e-9:
        raise ValueError("implausible 1.0 rate for non-base code")
    if val <= 0:
        raise ValueError("non-positive rate")
    return val

def _codes_from_musts_and_prefs(musts: List[str], prefs: Dict[str, Any]) -> List[str]:
    """Collect extra ISO codes the user implicitly/explicitly wants covered."""
    buckets = []
    for k in ("rates_for","include_codes","extra_codes","fx_codes"):
        v = (prefs or {}).get(k)
        if isinstance(v, str): buckets.append([v])
        elif isinstance(v, list): buckets.append([str(x) for x in v])
    buckets.append(musts or [])
    flat = [s.strip().upper() for bucket in buckets for s in (bucket or []) if isinstance(s, (str,))]
    return [c for c in flat if _valid_iso3(c)]

def _pick_target(args: FxOracleArgs, inferred_codes: List[str], extra_codes: List[str]) -> Optional[str]:
    """
    Priority:
      1) args.target_currency if ISO3
      2) preferences.currency if ISO3
      3) first valid ISO3 present in musts/extra codes (user intent)
      4) if exactly one unique inferred code, use it
      5) fallback to BASE
    """
    t = (args.target_currency or "").strip().upper()
    if _valid_iso3(t):
        return t
    pref = ((args.preferences or {}).get("currency") or "").strip().upper()
    if _valid_iso3(pref):
        return pref
    for cand in extra_codes:
        if _valid_iso3(cand):
            return cand
    uniq = sorted({c for c in inferred_codes if _valid_iso3(c)})
    if len(uniq) == 1:
        return uniq[0]
    return BASE


# ========================== Tool (pure) ==========================
def fx_oracle_tool(args: FxOracleArgs) -> FxOracleResult:
    """
    Tavily-only FX oracle (fast + parallel).
    - Country → ISO code: parallel
    - BASE→CODE spot rates: parallel
    - Returns None fields + errors when ambiguous/missing
    """
    t_start = time.time()
    result = FxOracleResult(provider="tavily-answer", base=BASE)
    errors: List[Dict[str, str]] = []

    # Ensure API key
    try:
        tv = _tavily()
    except Exception as e:
        errors.append({"stage": "init", "message": str(e)})
        result.as_of = _utc_now_iso()
        result.errors = errors
        return result

    lang = _pref_language(args.preferences)

    # Countries
    countries = _countries_from_args(args)
    if not countries:
        errors.append({"stage": "input", "message": "countries or city_country_map required"})
        result.as_of = _utc_now_iso()
        result.errors = errors
        return result

    # 1) Country -> ISO code (parallel)
    currency_by_country: Dict[str, str] = {}

    def _lookup_currency(country: str) -> Tuple[str, Optional[str], Optional[str]]:
        try:
            q = f"What is the official currency of {country}? Return the ISO 4217 3-letter code in your answer."
            if lang:
                q += f" Answer in {lang}."
            ans = _tavily_answer(tv, q)
            code = _pick_iso3_from_text(ans)
            return country, code, None
        except Exception as e:
            return country, None, str(e)

    with ThreadPoolExecutor(max_workers=min(FX_COUNTRY_WORKERS, max(1, len(countries)))) as pool:
        futs = {pool.submit(_lookup_currency, c): c for c in countries}
        for fut in as_completed(futs):
            c, code, err = fut.result()
            if code:
                currency_by_country[c] = code
            else:
                errors.append({"stage": "currency_lookup", "country": c, "message": err or "unknown error"})

    if errors:
        result.as_of = _utc_now_iso()
        result.currency_by_country = currency_by_country or None
        result.note = "FX unavailable due to currency_lookup errors."
        result.errors = errors
        return result

    # 2) Pick target currency
    inferred_codes = list(currency_by_country.values())
    extra_codes = _codes_from_musts_and_prefs(args.musts, args.preferences)
    target = _pick_target(args, inferred_codes, extra_codes)
    if not _valid_iso3(target):
        errors.append({"stage": "target_pick", "message": f"invalid target '{target}'"})
        result.as_of = _utc_now_iso()
        result.currency_by_country = currency_by_country
        result.target = target
        result.errors = errors
        return result
    result.target = target

    # 3) Build list of codes we need rates for
    needed = sorted({BASE, target, *inferred_codes, *extra_codes})
    rates: Dict[str, float] = {BASE: 1.0}

    def _lookup_rate(code: str) -> Tuple[str, Optional[float], Optional[str]]:
        if code == BASE:
            return code, 1.0, None
        try:
            q = f"What is the current exchange rate from {BASE} to {code}? Return only a decimal number or a phrase containing a decimal."
            if lang:
                q += f" Answer in {lang}."
            ans = _tavily_answer(tv, q)
            val = _parse_float_base_to_code(ans, code)
            return code, val, None
        except Exception as e:
            return code, None, str(e)

    # 4) Parallel spot-rate lookups
    with ThreadPoolExecutor(max_workers=min(FX_RATE_WORKERS, max(1, len(needed)))) as pool:
        futs = {pool.submit(_lookup_rate, c): c for c in needed}
        for fut in as_completed(futs):
            code, val, err = fut.result()
            if val is not None:
                rates[code] = float(f"{val:.8f}")
            elif err:
                errors.append({"stage": "rate_lookup", "code": code, "message": err})

    if errors:
        result.as_of = _utc_now_iso()
        result.currency_by_country = currency_by_country
        result.target = target
        result.note = "FX unavailable due to rate_lookup errors."
        result.errors = errors
        return result

    # 5) Build code->target multipliers
    r_t = rates.get(target, 1.0 if target == BASE else None)
    if r_t is None:
        errors.append({"stage": "convert", "message": f"Missing {BASE}→{target} rate"})
        result.as_of = _utc_now_iso()
        result.currency_by_country = currency_by_country
        result.errors = errors
        return result

    to_target: Dict[str, float] = {}
    for code in needed:
        if code == target:
            to_target[code] = 1.0
        elif code == BASE:
            to_target[code] = float(f"{r_t:.8f}")  # BASE→target
        else:
            r_x = rates.get(code)
            if r_x is None or r_x <= 0:
                errors.append({"stage": "convert", "message": f"Missing {BASE}→{code} rate"})
                break
            to_target[code] = float(f"{(r_t / r_x):.8f}")

    result.as_of = _utc_now_iso()
    result.rates = rates if not errors else None
    result.to_target = to_target if not errors else None
    result.currency_by_country = currency_by_country
    result.note = f"Convert with: amount_in_CODE * to_target[CODE] -> amount_in_{target}."
    result.errors = errors
    return result


# ========================== OpenAI tool schema (optional) ==========================
OPENAI_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "fx_oracle_tool",
        "description": "Infer native currencies for countries and fetch BASE→CODE spot rates via Tavily. Honors target_currency, language preference, musts, and preferences.*codes. No fallbacks; returns None fields + errors when ambiguous/missing.",
        "parameters": {
            "type": "object",
            "properties": {
                "countries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"country": {"type": "string"}, "name": {"type": "string"}}
                    }
                },
                "city_country_map": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                },
                "target_currency": {"type": "string"},
                "preferences": {"type": "object"},
                "musts": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}


# ========================== CLI: quick tests ==========================
def _print_fx(name: str, out: FxOracleResult, started_at: float) -> None:
    took = time.time() - started_at
    print(f"\n===== {name} =====")
    print(f"took: {took:.2f}s")
    print("ok?:", out.ok())
    print("as_of:", out.as_of)
    print("base:", out.base, "target:", out.target)
    print("currency_by_country:", out.currency_by_country)
    if out.rates:
        # show a few
        sample = dict(list(out.rates.items())[:6])
        print("rates sample:", sample)
    if out.to_target:
        sample = dict(list(out.to_target.items())[:6])
        print("to_target sample:", sample)
    if out.errors:
        print("errors:", out.errors)


if __name__ == "__main__":
    # Set env for speed testing, if you want (optional):
    # os.environ["FX_SEARCH_DEPTH"] = "basic"
    # os.environ["FX_COUNTRY_WORKERS"] = "8"
    # os.environ["FX_RATE_WORKERS"] = "8"
    # os.environ["FX_SEARCH_MAX_RESULTS"] = "3"

    tests = [
        {
            "name": "Japan + USA → target USD",
            "args": FxOracleArgs(
                countries=[CountryArg(country="Japan"), CountryArg(country="United States")],
                city_country_map={"Tokyo": "Japan", "New York": "United States"},
                target_currency="USD",
                preferences={"language": "en"},
            ),
        },
        {
            "name": "Spain + Italy → auto target",
            "args": FxOracleArgs(
                countries=[CountryArg(country="Spain"), CountryArg(country="Italy")],
                preferences={"language": "en", "rates_for": ["GBP"]},  # add extra code so GBP is covered
            ),
        },
        {
            "name": "France only, must CHF included, target from prefs",
            "args": FxOracleArgs(
                countries=[CountryArg(country="France")],
                preferences={"currency": "EUR", "language": "en"},
                musts=["CHF"],
            ),
        },
    ]

    for t in tests:
        t0 = time.time()
        out = fx_oracle_tool(t["args"])
        _print_fx(t["name"], out, t0)
