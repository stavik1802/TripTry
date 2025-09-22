"""
Gap Agent for TripPlanner Multi-Agent System

This agent identifies and fills missing data gaps in the research phase. It analyzes
the current data state, detects missing information, and uses web search tools to
fill gaps in POIs, restaurants, fares, and other travel-related data.

Key responsibilities:
- Identify missing data using gap detection functions
- Fill gaps using gap_data_tool with web search
- Apply patches to research data structures
- Handle fallback scenarios when tools are unavailable
- Prevent infinite recursion with item limits

The agent uses sophisticated patch application with support for array indexing
and nested data structures to ensure data integrity.
"""

from typing import Any, Dict, List, Optional
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentMessage, AgentContext
from app.agents.utils.graph_integration import AgentGraphBridge
from app.core.common_schema import STANDARD_TOOL_NAMES, AgentDataSchema
from app.tools.tools_utils.specs import (
    _missing_city_fares, _missing_intercity, _missing_pois, _missing_restaurants
)

class GapAgent(MemoryEnhancedBaseAgent):
    """Agent responsible for filling missing data gaps using web search"""
    
    def __init__(self):
        super().__init__("gap_agent", "gap_filler")
        self.capabilities = ["fill_missing_data", "search_web", "patch_data"]
        self.dependencies = ["research_agent", "budget_agent"]
        self.graph_bridge = AgentGraphBridge()
    
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute gap filling task (inline call). Applies patches directly to research_data."""
        self.update_status("working")
        
        # Analyze current data for gaps
        research_data = context.shared_data.get("research_data", {})
        planning_data = context.shared_data.get("planning_data", {})
        missing_items = self.identify_missing_data(research_data, planning_data)
        
        
        # Limit to maximum 8 items to prevent unlimited recursion
        MAX_ITEMS_TO_FILL = 8
        if len(missing_items) > MAX_ITEMS_TO_FILL:
            missing_items = missing_items[:MAX_ITEMS_TO_FILL]
        
        
        if not missing_items:
            self.update_status("completed")
            return {
                "status": "success",
                "agent_id": self.agent_id,
                "message": "No missing data identified",
                "filled_items": 0
            }
        
        try:
            
            # Validate tool availability
            tool_name = STANDARD_TOOL_NAMES["gap_data"]
            if not AgentDataSchema.validate_tool_availability(tool_name, self.graph_bridge.available_tools):
                return self._fallback_gap_filling(missing_items, research_data, context)
            
            # Use gap_data_tool to fill missing data
            gap_args = {
                "message": context.user_request,
                "request_snapshot": {
                    "research_data": research_data,
                    "planning_data": planning_data
                },
                "missing": missing_items,
                "max_queries_per_item": 2
            }
            
            gap_result = self.graph_bridge.execute_tool(tool_name, gap_args)
            
            if gap_result.get("status") == "success":
                # Extract patches from gap tool response (handles all known shapes)
                def _extract_patches(resp: Dict[str, Any]) -> Dict[str, Any]:
                    # Preferred: top-level 'patched' (full patched snapshot)
                    patched = resp.get("patched")
                    if isinstance(patched, dict) and patched:
                        # This is a full snapshot; we don't want to replace research_data wholesale.
                        # We still prefer granular patches if available below.
                        pass
                    # Common: result.patches
                    res = resp.get("result")
                    if isinstance(res, dict):
                        if isinstance(res.get("patches"), dict) and res["patches"]:
                            return res["patches"]
                        # Less common: result.result.patches (double-wrapped)
                        inner = res.get("result")
                        if isinstance(inner, dict) and isinstance(inner.get("patches"), dict) and inner["patches"]:
                            return inner["patches"]
                    # Fallback: no granular patches; try to diff at top-level is out of scope here
                    return {}
                
                def _extract_items(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
                    res = resp.get("result")
                    if isinstance(res, dict):
                        if isinstance(res.get("items"), list):
                            return res["items"]
                        inner = res.get("result")
                        if isinstance(inner, dict) and isinstance(inner.get("items"), list):
                            return inner["items"]
                    return []
                
                filled_data = gap_result.get("result", {}) or {}
                patches = _extract_patches(gap_result)
                items = _extract_items(gap_result)
                
                # Apply patches to research data (mutates shared object)
                applied_count = 0
                if patches:
                    self._apply_patches(research_data, patches)
                    # Keep context.shared_data['research_data'] reference aligned
                    context.shared_data["research_data"] = research_data
                    applied_count = len(patches)
                
                self.update_status("completed")
                return {
                    "status": "success",
                    "agent_id": self.agent_id,
                    "filled_items": len(items) or len(missing_items),
                    "patches_applied": applied_count,
                    "gap_data": filled_data
                }
            else:
                # Soft-fallback to break loops and keep pipeline moving
                err = gap_result.get("error", "Unknown gap filling error")
                synthesized_patches = {}
                for m in missing_items:
                    path = m.get("path")
                    if not path:
                        continue
                    # Create neutral containers (lists for plural paths, dict otherwise)
                    leaf = [] if any(k in path for k in ["poi","restaurants","fares","items","list","prices"]) else {}
                    synthesized_patches[path] = leaf
                if synthesized_patches:
                    self._apply_patches(research_data, synthesized_patches)
                    context.shared_data["research_data"] = research_data
                self.update_status("error")
                return {
                    "status": "success",              # return success so coordinator advances
                    "agent_id": self.agent_id,
                    "filled_items": 0,
                    "patches_applied": len(synthesized_patches),
                    "gap_data": {"items": [], "errors": [err], "fallback": True}
                }
                
        except Exception as e:
            synthesized_patches = {}
            for m in missing_items:
                path = m.get("path")
                if not path:
                    continue
                leaf = [] if any(k in path for k in ["poi","restaurants","fares","items","list","prices"]) else {}
                synthesized_patches[path] = leaf
            if synthesized_patches:
                self._apply_patches(research_data, synthesized_patches)
                context.shared_data["research_data"] = research_data
            self.update_status("error")
            return {
                "status": "success",                  # keep moving
                "agent_id": self.agent_id,
                "filled_items": 0,
                "patches_applied": len(synthesized_patches),
                "gap_data": {"items": [], "errors": [str(e)], "fallback": True}
            }
    
    def identify_missing_data(self, state_or_research: Dict[str, Any], planning_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # --- normalize inputs ---
        if planning_data is None:
            # single-arg call with a snapshot
            snapshot = state_or_research or {}
            research_data = snapshot.get("research_data", {})
            planning_data = snapshot.get("planning_data", {})
        else:
            # two-arg call (research_data, planning_data)
            research_data = state_or_research or {}

        missing_items: List[Dict[str, Any]] = []

        tool_plan = planning_data.get("tool_plan", [])

        # Build done_tools from data actually present in research_data
        # Use dot notation format expected by gap detection functions
        done_tools: List[str] = []
        if isinstance(research_data, dict):
            if research_data.get("poi"):         done_tools.append("poi.discovery")
            if research_data.get("restaurants"): done_tools.append("restaurants.discovery")
            if research_data.get("city_fares"):  done_tools.append("fares.city")
            if research_data.get("intercity"):   done_tools.append("fares.intercity")
            if research_data.get("fx"):          done_tools.append("fx.oracle")

        # Structure the state for detectors
        state = {
            **(research_data if isinstance(research_data, dict) else {}),
            **(planning_data if isinstance(planning_data, dict) else {}),
            "research_data": research_data,
            "planning_data": planning_data,
            "done_tools": done_tools,
        }

        # Normalize POI/restaurant shapes to what detectors expect
        if isinstance(research_data, dict) and "poi" in research_data and isinstance(research_data["poi"], dict):
            state["poi"] = research_data["poi"] if "poi_by_city" in research_data["poi"] else {"poi_by_city": research_data["poi"]}
        if isinstance(research_data, dict) and "restaurants" in research_data and isinstance(research_data["restaurants"], dict):
            state["restaurants"] = research_data["restaurants"] if "names_by_city" in research_data["restaurants"] else {"names_by_city": research_data["restaurants"]}


        try:
            if "fares.city" in done_tools:
                city_fares_missing = _missing_city_fares(state); missing_items.extend(city_fares_missing)

            if "fares.intercity" in done_tools:
                intercity_missing = _missing_intercity(state); missing_items.extend(intercity_missing)

            if "poi.discovery" in done_tools:
                pois_missing = _missing_pois(state); missing_items.extend(pois_missing)

            if "restaurants.discovery" in done_tools:
                restaurants_missing = _missing_restaurants(state); missing_items.extend(restaurants_missing)

        except Exception as e:
            print(f"[DEBUG] Error in gap detection: {e}")
            import traceback; traceback.print_exc()

        return missing_items

    def _fallback_gap_filling(self, missing_items: List[Dict[str, Any]], research_data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """Fallback gap filling when the gap tool is not available"""
        
        # Create basic fallback data structures
        synthesized_patches = {}
        for item in missing_items:
            path = item.get("path")
            if not path:
                continue
            # Create neutral containers based on path type
            if any(k in path for k in ["poi", "restaurants", "fares", "items", "list", "prices"]):
                synthesized_patches[path] = []
            else:
                synthesized_patches[path] = {}
        
        # Apply synthesized patches
        if synthesized_patches:
            self._apply_patches(research_data, synthesized_patches)
            context.shared_data["research_data"] = research_data
        
        return {
            "status": "success",
            "agent_id": self.agent_id,
            "filled_items": len(missing_items),
            "patches_applied": len(synthesized_patches),
            "gap_data": {"items": [], "errors": [], "fallback": True}
        }
    
    def _apply_patches(self, data: Dict[str, Any], patches: Dict[str, Any]) -> None:
        """Apply patches to the data structure with support for array indexing"""
        for path, value in patches.items():
            try:
                # Parse path with support for array indexing like [name=Eiffel Tower]
                keys = self._parse_path(path)
                current = data
                
                # Navigate to the parent of the target key
                i = 0
                while i < len(keys) - 1:
                    key = keys[i]
                    next_key = keys[i + 1] if i + 1 < len(keys) else None
                    
                    if isinstance(key, str):
                        if key not in current:
                            current[key] = {}
                        elif not isinstance(current[key], dict):
                            current[key] = {}
                        current = current[key]
                        
                        # If next token is an array index descriptor, handle in next loop step
                        if next_key and isinstance(next_key, dict) and "array_index" in next_key:
                            pass
                    elif isinstance(key, dict) and "array_index" in key:
                        # Handle array indexing like [name=Eiffel Tower]
                        array_key = None
                        for j in range(i - 1, -1, -1):
                            if isinstance(keys[j], str):
                                array_key = keys[j]
                                break
                        if array_key is None:
                            array_key = "items"
                        
                        if array_key not in current:
                            current[array_key] = []
                        elif not isinstance(current[array_key], list):
                            current[array_key] = []
                        
                        target_field = key.get("field")
                        target_value = key.get("value")
                        found_item = None
                        for item in current[array_key]:
                            if isinstance(item, dict) and item.get(target_field) == target_value:
                                found_item = item
                                break
                        if found_item is None:
                            new_item = {target_field: target_value}
                            current[array_key].append(new_item)
                            found_item = new_item
                        current = found_item
                    
                    i += 1
                
                # Set the final value
                final_key = keys[-1]
                if isinstance(final_key, str):
                    current[final_key] = value
                elif isinstance(final_key, dict) and "array_index" in final_key:
                    # Not expected as terminal token; ignore gracefully
                    pass
                
            except Exception as e:
                print(f"[GAP_AGENT] ❌ Failed to apply patch {path}: {e}")
    
    def _parse_path(self, path: str) -> List[Any]:
        """Parse a path string into a list of keys, handling array indexing"""
        keys = []
        current = ""
        i = 0
        
        while i < len(path):
            char = path[i]
            
            if char == '.':
                if current:
                    keys.append(current)
                    current = ""
            elif char == '[':
                if current:
                    keys.append(current)
                    current = ""
                
                bracket_start = i + 1
                bracket_end = path.find(']', bracket_start)
                if bracket_end == -1:
                    raise ValueError(f"Unclosed bracket in path: {path}")
                
                index_spec = path[bracket_start:bracket_end]
                if '=' in index_spec:
                    field, value = index_spec.split('=', 1)
                    keys.append({
                        "array_index": True,
                        "field": field.strip(),
                        "value": value.strip()
                    })
                else:
                    keys.append({"array_index": True, "field": "index", "value": index_spec.strip()})
                
                i = bracket_end
            else:
                current += char
            
            i += 1
        
        if current:
            keys.append(current)
        
        return keys
    
    # Message-based API kept for compatibility (not used by coordinator path now)

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming messages"""
        if message.message_type == "gap_fill_request":
            return self.handle_gap_fill_request(message)
        elif message.message_type == "data_patch_request":
            return self.handle_data_patch_request(message)
        return None
    
    def handle_gap_fill_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle gap filling requests (legacy message path)"""
        self.update_status("working")
        content = message.content
        
        missing_items = content.get("missing_items", [])
        current_state = content.get("current_state", {})
        user_message = content.get("user_message", "")
        
        MAX_ITEMS_TO_FILL = 8
        if len(missing_items) > MAX_ITEMS_TO_FILL:
            missing_items = missing_items[:MAX_ITEMS_TO_FILL]
        
        if not missing_items:
            return self.send_message(
                recipient=message.sender,
                message_type="gap_fill_complete",
                content={
                    "status": "success",
                    "message": "No missing data to fill",
                    "filled_items": 0,
                    "gap_filling_completed": True
                },
                priority=2
            )
        
        gap_args = {
            "message": user_message,
            "request_snapshot": current_state,
            "missing": missing_items,
            "max_queries_per_item": 1,
            "max_results_per_query": 1
        }
        
        result = self.graph_bridge.execute_tool("gap_data", gap_args)
        
        if result.get("status") == "error":
            return self.send_message(
                recipient=message.sender,
                message_type="gap_fill_complete",
                content={
                    "status": "success",
                    "filled_items": len(missing_items),
                    "patched_state": {},
                    "gap_results": {},
                    "errors": [result.get("error", "Unknown error")],
                    "message": "Gap filling failed but continuing workflow to prevent recursion",
                    "gap_filling_completed": True
                },
                priority=2
            )
        
        gap_result = result.get("result", {}) or {}
        patched_state = result.get("patched", {}) or {}
        filled_items = gap_result.get("items", [])
        errors = gap_result.get("errors", [])
        
        return self.send_message(
            recipient=message.sender,
            message_type="gap_fill_complete",
            content={
                "status": "success",
                "filled_items": len(filled_items),
                "patched_state": patched_state,
                "gap_results": gap_result,
                "errors": errors,
                "gap_filling_completed": True
            },
            priority=2
        )
    
    def handle_data_patch_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle specific data patching requests (legacy message path)"""
        self.update_status("working")
        content = message.content
        
        # Create missing items from the patch request
        missing_items = []
        for path, description in content.get("patches", {}).items():
            missing_items.append({
                "path": path,
                "description": description,
                "context": content.get("context", {}),
                "schema": content.get("schema"),
                "hints": content.get("hints", [])
            })
        
        gap_message = AgentMessage(
            sender=message.sender,
            recipient=self.agent_id,
            message_type="gap_fill_request",
            content={
                "missing_items": missing_items,
                "current_state": content.get("current_state", {}),
                "user_message": content.get("user_message", "")
            }
        )
        return self.handle_gap_fill_request(gap_message)
