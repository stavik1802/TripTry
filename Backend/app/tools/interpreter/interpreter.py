"""
AI-Powered Request Interpreter for TripPlanner Multi-Agent System

This tool interprets natural language user requests and converts them into structured
data that the multi-agent system can process. It classifies user intent, extracts
key information, and determines which tools should be used for the request.

Key features:
- Natural language processing using OpenAI GPT models
- Intent classification and data extraction
- Duration-aware processing (handles relative timeframes)
- Tool selection and prioritization
- Structured output with validation using Pydantic models

The interpreter serves as the bridge between human language and the structured
data format required by the multi-agent system, enabling natural interaction.
"""

from __future__ import annotations
import os, json, re, sys
from string import Template
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ValidationError

try:
    # pip install openai>=1.40
    from openai import OpenAI
except Exception:
    OpenAI = None


# ---------------- Schemas ----------------

class CountryInput(BaseModel):
    country: str
    cities: List[str] = Field(default_factory=list)

Intent = Literal[
    "plan_trip",
    "recommend_cities",
    "poi_lookup",
    "restaurants_nearby",
    "city_fares",
    "intercity_fares",
    "itinerary_edit",
    "general_question",
    "unknown",
]

class Interpretation(BaseModel):
    intent: Intent
    countries: List[CountryInput] = Field(default_factory=list)
    dates: Dict[str, str] = Field(default_factory=dict)  # {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}
    travelers: Dict[str, int] = Field(default_factory=lambda: {"adults": 1, "children": 0})
    musts: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    budget_caps: Dict[str, float] = Field(default_factory=dict)
    target_currency: str = "EUR"
    requires: List[str] = Field(default_factory=list)
    tool_plan: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------- Allowed tools (ONLY these six) ----------------

TOOL_INVENTORY: Dict[str, Dict[str, Any]] = {
  "cities.recommender": {
    "what": "Suggest cities to visit given country/season/themes.",
    "when": [
      "User asks for best cities or hasn't provided cities but wants a trip",
      "Trip planning needs city candidates"
    ],
    "needs": [],
    "provides": ["cities", "city_country_map", "scores", "sources"]
  },
  "fx.oracle": {
    "what": "Infer native currencies + USD→CODE spot; builds code→target multipliers.",
    "when": [
      "User asked for specific currency display (non-EUR)",
      "User mentions budgets or cost caps"
    ],
    "needs": ["target_currency"],
    "provides": ["fx", "to_target", "currency_by_country"]
  },
  "fares.city": {
    "what": "Local public transit and taxi fares per city (official-first).",
    "when": [
      "User asks about metro/bus/taxi fares in one or more cities",
      "Trip planning needs a city cost model"
    ],
    "needs": ["cities", "city_country_map"],
    "provides": ["city_fares"]
  },
  "fares.intercity": {
    "what": "Durations/prices for train/bus/flight between cities.",
    "when": [
      "User asks how to go from City A to City B (and price/time)",
      "Multi-city trip planning"
    ],
    "needs": ["cities", "city_country_map"],
    "provides": ["intercity"]
  },
  "poi.discovery": {
    "what": "Things to do / POIs in a city (hours/prices native currency if found).",
    "when": [
      "User wants attractions/activities/sights",
      "Trip planning enrichment"
    ],
    "needs": ["cities"],
    "provides": ["discovery.cities.*.pois"]
  },
  "restaurants.discovery": {
    "what": "Restaurants near POIs/city centers; honors cuisines/diet/price/kid-friendly.",
    "when": [
      "User asks for places to eat",
      "Trip planning enrichment around POIs"
    ],
    "needs": ["cities"],
    "provides": ["restaurants"]
  },
}

ALLOWED_TOOLS = set(TOOL_INVENTORY.keys())


# ---------------- Prompt (string.Template) ----------------

SYSTEM = (
    "You are a strict JSON information extractor and travel-intent classifier. "
    "You must only choose tools from the provided inventory. Output ONLY JSON. No prose."
)

USER_TEMPLATE = Template(
"""Interpret the user's travel message. Extract normalized fields and classify intent.

Rules:
- ISO dates only (YYYY-MM-DD). If only month/season or relative duration is given (e.g., '3 days', 'one week', 'weekend'),
  leave dates empty and set preferences.duration_days (integer) or preferences.duration_hint ('weekend', 'few_days', etc.).
- Travelers default to {"adults":1,"children":0} unless stated.
- Countries should be country names; include cities if mentioned.
- Do NOT fabricate cities or dates. Only fill what's stated or clearly implied (e.g., "in Paris" → city=Paris, country=France).
- target_currency defaults to "EUR" unless user specified otherwise (e.g., USD, GBP, JPY).
- If budgets like "under $$1500" appear, put the numeric under budget_caps.total; FX happens later.
- For landmark queries (e.g., Eiffel Tower), include preferences.landmark_context with near/city_hint/country_hint.
- Allowed intents: plan_trip, recommend_cities, poi_lookup, restaurants_nearby, city_fares, intercity_fares, itinerary_edit, general_question, unknown.

TOOL PLANNING (CRITICAL):
- You MUST select a minimal, ordered 'tool_plan' using ONLY these tools:
  ${allowed_tools}
- Pick only what is necessary for the user’s ask. Avoid extra steps.
- Examples:
  • City fares question → ["fares.city"] (+ "fx.oracle" if non-EUR or budget is asked)
  • Between two cities → ["fares.intercity"] (+ "fx.oracle" if non-EUR/budget)
  • Things to do → ["poi.discovery"]
  • Restaurants near a landmark → ["restaurants.discovery"]
  • “Plan a 3-day trip in Japan” → ["cities.recommender","poi.discovery","fares.city","restaurants.discovery"]
- NEVER include tools that are not in the list above.

REQUIREMENTS:
- 'requires' should list missing slots for the chosen tools.
- Do NOT require dates when a relative duration or weekend is given (store in preferences.duration_* instead).
- Typical requires:
  • For any tool that needs cities but none parsed → include "cities_or_country".
  • For fares.intercity when <2 cities → include "two_cities".
  • Only require "dates" if neither exact dates nor a duration hint was provided.

Respond with STRICT JSON of this shape:
{
  "intent": "...",
  "countries": [{"country":"...","cities":["..."]}],
  "dates": {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"},
  "travelers": {"adults":1,"children":0},
  "musts": ["..."],
  "preferences": {},
  "budget_caps": {},
  "target_currency": "EUR",
  "requires": ["..."],
  "tool_plan": ["..."],
  "notes": ["..."]
}

Tool inventory and guidance:
${tool_guide}

User timezone: America/Chicago
User message:
<<<MESSAGE_START>>>
$message
<<<MESSAGE_END>>>
"""
)


# ---------------- Few-shot examples (compact) ----------------

EXAMPLES: List[tuple[str, Dict[str, Any]]] = [
    (
        "We’re two adults visiting Japan next April for about a week. Tokyo and Kyoto. Mid budget. Show prices in USD.",
        {
          "intent":"plan_trip",
          "countries":[{"country":"Japan","cities":["Tokyo","Kyoto"]}],
          "dates":{},
          "travelers":{"adults":2,"children":0},
          "musts":[],
          "preferences":{"budget_tier":"mid","duration_days":7,"month_hint":"April"},
          "budget_caps":{},
          "target_currency":"USD",
          "requires":[],
          "tool_plan":[
            "cities.recommender","fares.city","fares.intercity",
            "poi.discovery","restaurants.discovery","fx.oracle"
          ],
          "notes":["Month + relative duration, no exact dates required"]
        }
    ),
    (
        "How much are taxis and a metro day pass in New York City? Show in USD.",
        {
          "intent":"city_fares",
          "countries":[{"country":"United States","cities":["New York"]}],
          "dates":{},
          "travelers":{"adults":1,"children":0},
          "musts":[],
          "preferences":{},
          "budget_caps":{},
          "target_currency":"USD",
          "requires":[],
          "tool_plan":["fares.city","fx.oracle"],
          "notes":[]
        }
    ),
    (
        "I'm at the Eiffel Tower with my kid — any kid-friendly restaurants nearby?",
        {
          "intent":"restaurants_nearby",
          "countries":[{"country":"France","cities":["Paris"]}],
          "dates":{},
          "travelers":{"adults":1,"children":1},
          "musts":[],
          "preferences":{
            "kid_friendly":True,
            "landmark_context":{"near":"Eiffel Tower","city_hint":"Paris","country_hint":"France"}
          },
          "budget_caps":{},
          "target_currency":"EUR",
          "requires":[],
          "tool_plan":["restaurants.discovery"],
          "notes":[]
        }
    ),
    (
        "Best way and price to go from Rome to Florence next weekend?",
        {
          "intent":"intercity_fares",
          "countries":[{"country":"Italy","cities":["Rome","Florence"]}],
          "dates":{},
          "travelers":{"adults":1,"children":0},
          "musts":[],
          "preferences":{"date_hint":"weekend"},
          "budget_caps":{},
          "target_currency":"EUR",
          "requires":[],
          "tool_plan":["fares.intercity"],
          "notes":["Weekend hint provided; no exact dates required"]
        }
    ),
    (
        "3-day trip plan in Japan — food and art focus, please.",
        {
          "intent":"plan_trip",
          "countries":[{"country":"Japan","cities":[]}],
          "dates":{},
          "travelers":{"adults":1,"children":0},
          "musts":[],
          "preferences":{"themes":["food","art"],"duration_days":3},
          "budget_caps":{},
          "target_currency":"EUR",
          "requires":[],
          "tool_plan":["cities.recommender","poi.discovery","fares.city","restaurants.discovery"],
          "notes":[]
        }
    ),
]


def _examples_block() -> str:
    parts = []
    for i, (msg, out) in enumerate(EXAMPLES, 1):
        parts.append(
            f'Example {i} Input\n<<<EXAMPLE_MESSAGE_START>>>\n{msg}\n<<<EXAMPLE_MESSAGE_END>>>\n'
            f'Example {i} Output JSON\n{json.dumps(out, ensure_ascii=False)}'
        )
    return "\n\n".join(parts)


# ---------------- Utilities ----------------

_DURATION_PATTERNS = [
    # days
    (re.compile(r"\b(\d{1,2})\s*(?:day|days)\b", re.I), "days"),
    # weeks
    (re.compile(r"\b(\d{1,2})\s*(?:week|weeks)\b", re.I), "weeks"),
    # weekend
    (re.compile(r"\bweekend\b", re.I), "weekend"),
    # few/couple
    (re.compile(r"\b(a\s*few|few)\s*days\b", re.I), "few_days"),
    (re.compile(r"\b(couple\s*of)\s*days\b", re.I), "few_days"),
]

def _extract_duration_from_text(message: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    m = message or ""
    for pat, kind in _DURATION_PATTERNS:
        mm = pat.search(m)
        if not mm:
            continue
        if kind == "days" and mm.group(1):
            try:
                out["duration_days"] = int(mm.group(1))
            except Exception:
                pass
        elif kind == "weeks" and mm.group(1):
            try:
                out["duration_days"] = int(mm.group(1)) * 7
            except Exception:
                pass
        elif kind == "weekend":
            out["duration_hint"] = "weekend"
        elif kind == "few_days":
            out["duration_hint"] = "few_days"
        # Prefer concrete duration_days over hints if both appear
    return out

_MONTHS = {m.lower(): m for m in
           ["January","February","March","April","May","June","July","August","September","October","November","December"]}

def enrich_from_text(message: str, interp: Interpretation) -> Interpretation:
    """Light heuristics to keep useful hints when LLM omits them."""
    m = (message or "").lower()

    # budget tier hints
    if "luxury" in m or "5-star" in m or "splurge" in m:
        interp.preferences.setdefault("budget_tier", "luxury")
    elif "mid" in m or "moderate" in m or "mid-range" in m:
        interp.preferences.setdefault("budget_tier", "mid")
    elif "cheap" in m or "affordable" in m or "budget" in m:
        interp.preferences.setdefault("price_tier", "budget")

    # month hint
    for token in _MONTHS:
        if re.search(rf"\b{token}\b", m):
            interp.preferences.setdefault("month_hint", _MONTHS[token])
            break

    # weekend hint
    if "weekend" in m:
        interp.preferences.setdefault("date_hint", "weekend")

    # family/kids
    if "kid" in m or "family" in m or "children" in m:
        interp.preferences.setdefault("kid_friendly", True)

    # duration extraction
    dur = _extract_duration_from_text(message)
    for k, v in dur.items():
        interp.preferences.setdefault(k, v)

    return interp

def _needs_fx(interp: Interpretation) -> bool:
    tc = (interp.target_currency or "").upper()
    return (tc and tc != "EUR") or bool(interp.budget_caps)

def _ensure_fx_tool(interp: Interpretation) -> Interpretation:
    """Add fx.oracle when target currency isn't EUR or budgets are present."""
    if _needs_fx(interp) and "fx.oracle" not in interp.tool_plan:
        # Try to place it after any fares/cost tools if present, else at end
        insert_after = ["fares.city", "fares.intercity", "poi.discovery", "restaurants.discovery"]
        idx = -1
        for t in insert_after:
            if t in interp.tool_plan:
                idx = max(idx, interp.tool_plan.index(t))
        if idx >= 0:
            interp.tool_plan.insert(idx + 1, "fx.oracle")
        else:
            interp.tool_plan.append("fx.oracle")
    return interp

def _salvage_json(txt: Optional[str]) -> Dict[str, Any]:
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"{[\s\S]*}", txt)
        return json.loads(m.group(0)) if m else {}

def _heuristic_fallback(message: str, note: str) -> Interpretation:
    m = (message or "").lower()
    intent: Intent = "unknown"
    if any(k in m for k in ["trip", "itinerary", "days", "nights", "plan"]):
        intent = "plan_trip"
    elif "restaurant" in m or "eat" in m:
        intent = "restaurants_nearby"
    elif any(k in m for k in ["taxi", "metro", "fare"]):
        intent = "city_fares"
    elif " from " in m and " to " in m:
        intent = "intercity_fares"

    interp = Interpretation(intent=intent, requires=["llm_interpretation"], notes=[note])

    # Minimal default plan from allowed tools only
    minimal: Dict[str, List[str]] = {
        "plan_trip": ["cities.recommender","poi.discovery","fares.city","restaurants.discovery"],
        "recommend_cities": ["cities.recommender"],
        "poi_lookup": ["poi.discovery"],
        "restaurants_nearby": ["restaurants.discovery"],
        "city_fares": ["fares.city"],
        "intercity_fares": ["fares.intercity"],
        "itinerary_edit": ["poi.discovery"],
        "general_question": [],
        "unknown": [],
    }
    interp.tool_plan = minimal.get(interp.intent, [])

    # FX if needed
    interp = enrich_from_text(message, interp)
    interp = _ensure_fx_tool(interp)

    # Requires guards (no dates required if duration present)
    has_exact_dates = bool(interp.dates.get("start") and interp.dates.get("end"))
    has_duration = ("duration_days" in interp.preferences) or ("duration_hint" in interp.preferences) or ("date_hint" in interp.preferences)
    reqs = set(interp.requires or [])
    if any(t in interp.tool_plan for t in ["fares.city","poi.discovery","restaurants.discovery"]) and not interp.countries:
        reqs.add("cities_or_country")
    if "fares.intercity" in interp.tool_plan:
        # need at least two cities
        total_cities = sum(len(ci.cities or []) for ci in interp.countries)
        if total_cities < 2:
            reqs.add("two_cities")
    if (interp.intent in ("plan_trip","intercity_fares")) and (not has_exact_dates and not has_duration):
        reqs.add("dates")
    interp.requires = list(reqs)
    return interp


# ---------------- Runner ----------------

def interpret(message: str) -> Interpretation:
    """
    Return a validated Interpretation for a free-text message using one LLM call.
    Falls back to a minimal heuristic if OpenAI SDK is unavailable or no API key.
    """
    key = os.getenv("OPENAI_API_KEY")
    if OpenAI is None or not key:
        note = "OpenAI SDK not installed" if OpenAI is None else "missing OPENAI_API_KEY; heuristic fallback"
        interp = _heuristic_fallback(message, note)
        return interp

    # Normal LLM path
    try:
        client = OpenAI(api_key=key)
    except Exception as e:
        return _heuristic_fallback(message, f"OpenAI client init error: {e}")

    tool_guide = json.dumps(TOOL_INVENTORY, ensure_ascii=False, indent=2)
    prompt = USER_TEMPLATE.substitute(
        message=message,
        tool_guide=tool_guide,
        allowed_tools=json.dumps(sorted(list(ALLOWED_TOOLS)))
    )
    prompt_with_examples = prompt + "\n\n" + _examples_block()

    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt_with_examples},
        ],
    )

    raw = resp.choices[0].message.content
    data = _salvage_json(raw)

    # Fix common LLM mistakes: ensure budget_caps and preferences are dicts, not strings
    if "budget_caps" in data and not isinstance(data["budget_caps"], dict):
        if isinstance(data["budget_caps"], str):
            # If LLM put currency in budget_caps, move it to target_currency
            if data["budget_caps"] in ["USD", "EUR", "GBP", "JPY"] and "target_currency" not in data:
                data["target_currency"] = data["budget_caps"]
            data["budget_caps"] = {}
        else:
            data["budget_caps"] = {}
    
    if "preferences" in data and not isinstance(data["preferences"], dict):
        data["preferences"] = {}

    # Fix common LLM mistakes: map tool names to intents
    intent_mapping = {
        "fares.city": "city_fares",
        "fares.intercity": "intercity_fares", 
        "poi.discovery": "poi_lookup",
        "restaurants.discovery": "restaurants_nearby",
        "cities.recommender": "recommend_cities"
    }
    
    # If intent is a tool name, map it to the correct intent
    if data.get("intent") in intent_mapping:
        data["intent"] = intent_mapping[data["intent"]]
    
    try:
        interp = Interpretation.model_validate(data)
    except ValidationError as e:
        # Best-effort: keep declared intent, everything else defaulted
        interp = Interpretation(intent=data.get("intent") or "unknown", notes=[f"validation_error: {e}"])

    # Safety rails: filter + dedupe tools to ALLOWED_TOOLS, preserve order
    filtered: List[str] = []
    seen = set()
    for t in (interp.tool_plan or []):
        if t in ALLOWED_TOOLS and t not in seen:
            seen.add(t); filtered.append(t)
    interp.tool_plan = filtered

    # Add FX if needed
    interp = _ensure_fx_tool(interp)

    # Requires guardrails (no dates required if duration present)
    has_exact_dates = bool(interp.dates.get("start") and interp.dates.get("end"))
    has_duration = ("duration_days" in interp.preferences) or ("duration_hint" in interp.preferences) or ("date_hint" in interp.preferences)

    reqs = set(interp.requires or [])
    if any(t in interp.tool_plan for t in ["fares.city","poi.discovery","restaurants.discovery"]) and not interp.countries:
        reqs.add("cities_or_country")
    if "fares.intercity" in interp.tool_plan:
        total_cities = sum(len(ci.cities or []) for ci in interp.countries)
        if total_cities < 2:
            reqs.add("two_cities")
    if (interp.intent in ("plan_trip","intercity_fares")) and (not has_exact_dates and not has_duration):
        reqs.add("dates")
    interp.requires = list(reqs)

    # Enrich small hints (budget tier, month/weekend, family, duration)
    interp = enrich_from_text(message, interp)
    return interp


# ---------------- CLI (run directly) ----------------

if __name__ == "__main__":
    # Usage:
    # 1) Pass one or more messages as CLI args:
    #    python agent_interpreter.py "Plan Japan in April..." "Taxi prices in NYC?"
    # 2) Pipe from stdin:
    #    echo "I'm at the Eiffel Tower..." | python agent_interpreter.py -
    # 3) No args -> run a small demo batch below.

    args = sys.argv[1:]
    if args == ["-"]:
        msg = sys.stdin.read().strip()
        msgs = [msg] if msg else []
    elif args:
        msgs = args
    else:
        msgs = [
            "We’re two adults visiting Japan next April for a week. Tokyo and Kyoto. Show prices in USD.",
            "How much are taxis and a metro day pass in New York City? Show in USD.",
            "I'm at the Eiffel Tower with my kid — any kid-friendly restaurants nearby?",
            "Best way and price to go from Rome to Florence next weekend?",
            "3-day trip plan in Japan — food and art focus, please.",
        ]

    for i, msg in enumerate(msgs, 1):
        out = interpret(msg)
        print(f"\n=== Message {i} ===")
        print(msg)
        print("=== Interpretation ===")
        print(out.model_dump_json(indent=2))
