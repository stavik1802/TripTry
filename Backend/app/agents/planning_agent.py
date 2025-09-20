# Planning Agent - Interprets user requests and creates plans
from typing import Any, Dict, List, Optional
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentContext
from .graph_integration import AgentGraphBridge
from .common_schema import STANDARD_TOOL_NAMES, AgentDataSchema

# --- Mapping from the interpreter's 6 canonical tools → legacy tool ids used elsewhere ---
_INTERPRETER_TO_LEGACY = {
    "cities.recommender": "city_recommender",
    "poi.discovery": "poi_discovery",
    "restaurants.discovery": "restaurants_discovery",
    "fares.city": "city_fare",
    "fares.intercity": "intercity_fare",
    "fx.oracle": "currency",
}

def _map_interpreter_tools_to_legacy(tools: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for t in tools or []:
        mapped = _INTERPRETER_TO_LEGACY.get(t)
        if mapped and mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    return out

def _flatten_cities_from_countries(countries: List[Dict[str, Any]]) -> List[str]:
    flat: List[str] = []
    for c in countries or []:
        for city in c.get("cities", []) or []:
            if city and city not in flat:
                flat.append(city)
    return flat


class PlanningAgent(MemoryEnhancedBaseAgent):
    """Agent responsible for interpreting user requests and creating plans"""
    
    def __init__(self):
        super().__init__("planning_agent", "planner")
        self.capabilities = ["interpret_user_request", "create_tool_plan", "coordinate_agents"]
        self.dependencies = []  # This agent doesn't depend on others initially
        self.graph_bridge = AgentGraphBridge()
    
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute planning task"""
        self.update_status("working")
        
        user_request = context.user_request
        
        try:
            # Use the interpreter tool through the bridge
            interpreter_result = self.graph_bridge.execute_tool("interpreter", {"user_request": user_request})
            
            if interpreter_result.get("status") == "error":
                return {
                    "status": "error",
                    "error": interpreter_result.get("error", "Unknown interpreter error"),
                    "agent_id": self.agent_id
                }
            
            interpretation = interpreter_result.get("result")
            
            print(f"[DEBUG] Planning agent - interpreter result: {interpreter_result}")
            print(f"[DEBUG] Planning agent - interpretation: {interpretation}")
            
            # Handle case where interpretation might not have model_dump method
            if hasattr(interpretation, 'model_dump'):
                plan_data = interpretation.model_dump()
            else:
                plan_data = interpretation if isinstance(interpretation, dict) else {"intent": "unknown"}
            
            print(f"[DEBUG] Planning agent - plan_data: {plan_data}")
            
            # Ensure a flat 'cities' list (union of countries[].cities) for downstream agents/tests
            if not plan_data.get("cities"):
                plan_data["cities"] = _flatten_cities_from_countries(plan_data.get("countries", []))

            # Prefer the interpreter's tool_plan mapped to legacy names used by other agents/tests
            legacy_tool_plan = _map_interpreter_tools_to_legacy(plan_data.get("tool_plan", []))

            print(f"[DEBUG] Planning agent - legacy_tool_plan: {legacy_tool_plan}")

            # Fallback to legacy builder if the interpreter didn't choose tools
            if not legacy_tool_plan:
                legacy_tool_plan = self._create_tool_plan(plan_data)

            # Persist tool plan back into plan_data (so everyone reads the same)
            plan_data["tool_plan"] = legacy_tool_plan

            # Create tool plan based on interpretation (already done), store in shared data
            context.shared_data["planning_data"] = plan_data
            context.shared_data["tool_plan"] = legacy_tool_plan
            
            self.update_status("completed")
            
            return {
                "status": "success",
                "agent_id": self.agent_id,
                "planning_data": plan_data,
                "tool_plan": legacy_tool_plan
            }
            
        except Exception as e:
            self.update_status("error")
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id
            }
    
    def _create_tool_plan(self, plan_data: Dict[str, Any]) -> List[str]:
        """Create a tool execution plan based on interpretation using standardized tool names.
        This is kept as a fallback when the interpreter doesn't return a tool_plan."""
        tool_plan: List[str] = []
        
        # Always include basic discovery tools if countries present (city recommender)
        if plan_data.get("countries"):
            tool_plan.append(STANDARD_TOOL_NAMES["city_recommender"])
        
        # If specific cities are present, queue the per-city discovery tools
        if plan_data.get("cities"):
            tool_plan.extend([
                STANDARD_TOOL_NAMES["poi_discovery"],
                STANDARD_TOOL_NAMES["restaurants_discovery"],
                STANDARD_TOOL_NAMES["city_fare"],
                STANDARD_TOOL_NAMES["intercity_fare"]
            ])
        
        # Add currency tool if needed
        if plan_data.get("target_currency") or plan_data.get("countries"):
            tool_plan.append(STANDARD_TOOL_NAMES["currency"])
        
        # Add cost calculation and optimization
        tool_plan.extend([
            STANDARD_TOOL_NAMES["discoveries_costs"],
            STANDARD_TOOL_NAMES["optimizer"]
        ])
        
        # Add output generation
        tool_plan.extend([
            STANDARD_TOOL_NAMES["trip_maker"],
            STANDARD_TOOL_NAMES["writer_report"]
        ])
        
        return tool_plan
    
    def process_message(self, message) -> Optional[Any]:
        """Process incoming messages"""
        # Simple implementation for LangGraph compatibility
        return None
