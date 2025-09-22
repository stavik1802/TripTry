"""
Gap Data Tool for TripPlanner Multi-Agent System

This tool identifies and fills missing data gaps in trip planning research by using
web search and AI to find information that wasn't discovered by other tools.
It searches for missing POIs, restaurants, fares, and other travel-related data.

Key features:
- Web search integration using Tavily API
- AI-powered data extraction and structuring
- Configurable search parameters via environment variables
- Automatic data validation and normalization
- Patch generation for seamless data integration

The tool helps ensure comprehensive trip data by filling gaps that other
discovery tools might have missed, improving the overall quality of trip plans.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from copy import deepcopy
import json, os, re

# ================= Env knobs (tiny, safe) =================
MAX_RESULTS_PER_QUERY = int(os.getenv("GAP_MAX_RESULTS_PER_QUERY", "1"))  # stick to 1
INCLUDE_ANSWER        = os.getenv("GAP_INCLUDE_ANSWER", "1") == "1"       # use Tavily's answer blob
SEARCH_DEPTH          = os.getenv("GAP_SEARCH_DEPTH", "basic")            # keep "basic" (cheap)
TAVILY_TOPIC          = os.getenv("GAP_TAVILY_TOPIC", "general")

# ================= Clients =================
from tavily import TavilyClient
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"{name} not set")
    return v

def _openai_client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("openai package not available")
    return OpenAI(api_key=_require_env("OPENAI_API_KEY"))

def _tavily_client() -> TavilyClient:
    return TavilyClient(api_key=_require_env("TAVILY_API_KEY"))

# ================= Datatypes =================
@dataclass
class MissingItem:
    path: str
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    schema: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    allow_source_patch: bool = True

@dataclass
class GapFillerArgs:
    message: str
    request_snapshot: Dict[str, Any]
    missing: List[MissingItem]
    # we will hard-cap to 1 query per item; keep args for API compatibility
    max_queries_per_item: int = 1
    max_results_per_query: int = MAX_RESULTS_PER_QUERY
    model_for_queries: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    model_for_extract: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

@dataclass
class GapFillerItemResult:
    path: str
    value: Any
    sources: List[str]

@dataclass
class GapFillerResult:
    items: List[GapFillerItemResult] = field(default_factory=list)
    patches: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

# ================ Simple dotted patcher ================
def _apply_patch_path(root: Dict[str, Any], dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    cur = root
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value

def apply_patches(root: Dict[str, Any], patches: Dict[str, Any]) -> None:
    for path, val in patches.items():
        _apply_patch_path(root, path, val)

# ================ Minimal money coercion ================
def _is_money_schema(schema: Optional[str]) -> bool:
    if not schema:
        return False
    try:
        sch = json.loads(schema)
    except Exception:
        return False
    props = (sch.get("properties") or {})
    return isinstance(props, dict) and "amount" in props and "currency" in props

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
SYM_TO_ISO = {"¥":"JPY","€":"EUR","$":"USD","£":"GBP"}
WORD_TO_ISO = {
    "yen":"JPY","jpy":"JPY",
    "eur":"EUR","euro":"EUR","euros":"EUR",
    "usd":"USD","dollar":"USD","dollars":"USD",
    "gbp":"GBP","pound":"GBP","pounds":"GBP",
}

def _norm_amount(val: Any) -> Optional[float]:
    if isinstance(val, (int, float)): return float(val)
    if not isinstance(val, str): return None
    m = NUM_RE.search(val); 
    if not m: return None
    s = m.group(0)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    try: return float(s)
    except: return None

def _norm_currency(val: Any) -> Optional[str]:
    if val is None: return None
    s = str(val).strip()
    for sym, iso in SYM_TO_ISO.items():
        if sym in s: return iso
    low = s.lower()
    return WORD_TO_ISO.get(low, s.upper()[:3])

def _coerce_money(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return {"amount": _norm_amount(value.get("amount")), "currency": _norm_currency(value.get("currency"))}
    return {"amount": _norm_amount(value), "currency": _norm_currency(value)}

# ================ Prompts =================
_Q_SYS = "Return strict JSON only. No commentary."
_Q_USER = (
    "Generate ONE focused web search query to recover a missing field.\n"
    "Return JSON: {{\"query\": \"...\"}}\n"
    "Rules:\n"
    "- ≤ 12 words, include strong disambiguators (city, country, venue/name).\n"
    "- Prefer official sources when applicable (authority, museum, transit operator).\n"
    "- If price-related include 'price'/'fare'/'tariff'/'admission'. If hours, include 'hours'.\n"
    "- No URLs. No prose.\n\n"
    "Context\n"
    "- Path: {path}\n"
    "- Description: {desc}\n"
    "- Hints: {hints}\n"
    "- JSON Context: {ctx}\n"
    "- User message (optional): {message}\n"
)

_E_SYS = "Return strict JSON only. No commentary."
_E_USER_GENERIC = (
    "Extract exactly one value for a missing field in a travel plan.\n"
    "Field: {path}\n"
    "Description: {desc}\n"
    "Context JSON: {ctx}\n"
    "Return JSON: {{\"value\": <single value>}}\n"
    "Avoid ranges and avoid prose.\n\n"
    "SOURCES:\n{sources}\n\n"
    "EXCERPTS:\n{excerpts}\n"
)

_E_USER_MONEY = (
    "Extract exactly one monetary value for a missing field in a travel plan.\n"
    "Field: {path}\n"
    "Description: {desc}\n"
    "Context JSON: {ctx}\n"
    "Return JSON: {{\"value\": {{\"amount\": <number>, \"currency\": \"ISO-4217\"}}}}\n"
    "Avoid ranges and prose. Convert symbols/words (e.g., 'yen') to ISO (e.g., 'JPY').\n\n"
    "SOURCES:\n{sources}\n\n"
    "EXCERPTS:\n{excerpts}\n"
)


# ================ Per-item worker (sequential, one Tavily call) ================
def _process_item_basic(item: MissingItem, args: GapFillerArgs, oa: OpenAI, tv: TavilyClient) -> Tuple[str, Any, List[str]]:
    # 1) LLM → ONE query
    q_prompt = _Q_USER.format(
        path=item.path,
        desc=item.description,
        hints=", ".join(item.hints or []),
        ctx=json.dumps(item.context, ensure_ascii=False),
        message=(args.message or "")[:500],
    )
    q_resp = oa.chat.completions.create(
        model=args.model_for_queries,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _Q_SYS},
                  {"role": "user", "content": q_prompt}],
    )
    try:
        query = json.loads(q_resp.choices[0].message.content).get("query", "")
    except Exception:
        query = ""
    if not query:
        return (item.path, None, [])
    # 2) Single Tavily search (basic, cheap)
    sr = tv.search(
        query,
        include_answer=INCLUDE_ANSWER,
        max_results=MAX_RESULTS_PER_QUERY,
        search_depth=SEARCH_DEPTH,
        topic=TAVILY_TOPIC,
        timeout=20,
        auto_parameters=False,  # avoid any auto-upgrade
    ) or {}
    urls: List[str] = []
    for r in (sr.get("results") or []):
        u = (r.get("url") or "").strip()
        if u:
            urls.append(u)
    urls = urls[:MAX_RESULTS_PER_QUERY]  # 0 or 1

    # Build tiny blob for extraction (answer + first snippet)
    excerpts_parts: List[str] = []
    ans = (sr.get("answer") or "").strip()
    if ans:
        excerpts_parts.append(f"--- about:answer ---\n{ans[:4000]}")
    if sr.get("results"):
        r0 = sr["results"][0]
        title = (r0.get("title") or "").strip()
        cont  = (r0.get("content") or "").strip()
        if title or cont:
            snippets = (title + "\n" + cont).strip()
            excerpts_parts.append(f"--- {urls[0] if urls else 'about:first'} ---\n{snippets[:4000]}")

    excerpts = "\n\n".join(excerpts_parts)[:8000]

    # 3) LLM extraction
    tpl = _E_USER_MONEY if _is_money_schema(item.schema) else _E_USER_GENERIC
    e_prompt = tpl.format(
        path=item.path,
        desc=item.description,
        ctx=json.dumps(item.context, ensure_ascii=False),
        sources="\n".join(f"- {u}" for u in urls),
        excerpts=excerpts,
    )
    e_resp = oa.chat.completions.create(
        model=args.model_for_extract,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _E_SYS},
                  {"role": "user", "content": e_prompt}],
    )
    try:
        value = json.loads(e_resp.choices[0].message.content).get("value", None)
    except Exception:
        value = None

    if _is_money_schema(item.schema):
        value = _coerce_money(value)

    return (item.path, value, urls)

# ================ Runner =================
def run_search_only(args: GapFillerArgs) -> GapFillerResult:
    res = GapFillerResult()
    oa = _openai_client()
    tv = _tavily_client()

    # Sequential over items: exactly one Tavily call per item
    for item in args.missing:
        try:
            path, value, srcs = _process_item_basic(item, args, oa, tv)
        except Exception as e:
            res.errors.append({"where": "item", "message": str(e)})
            continue
        res.items.append(GapFillerItemResult(path=path, value=value, sources=srcs))
        res.patches[path] = value
        if srcs:
            # Keep sibling source for scalars; nested for dict money values
            if isinstance(value, dict):
                res.patches[f"{path}.__sources"] = srcs
            else:
                res.patches[f"{path}__sources"] = srcs
    return res

# ================ Public wrapper (unchanged API) =================
def fill_gaps_search_only(args_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    message = args_dict.get("message") or ""
    req = deepcopy(args_dict.get("request_snapshot") or {})

    missing_items: List[MissingItem] = []
    for m in (args_dict.get("missing") or []):
        missing_items.append(MissingItem(
            path=m["path"],
            description=m["description"],
            context=m.get("context") or {},
            schema=m.get("schema"),
            hints=m.get("hints") or [],
            allow_source_patch=bool(m.get("allow_source_patch", True)),
        ))

    gf_args = GapFillerArgs(
        message=message,
        request_snapshot=req,
        missing=missing_items,
        max_queries_per_item=1,
        max_results_per_query=MAX_RESULTS_PER_QUERY,
    )

    result = run_search_only(gf_args)
    patched = deepcopy(req)
    apply_patches(patched, result.patches)

    result_dict = {
        "items": [dict(path=i.path, value=i.value, sources=i.sources) for i in result.items],
        "patches": result.patches,
        "logs": result.logs,
        "errors": result.errors,
    }
    return result_dict, patched
