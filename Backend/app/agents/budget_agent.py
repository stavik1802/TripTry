"""
Budget Agent for TripPlanner Multi-Agent System

This agent handles cost calculation, budget optimization, and trip financial planning.
It processes research data to calculate costs, optimize itineraries, and create detailed
trip plans with budget breakdowns.

Key responsibilities:
- Calculate costs using discoveries_costs tool
- Create city graphs with geocost data
- Optimize itineraries for cost efficiency
- Generate complete trip plans with budget details
- Handle partial success scenarios gracefully

The agent follows a 4-step workflow: cost calculation → city graph creation → 
optimization → trip generation, with comprehensive error handling at each step.
"""

from typing import Any, Dict, List, Optional
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentContext
from app.agents.utils.graph_integration import AgentGraphBridge
from app.core.common_schema import STANDARD_TOOL_NAMES, AgentDataSchema, CostBreakdown

class BudgetAgent(MemoryEnhancedBaseAgent):
    """Agent responsible for budget management and cost optimization"""
    
    def __init__(self):
        super().__init__("budget_agent", "budget_manager")
        self.capabilities = ["calculate_costs", "optimize_budget", "track_expenses"]
        self.dependencies = ["research_agent"]
        self.graph_bridge = AgentGraphBridge()
    
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute budget calculation and optimization task"""
        self.update_status("working")

        # Get research data
        research_data = context.shared_data.get("research_data", {})
        planning_data = context.shared_data.get("planning_data", {})
        
        
        try:
            # Validate input data structure and types
            if not AgentDataSchema.validate_data_structure(research_data, ["cities"], "research_data"):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "Invalid research data structure",
                    "agent_id": self.agent_id,
                }
            
            # Validate data types
            type_schema = {
                "cities": list,
                "poi": dict,
                "restaurants": dict,
                "city_fares": dict,
                "intercity": dict
            }
            if not AgentDataSchema.validate_data_types(research_data, type_schema, "research_data"):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "Invalid research data types",
                    "agent_id": self.agent_id,
                }
            
            # Step 1: Calculate costs using discoveries_costs tool
            cost_payload = {
                "request": {
                    "cities": research_data.get("cities", []),
                    "countries": planning_data.get("countries", []),
                    "travelers": planning_data.get("travelers", {}),
                    "musts": planning_data.get("musts", []),
                    "preferences": planning_data.get("preferences", {})
                },
                "poi_by_city": research_data.get("poi", {}).get("poi_by_city", {}),
                "restaurants_by_city": research_data.get("restaurants", {}).get("names_by_city", {}),
                "city_fares_by_city": research_data.get("city_fares", {}).get("city_fares", {}),
                "intercity_by_city": research_data.get("intercity", {}).get("hops", []),
                "fx": research_data.get("fx", {})
            }

            # Validate tool availability
            if not AgentDataSchema.validate_tool_availability(STANDARD_TOOL_NAMES["discoveries_costs"], self.graph_bridge.available_tools):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "Discoveries costs tool not available",
                    "agent_id": self.agent_id,
                }

            cost_result = self.graph_bridge.execute_tool(STANDARD_TOOL_NAMES["discoveries_costs"], cost_payload)
            
            if cost_result.get("status") != "success":
                self.update_status("error")
                return {
                    "status": "error",
                    "error": cost_result.get("error", "Unknown cost calculation error"),
                    "agent_id": self.agent_id,
                }
            
            cost_data = cost_result.get("result", {})
            context.shared_data["budget_data"] = cost_data
            
            # Step 2: Create city graph using geocost_assembler
            # Handle POIs per city robustly (list or dict with 'pois')
            poi_by_city = research_data.get("poi", {}).get("poi_by_city", {})
            def _city_pois(city: str):
                v = poi_by_city.get(city, [])
                if isinstance(v, dict):
                    return v.get("pois", [])
                return v if isinstance(v, list) else []

            city_graph_payload = {
                "request": {
                    "cities": research_data.get("cities", []),
                    "countries": planning_data.get("countries", []),
                    "travelers": planning_data.get("travelers", {}),
                    "musts": planning_data.get("musts", []),
                    "preferences": planning_data.get("preferences", {}),
                    "discovery": {
                        "cities": {
                            city: {
                                "pois": _city_pois(city),
                                "fares": research_data.get("city_fares", {}).get("city_fares", {}).get(city, {})
                            }
                            for city in research_data.get("cities", [])
                        }
                    }
                }
            }

            # Check city graph tool availability
            if not AgentDataSchema.validate_tool_availability(STANDARD_TOOL_NAMES["city_graph"], self.graph_bridge.available_tools):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "City graph tool not available",
                    "agent_id": self.agent_id,
                }
            
            city_graph_result = self.graph_bridge.execute_tool(STANDARD_TOOL_NAMES["city_graph"], city_graph_payload)
            
            if city_graph_result.get("status") != "success":
                self.update_status("error")
                return {
                    "status": "error",
                    "error": city_graph_result.get("error", "City graph creation failed"),
                    "agent_id": self.agent_id,
                }
            
            geocost_data = city_graph_result.get("result", {}).get("request", {}).get("geocost", {})
            context.shared_data["geocost_data"] = geocost_data
            
            # Step 3: Optimize itinerary using optimizer tool
            optimizer_payload = {
                "request": {
                    "cities": research_data.get("cities", []),
                    "countries": planning_data.get("countries", []),
                    "travelers": planning_data.get("travelers", {}),
                    "musts": planning_data.get("musts", []),
                    "preferences": planning_data.get("preferences", {}),
                    "geocost": geocost_data
                }
            }

            # Check optimizer tool availability
            if not AgentDataSchema.validate_tool_availability(STANDARD_TOOL_NAMES["optimizer"], self.graph_bridge.available_tools):
                self.update_status("error")
                return {
                    "status": "error",
                    "error": "Optimizer tool not available",
                    "agent_id": self.agent_id,
                }
            
            optimizer_result = self.graph_bridge.execute_tool(STANDARD_TOOL_NAMES["optimizer"], optimizer_payload)
            
            if optimizer_result.get("status") != "success":
                self.update_status("error")
                return {
                    "status": "error",
                    "error": optimizer_result.get("error", "Optimization failed"),
                    "agent_id": self.agent_id,
                }
            
            optimized_data = optimizer_result.get("result", {})
            context.shared_data["optimized_data"] = optimized_data
            
            # Step 4: Create trip using trip maker
            trip_maker_payload = {
                "request": {
                    "cities": research_data.get("cities", []),
                    "countries": planning_data.get("countries", []),
                    "travelers": planning_data.get("travelers", {}),
                    "musts": planning_data.get("musts", []),
                    "preferences": planning_data.get("preferences", {}),
                    "dates": planning_data.get("dates", {}),
                    "discovery": city_graph_payload["request"]["discovery"],
                    "geocost": geocost_data
                }
            }

            # Check trip maker tool availability
            if not AgentDataSchema.validate_tool_availability(STANDARD_TOOL_NAMES["trip_maker"], self.graph_bridge.available_tools):
                # Return partial success with available data
                self.update_status("completed")
                return {
                    "status": "partial_success",
                    "agent_id": self.agent_id,
                    "budget_data": cost_data,
                    "geocost_data": geocost_data,
                    "optimized_data": optimized_data,
                    "trip_error": "Trip maker tool not available"
                }
            
            trip_result = self.graph_bridge.execute_tool(STANDARD_TOOL_NAMES["trip_maker"], trip_maker_payload)
            
            if trip_result.get("status") == "success":
                trip_data = trip_result.get("result", {})
                context.shared_data["trip_data"] = trip_data
                if trip_data.get("request", {}).get("trip"):
                    trip = trip_data["request"]["trip"]
                
                self.update_status("completed")
                return {
                    "status": "success",
                    "agent_id": self.agent_id,
                    "budget_data": cost_data,
                    "geocost_data": geocost_data,
                    "optimized_data": optimized_data,
                    "trip_data": trip_data
                }
            else:
                # Return partial success with available data
                self.update_status("completed")
                return {
                    "status": "partial_success",
                    "agent_id": self.agent_id,
                    "budget_data": cost_data,
                    "geocost_data": geocost_data,
                    "optimized_data": optimized_data,
                    "trip_error": trip_result.get("error", "Unknown trip creation error")
                }
                
        except Exception as e:
            self.update_status("error")
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id,
            }
    def process_message(self, message) -> Optional[Any]:
        """Process incoming messages"""
        # Simple implementation for LangGraph compatibility
        return None
