"""
Research Agent for TripPlanner Multi-Agent System

This agent coordinates the discovery and data gathering phase by executing various
research tools to collect comprehensive information about destinations, attractions,
restaurants, and transportation options.

Key responsibilities:
- Execute discovery tools based on planning agent's tool plan
- Gather city recommendations and destination information
- Discover Points of Interest (POIs) and attractions
- Research restaurants and dining options
- Collect transportation fares (city and intercity)
- Validate and structure collected research data

The agent systematically executes research tools in parallel to gather all
necessary information for trip planning, ensuring comprehensive data collection
for the budget and optimization phases.
"""

from typing import Any, Dict, List, Optional
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentContext
from app.agents.utils.graph_integration import AgentGraphBridge
from app.core.common_schema import AgentDataSchema

class ResearchAgent(MemoryEnhancedBaseAgent):
    """Agent responsible for gathering information using discovery tools"""
    
    def __init__(self):
        super().__init__("research_agent", "researcher")
        self.capabilities = ["discover_cities", "discover_pois", "discover_restaurants", "gather_fares"]
        self.dependencies = ["planning_agent"]
        self.graph_bridge = AgentGraphBridge()
    
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute research task"""
        self.update_status("working")
        
        # Get planning data
        planning_data = context.shared_data.get("planning_data", {})
        # PATCH #1: Read tool_plan only from planning_data (persisted), not from a top-level transient key
        tool_plan = list(set(planning_data.get("tool_plan", [])))
        
        
        research_results: Dict[str, Any] = {}
        
        try:
            # PATCH #2: Validation—accept either countries OR cities
            has_countries = AgentDataSchema.validate_data_structure(planning_data, ["countries"], "planning_data")
            has_cities    = bool(planning_data.get("cities"))
            if not (has_countries or has_cities):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "Invalid planning data: need 'countries' or 'cities'",
                    "agent_id": self.agent_id
                }

            # --- Seed cities from planning_data if provided (independent of city_recommender) ---
            if planning_data.get("cities"):
                research_results["cities"] = planning_data["cities"]
                # Build city_country_map from planning data (first country wins if multiple)
                countries = planning_data.get("countries", [])
                if countries:
                    country = countries[0].get("country", countries[0].get("name", "Unknown"))
                    research_results["city_country_map"] = {city: country for city in planning_data["cities"]}
            
            # Only discover cities if we still don't have them and city_recommender is in the tool plan
            if not research_results.get("cities") and "city_recommender" in tool_plan:
                # Use cities from planning data if available, otherwise discover cities
                if planning_data.get("cities"):
                    # Use cities from planning data
                    research_results["cities"] = planning_data.get("cities", [])
                    # Build city_country_map from planning data
                    countries = planning_data.get("countries", [])
                    if countries:
                        country = countries[0].get("country", "Unknown")
                        research_results["city_country_map"] = {city: country for city in research_results["cities"]}
                elif planning_data.get("countries"):
                    # Discover cities if not specified in planning data
                    cities_data = self._discover_cities(planning_data)
                    if cities_data.get("cities"):
                        research_results["cities"] = cities_data.get("cities", [])
                        research_results["city_country_map"] = cities_data.get("city_country_map", {})
            else:
                # For specific intents that need cities but don't use cities.recommender
                # Extract city directly from planning data
                intent = planning_data.get("intent", "")
                if intent in ["city_fares", "poi_lookup", "restaurants_nearby"]:
                    countries = planning_data.get("countries", [])
                    if countries and countries[0].get("cities"):
                        city = countries[0]["cities"][0]  # Take first city
                        country = countries[0].get("country", "Unknown")
                        research_results["cities"] = [city]
                        research_results["city_country_map"] = {city: country}
            
            # Execute tools based on intent and tool plan
            
            # Only execute tools that are in the tool plan
            if research_results.get("cities"):
                if "poi_discovery" in tool_plan:
                    pois_data = self._discover_pois(planning_data, research_results)
                    if pois_data.get("poi_by_city"):
                        research_results["poi"] = {"poi_by_city": pois_data.get("poi_by_city", {})}
                
                if "restaurants_discovery" in tool_plan:
                    restaurants_data = self._discover_restaurants(planning_data, research_results)  # PATCH #3 handled in helper
                    if restaurants_data.get("names_by_city"):
                        research_results["restaurants"] = {
                            "names_by_city": restaurants_data.get("names_by_city", {}),
                            "links_by_city": restaurants_data.get("links_by_city", {}),
                            "details_by_city": restaurants_data.get("details_by_city", {})
                        }
                
                if "city_fare" in tool_plan:
                    city_fares_data = self._gather_city_fares(planning_data, research_results)
                    if city_fares_data.get("city_fares"):
                        research_results["city_fares"] = {"city_fares": city_fares_data.get("city_fares", {})}
                
                if "intercity_fare" in tool_plan:
                    intercity_fares_data = self._gather_intercity_fares(planning_data, research_results)
                    # Handle both data structures: direct 'hops' or nested 'intercity.hops'
                    if intercity_fares_data.get("hops"):
                        research_results["intercity"] = {"hops": intercity_fares_data.get("hops", {})}
                    elif intercity_fares_data.get("intercity"):
                        research_results["intercity"] = {"hops": intercity_fares_data.get("intercity", {}).get("hops", [])}
            
            # Always try to get currency data if needed
            if "currency" in tool_plan:
                currency_data = self._gather_currency_data(planning_data)
                if currency_data.get("fx"):
                    research_results["fx"] = currency_data.get("fx", {})
            
            # PATCH #4: Deep-merge into existing research_data instead of overwriting
            existing = context.shared_data.get("research_data", {})
            if isinstance(existing, dict) and isinstance(research_results, dict):
                def _merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
                    for k, v in src.items():
                        if isinstance(v, dict) and isinstance(dst.get(k), dict):
                            _merge(dst[k], v)
                        else:
                            dst[k] = v
                    return dst
                merged = _merge(dict(existing), research_results)
                context.shared_data["research_data"] = merged
            else:
                context.shared_data["research_data"] = research_results
            
            self.update_status("completed")
            
            return {
                "status": "success",
                "agent_id": self.agent_id,
                "research_data": context.shared_data["research_data"]
            }
            
        except Exception as e:
            self.update_status("error")
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id
            }
    
    def _discover_cities(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Discover cities using city recommender tool"""
        countries = []
        for c in plan_data.get("countries", []):
            countries.append({"country": c.get("country", c.get("name", ""))})
        
        
        args = {
            "countries": countries,
            "dates": plan_data.get("dates"),
            "travelers": plan_data.get("travelers", {}),
            "musts": plan_data.get("musts", []),
            "preferences": plan_data.get("preferences", {})
        }
        
        
        result = self.graph_bridge.execute_tool("city_recommender", args)
        
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def _discover_pois(self, plan_data: Dict[str, Any], research_results: Dict[str, Any]) -> Dict[str, Any]:
        """Discover POIs using POI discovery tool"""
        cities = research_results.get("cities", [])
        
        # Build city_country_map from research results or planning data
        city_country_map = research_results.get("city_country_map", {})
        if not city_country_map and cities:
            # Fallback: assume cities are in the first country from planning data
            countries = plan_data.get("countries", [])
            if countries:
                country = countries[0].get("country", "Unknown")
                city_country_map = {city: country for city in cities}
        
        args = {
            "cities": cities,
            "city_country_map": city_country_map,
            "travelers": plan_data.get("travelers", {}),
            "musts": plan_data.get("musts", []),
            "preferences": plan_data.get("preferences", {})
        }
        
        result = self.graph_bridge.execute_tool("poi_discovery", args)
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def _discover_restaurants(self, plan_data: Dict[str, Any], research_results: Dict[str, Any]) -> Dict[str, Any]:
        """Discover restaurants using restaurant discovery tool"""
        # PATCH #3: Read from the correct level: poi -> poi_by_city
        cities = research_results.get("cities", [])
        poi_block = research_results.get("poi", {})
        poi_by_city = poi_block.get("poi_by_city", {}) if isinstance(poi_block, dict) else {}

        # Ensure schema expected by the restaurants tool
        pois_by_city = {city: poi_by_city.get(city, []) for city in cities}
        
        args = {
            "cities": cities,
            "pois_by_city": pois_by_city,
            "travelers": plan_data.get("travelers", {}),
            "musts": plan_data.get("musts", []),
            "preferences": plan_data.get("preferences", {})
        }
        
        result = self.graph_bridge.execute_tool("restaurants_discovery", args)
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def _gather_city_fares(self, plan_data: Dict[str, Any], research_results: Dict[str, Any]) -> Dict[str, Any]:
        """Gather city fares using city fare tool"""
        cities = research_results.get("cities", [])
        
        args = {
            "cities": cities,
            "city_country_map": research_results.get("city_country_map", {}),
            "preferences": plan_data.get("preferences", {}),
            "travelers": plan_data.get("travelers", {}),
            "musts": plan_data.get("musts", [])
        }
        
        result = self.graph_bridge.execute_tool("city_fare", args)
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def _gather_intercity_fares(self, plan_data: Dict[str, Any], research_results: Dict[str, Any]) -> Dict[str, Any]:
        """Gather intercity fares using intercity fare tool"""
        cities = research_results.get("cities", [])
        
        args = {
            "cities": cities,
            "city_country_map": research_results.get("city_country_map", {}),
            "preferences": plan_data.get("preferences", {}),
            "travelers": plan_data.get("travelers", {}),
            "musts": plan_data.get("musts", [])
        }
        
        result = self.graph_bridge.execute_tool("intercity_fare", args)
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def _gather_currency_data(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gather currency data using FX oracle tool"""
        target_currency = plan_data.get("target_currency", "EUR")
        countries = [{"country": c["country"]} for c in plan_data.get("countries", [])]
        
        args = {
            "target_currency": target_currency,
            "countries": countries,
            "preferences": plan_data.get("preferences", {})
        }
        
        result = self.graph_bridge.execute_tool("currency", args)
        if result.get("status") == "success":
            return result["result"]
        else:
            return {"error": result.get("error", "Unknown error")}
    
    def process_message(self, message) -> Optional[Any]:
        """Process incoming messages"""
        # Simple implementation for LangGraph compatibility
        return None
