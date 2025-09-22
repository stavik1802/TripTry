"""
Output Agent for TripPlanner Multi-Agent System

This agent generates the final human-readable response by synthesizing all the data
collected from other agents. It transforms structured data into natural language
responses, JSON outputs, and formatted reports for users.

Key responsibilities:
- Synthesize data from planning, research, and budget agents
- Generate AI-powered human-like responses using OpenAI
- Format outputs in multiple formats (JSON, markdown, text, HTML)
- Create comprehensive trip reports with detailed itineraries
- Handle fallback responses when AI services are unavailable

The agent combines all agent outputs into a cohesive, user-friendly response
that provides complete trip planning information with budgets, itineraries,
and recommendations.
"""

from typing import Any, Dict, Optional, List
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentMessage, AgentContext
from app.core.common_schema import AgentDataSchema
from datetime import datetime
import os
import json

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class OutputAgent(MemoryEnhancedBaseAgent):
    """Formats final deliverable as JSON/markdown with tiers + provenance."""

    def __init__(self):
        super().__init__("output_agent", "response_formatter")
        self.capabilities = ["render_json", "render_markdown", "render_text", "render_html"]
        self.dependencies = ["planning_agent", "research_agent", "budget_agent"]

    # ---------------------------
    # Message interface
    # ---------------------------
    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        return None

    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        self.update_status("working")

        planning_data  = context.shared_data.get("planning_data", {}) or {}
        research_data  = context.shared_data.get("research_data", {}) or {}
        budget_data    = context.shared_data.get("budget_data", {}) or {}
        trip_data      = context.shared_data.get("trip_data", {}) or {}
        geocost_data   = context.shared_data.get("geocost_data", {}) or {}
        optimized_data = context.shared_data.get("optimized_data", {}) or {}

        user_request = context.user_request or ""

        try:
            response = self._generate_ai_response(
                user_request=user_request,
                planning_data=planning_data,
                research_data=research_data,
                budget_data=budget_data,
                trip_data=trip_data,
                geocost_data=geocost_data,
                optimized_data=optimized_data
            )
            self.update_status("completed")
            return {
                "status": "success",
                "response": response,
                "trip_data": trip_data,
                "agent_id": self.agent_id
            }
        except Exception as e:
            self.update_status("error")
            return {"status": "error", "error": str(e), "agent_id": self.agent_id}

    # ---------------------------
    # LLM Orchestration
    # ---------------------------
    def _generate_ai_response(
        self,
        user_request: str,
        planning_data: Dict[str, Any],
        research_data: Dict[str, Any],
        budget_data: Dict[str, Any],
        trip_data: Dict[str, Any],
        geocost_data: Dict[str, Any],
        optimized_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate AI-powered human-like response using OpenAI with improved error handling"""

        if OpenAI is None:
            return self._fallback_response(planning_data, research_data, budget_data, trip_data)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._fallback_response(planning_data, research_data, budget_data, trip_data)

        try:
            client = OpenAI(api_key=api_key)
        except Exception as e:
            return self._fallback_response(planning_data, research_data, budget_data, trip_data)

        # 1) Normalize & summarize
        data_summary = self._prepare_data_summary(
            planning_data, research_data, budget_data, trip_data, geocost_data, optimized_data
        )

        # 2) Build a FULL LLM PACKET (summary + raw buckets: everything you produced)
        llm_packet = self._build_llm_packet(
            user_request=user_request,
            summary=data_summary,
            planning_data=planning_data,
            research_data=research_data,
            budget_data=budget_data,
            trip_data=trip_data,
            geocost_data=geocost_data,
            optimized_data=optimized_data,
        )

        # 3) Prompt
        prompt, max_tokens, response_style = self._create_response_prompt(user_request, data_summary, llm_packet)


        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful travel assistant. "
                            "Use ONLY the facts present in the DATA PACKET. "
                            "Do NOT invent attractions, prices, dates, or names. "
                            "If a fact is not present, omit it."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            print("[DEBUG] OpenAI API call successful")
            ai_response = response.choices[0].message.content or ""
            print(f"[DEBUG] AI response length: {len(ai_response)}")
            print(f"[DEBUG] AI response preview: {ai_response}")  # no slicing

            result = self._parse_ai_response(ai_response, data_summary)
            return result
        except Exception as e:
            print(f"[DEBUG] OpenAI API call failed: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_response(planning_data, research_data, budget_data, trip_data)

    # ---------------------------
    # FULL LLM DATA PACKET (summary + raw)
    # ---------------------------
    def _build_llm_packet(
        self,
        user_request: str,
        summary: Dict[str, Any],
        planning_data: Dict[str, Any],
        research_data: Dict[str, Any],
        budget_data: Dict[str, Any],
        trip_data: Dict[str, Any],
        geocost_data: Dict[str, Any],
        optimized_data: Dict[str, Any],
    ) -> str:
        """Create a JSON text block with normalized summary AND all raw buckets (no slicing)."""
        packet = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "user_request": user_request,
                "note": "Use only data present in this packet. Omit anything not present.",
            },
            "normalized_summary": summary,
            "raw": {
                "planning_data": planning_data,
                "research_data": research_data,
                "budget_data": budget_data,
                "trip_data": trip_data,
                "geocost_data": geocost_data,
                "optimized_data": optimized_data,
            },
        }
        try:
            return json.dumps(packet, ensure_ascii=False, indent=2)
        except Exception:
            # As a fallback, dump without indent to avoid encoding issues
            return json.dumps(packet, ensure_ascii=False)

    # ---------------------------
    # Normalization (ALL buckets)
    # ---------------------------
    def _first_list_of_dicts(self, obj):
        if isinstance(obj, list) and (not obj or isinstance(obj[0], dict)):
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = self._first_list_of_dicts(v)
                if found is not None:
                    return found
        return None

    def _normalize_cities(self, research_data: Dict[str, Any], planning_data: Dict[str, Any]) -> List[str]:
        cities = research_data.get("cities")
        if isinstance(cities, list) and cities:
            return cities
        disc_cities = (research_data.get("discovery") or {}).get("cities") or {}
        if isinstance(disc_cities, dict) and disc_cities:
            return list(disc_cities.keys())
        geocost = (planning_data.get("geocost") or research_data.get("geocost") or {})
        if isinstance(geocost, dict) and geocost:
            return list(geocost.keys())
        return []

    def _normalize_pois_by_city(self, research_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        poi_block = research_data.get("poi") or {}
        base = poi_block.get("poi_by_city") if isinstance(poi_block, dict) else None
        if not isinstance(base, dict):
            base = poi_block if isinstance(poi_block, dict) else {}
        if not base:
            base = ((research_data.get("discovery") or {}).get("cities") or {})
        for city, val in (base or {}).items():
            if isinstance(val, dict):
                lst = val.get("pois")
                if isinstance(lst, list):
                    out[city] = lst
                    continue
                lst = self._first_list_of_dicts(val)
                if isinstance(lst, list):
                    out[city] = lst
            elif isinstance(val, list):
                out[city] = val
        return out

    def _normalize_restaurants_by_city(self, restaurants_block: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        if not isinstance(restaurants_block, dict):
            return {}
        if "names_by_city" in restaurants_block and isinstance(restaurants_block["names_by_city"], dict):
            return restaurants_block["names_by_city"]
        out: Dict[str, List[Dict[str, Any]]] = {}
        for city, val in restaurants_block.items():
            if isinstance(val, list) and (not val or isinstance(val[0], dict)):
                out[city] = val
            elif isinstance(val, dict):
                lst = self._first_list_of_dicts(val)
                if isinstance(lst, list):
                    out[city] = lst
        return out

    def _normalize_city_fares(self, research_data: Dict[str, Any]) -> Dict[str, Any]:
        cf = research_data.get("city_fares") or {}
        if not isinstance(cf, dict):
            return {}
        if "city_fares" in cf and isinstance(cf["city_fares"], dict):
            return cf["city_fares"]
        return cf

    def _normalize_intercity(self, research_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        inter = research_data.get("intercity") or {}
        if isinstance(inter, list):
            out = {}
            for h in inter:
                a = (h or {}).get("from"); b = (h or {}).get("to")
                if a and b:
                    out[f"{a} -> {b}"] = h
            return out
        if isinstance(inter, dict) and isinstance(inter.get("hops"), list):
            out = {}
            for h in inter["hops"]:
                a = (h or {}).get("from"); b = (h or {}).get("to")
                if a and b:
                    out[f"{a} -> {b}"] = h
            return out
        return inter if isinstance(inter, dict) else {}

    def _normalize_fx(self, research_data: Dict[str, Any], planning_data: Dict[str, Any]) -> Dict[str, Any]:
        fx = research_data.get("fx") or {}
        if isinstance(fx, dict) and fx:
            return fx
        cur = research_data.get("currency") or {}
        rates = cur.get("rates") if isinstance(cur, dict) else None
        if isinstance(rates, dict):
            return {"rates": rates}
        target = planning_data.get("target_currency") or "EUR"
        return {"target": target, "rates": {}}

    def _normalize_cost_breakdown(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cb = AgentDataSchema.extract_cost_breakdown(trip_data)
            return {
                "lodging": cb.lodging,
                "transit": cb.transit,
                "intercity": cb.intercity,
                "travel": cb.travel,
                "poi_entry": cb.poi_entry,
                "meals": cb.meals,
                "grand_total": cb.grand_total
            }
        except Exception:
            t = (((trip_data or {}).get("request") or {}).get("trip") or {}).get("totals") \
                or ((trip_data or {}).get("trip") or {}).get("totals") \
                or {}
            return {
                "lodging": t.get("lodging"),
                "transit": t.get("transit"),
                "intercity": t.get("intercity"),
                "travel": t.get("travel"),
                "poi_entry": t.get("poi_entry"),
                "meals": t.get("meals"),
                "grand_total": t.get("grand_total"),
            }

    # ---------------------------
    # Summary + formatting helpers
    # ---------------------------
    def _prepare_data_summary(self, planning_data, research_data, budget_data, trip_data, geocost_data, optimized_data) -> Dict[str, Any]:
        cost_breakdown_dict = self._normalize_cost_breakdown(trip_data)
        gt = cost_breakdown_dict.get("grand_total")
        total_cost = gt.get("amount", 0) if isinstance(gt, dict) else (gt or 0)

        cities             = self._normalize_cities(research_data, planning_data)
        pois_by_city       = self._normalize_pois_by_city(research_data)
        restaurants_by_city= self._normalize_restaurants_by_city(research_data.get("restaurants") or {})
        city_fares         = self._normalize_city_fares(research_data)
        intercity_hops     = self._normalize_intercity(research_data)
        fx                 = self._normalize_fx(research_data, planning_data)

        summary = {
            "user_request": planning_data.get("intent", "plan_trip"),
            "travelers": planning_data.get("travelers", {}),
            "duration": planning_data.get("preferences", {}).get("duration_days", 0),
            "budget": planning_data.get("budget_caps", {}).get("total", 0),
            "currency": planning_data.get("target_currency", "EUR"),
            "must_visit": planning_data.get("musts", []),
            "preferences": planning_data.get("preferences", {}),
            "cities": cities,
            "city_country_map": research_data.get("city_country_map", {}),
            "pois": pois_by_city,
            "restaurants": restaurants_by_city,
            "city_fares": city_fares,
            "intercity_fares": intercity_hops,
            "currency_rates": fx,
            "trip_itinerary": AgentDataSchema.extract_trip_days(trip_data),
            "cost_breakdown": cost_breakdown_dict,
            "total_cost": total_cost,
        }
        return summary

    def _format_pois(self, pois: Dict[str, Any]) -> str:
        if not pois: return "No POIs found"
        lines = []
        for city, city_pois in pois.items():
            lines.append(f"\n{city}:")
            items = city_pois if isinstance(city_pois, list) else (city_pois.get("pois", []) if isinstance(city_pois, dict) else [])
            for poi in items:
                name = poi.get("name", "Unknown") if isinstance(poi, dict) else str(poi)
                desc = poi.get("description", "") if isinstance(poi, dict) else ""
                price = poi.get("price", {}) if isinstance(poi, dict) else {}
                line = f"  - {name}"
                if desc: line += f": {desc}"
                lines.append(line)
                if price: lines.append(f"    Price: {price}")
        return "\n".join(lines) if lines else "No POIs found"

    def _format_restaurants(self, restaurants_by_city: Dict[str, Any]) -> str:
        if not restaurants_by_city: return "No restaurants found"
        lines = []
        for city, rest_list in restaurants_by_city.items():
            if isinstance(rest_list, list) and rest_list:
                lines.append(f"\n{city}:")
                for rest in rest_list:
                    if isinstance(rest, dict):
                        name = rest.get("name", "Unknown")
                        cuisine = rest.get("cuisine", "")
                        lines.append(f"  - {name}" + (f" ({cuisine})" if cuisine else ""))
                    else:
                        lines.append(f"  - {str(rest)}")
        return "\n".join(lines) if lines else "No restaurants found"

    def _format_itinerary(self, itinerary: List[Dict[str, Any]]) -> str:
        if not itinerary: return "No detailed itinerary available"
        lines = []
        for i, day in enumerate(itinerary):
            date = day.get("date", f"Day {i+1}")
            city = day.get("city", "Unknown")
            items = day.get("items", [])
            lines.append(f"\n{date} - {city}:")
            for item in items:
                name = item.get("name", "Unknown")
                item_type = item.get("type", "activity")
                start_time = item.get("start_min", 0)
                if start_time:
                    hours = start_time // 60
                    minutes = start_time % 60
                    time_str = f"{hours:02d}:{minutes:02d}"
                    lines.append(f"  {time_str}: {name} ({item_type})")
                else:
                    lines.append(f"  - {name} ({item_type})")
        return "\n".join(lines) if lines else "No detailed itinerary available"

    # ---------------------------
    # Prompt construction
    # ---------------------------
    def _create_response_prompt(self, user_request: str, data_summary: Dict[str, Any], llm_packet: str):
        # Intent
        request_lower = (user_request or "").lower()
        is_simple_query = any(k in request_lower for k in [
            "fare","price","cost","how much","bus fare","taxi fare",
            "restaurant","restaurant recommendation","poi","attraction",
            "what is","tell me about","information about"
        ])
        is_complex_planning = any(k in request_lower for k in [
            "plan","itinerary","trip","travel","visit","vacation","holiday",
            "journey","tour","explore","discover","schedule","days"
        ])

        if is_simple_query and not is_complex_planning:
            response_style = "CONCISE";      max_tokens = 500
        elif is_complex_planning:
            response_style = "COMPREHENSIVE"; max_tokens = 2000
        else:
            response_style = "BALANCED";      max_tokens = 1000

        # Human-readable blocks (for the model’s convenience)
        pois_block = self._format_pois(data_summary.get("pois", {}))
        restaurants_block = self._format_restaurants(data_summary.get("restaurants", {}))
        itinerary_block = self._format_itinerary(data_summary.get("trip_itinerary", []))

        # FINAL PROMPT (includes FULL DATA PACKET at the end)
        prompt = f"""
You must answer using ONLY facts from the DATA PACKET below. If a detail is not present, omit it. Never invent names, prices, or times.

REQUEST:
{user_request}

RESPONSE STYLE: {response_style}
- If CONCISE: 2–3 sentences max, direct answer only.
- If BALANCED: 1–2 short paragraphs, highlights only (prose, not bullets).
- If COMPREHENSIVE (trip planning): multi-paragraph human narration with day-by-day flow. Use the itinerary order provided. Weave in POIs, restaurants, fares, and costs when present, but do not fabricate any. Do not mention missing data.

SUMMARY SNAPSHOT (normalized; for convenience only):
- Cities: {data_summary.get('cities', [])}
- POIs (by city): 
{pois_block}
- Restaurants (by city): 
{restaurants_block}
- City fares (raw): {data_summary.get('city_fares', {})}
- Intercity (raw): {data_summary.get('intercity_fares', {})}
- Budget total: {data_summary.get('total_cost', 0)} {data_summary.get('currency', 'EUR')}
- Itinerary (read-only; do not invent):
{itinerary_block}

DATA PACKET (JSON; authoritative, use only this data):
{llm_packet}
""".strip()

        return prompt, max_tokens, response_style

    # ---------------------------
    # Parse / Fallback / Format
    # ---------------------------
    def _parse_ai_response(self, ai_response: str, data_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "tier": "full" if data_summary.get("trip_itinerary") else "standard",
            "response_text": ai_response,
            "summary": {
                "cities": data_summary.get("cities", []),
                "duration": data_summary.get("duration", 0),
                "budget": data_summary.get("budget", 0),
                "currency": data_summary.get("currency", "EUR"),
                "has_itinerary": bool(data_summary.get("trip_itinerary")),
                "has_pois": bool(data_summary.get("pois")),
                "has_restaurants": bool(data_summary.get("restaurants")),
                "has_transportation": bool(data_summary.get("city_fares") or data_summary.get("intercity_fares")),
            },
            "trip_data": data_summary.get("trip_itinerary", []),
            "preferences": data_summary.get("preferences", {}),
        }

    def _fallback_response(self, planning_data: Dict[str, Any], research_data: Dict[str, Any], budget_data: Dict[str, Any], trip_data: Dict[str, Any]) -> Dict[str, Any]:
        cities = research_data.get("cities", [])
        duration = planning_data.get("preferences", {}).get("duration_days", 0)
        budget = planning_data.get("budget_caps", {}).get("total", 0)
        currency = planning_data.get("target_currency", "EUR")

        response_text = f"""
Travel Plan Summary (fallback)
Destinations: {', '.join(cities) if cities else 'N/A'}
Duration: {duration} days | Budget: {budget} {currency}
Note: OpenAI was unavailable; this is a minimal fallback message.
""".strip()

        has_pois = bool((research_data.get("poi") or {}).get("poi_by_city"))
        has_restaurants = bool((research_data.get("restaurants") or {}).get("names_by_city"))
        has_transportation = bool(research_data.get("city_fares") or research_data.get("intercity"))

        return {
            "status": "success",
            "tier": "basic",
            "response_text": response_text,
            "summary": {
                "cities": cities,
                "duration": duration,
                "budget": budget,
                "currency": currency,
                "has_itinerary": False,
                "has_pois": has_pois,
                "has_restaurants": has_restaurants,
                "has_transportation": has_transportation,
            },
            "trip_data": [],
            "preferences": planning_data.get("preferences", {}),
        }

    # ---------------------------
    # Public formatting API
    # ---------------------------
    def format_response(self, data: Dict[str, Any], format_type: str = "json") -> Any:
        if format_type == "json":
            return data
        elif format_type == "text":
            return str(data)
        elif format_type == "markdown":
            return f"# Trip Summary\n\n{str(data)}"
        elif format_type == "html":
            return f"<html><body><h1>Trip Summary</h1><pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre></body></html>"
        else:
            return data
