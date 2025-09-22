"""
Agent Coordination System with LangGraph Integration

This module implements the core coordination system for the TripPlanner multi-agent system
using LangGraph. It orchestrates the workflow between specialized agents, manages state
transitions, handles message passing, and ensures robust execution with error handling
and performance monitoring.

ARCHITECTURE OVERVIEW:
=====================
The coordinator uses a LangGraph-based state machine to manage agent interactions:

1. COORDINATOR NODE    - Initializes the workflow and sets up agent states
2. PLANNING AGENT     - Interprets user requests and creates execution plans
3. RESEARCH AGENT     - Gathers data using external tools (POIs, restaurants, fares)
4. GAP AGENT         - Identifies and fills missing data gaps
5. BUDGET AGENT      - Optimizes costs and creates detailed itineraries
6. OUTPUT AGENT      - Generates human-readable responses
7. LEARNING AGENT    - Analyzes performance and learns from interactions
8. ERROR HANDLER     - Manages errors and provides fallback responses

WORKFLOW FEATURES:
=================
- Message-driven communication between agents
- Canonical state management with shared data buckets
- Telemetry and performance monitoring
- SLA (Service Level Agreement) timeout handling
- Retry logic with bounded attempts
- Gap detection and automatic data filling
- Error recovery and fallback mechanisms
- Memory persistence across sessions

STATE MANAGEMENT:
================
The system maintains a canonical state with these key data buckets:
- planning_data: Initial request interpretation
- research_data: Gathered information from tools
- budget_data: Cost analysis and optimization
- trip_data: Complete trip plans
- geocost_data: Geographic and cost information
- optimized_data: Optimized itineraries

ROUTING LOGIC:
=============
The coordinator implements intelligent routing:
- Sequential workflow with conditional branching
- Gap detection after research phase
- SLA-aware shortcuts for time-critical requests
- Retry mechanisms with exponential backoff
- Error handling with graceful degradation

USAGE:
======
coordinator = AgentCoordinator()
coordinator.register_agent("planning_agent", PlanningAgent())
coordinator.register_agent("research_agent", ResearchAgent())
# ... register other agents

graph = coordinator.build_agent_graph()
result = graph.invoke(initial_state)
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
import uuid

from langgraph.graph import StateGraph, END

from app.agents.agent_state import AgentState, AgentMessage, AgentStatus, AgentMemory
from app.agents.base_agent import BaseAgent, AgentContext
from app.agents.utils.memory_system import MemorySystem
from app.agents.learning_agent import LearningAgent
from app.database.mongo_store import MongoStore

# Robust imports (support both spellings for research agent)
try:
    from app.agents.planning_agent import PlanningAgent  
except ImportError as e:
    class PlanningAgent(BaseAgent):  # fallback
        def __init__(self): super().__init__("planning_agent", "planner")
        def process_message(self, m): return None
        def execute_task(self, ctx: AgentContext): return {"status": "success"}

try:
    from app.agents.reasearch_agent import ResearchAgent  
except ImportError as e:
    class ResearchAgent(BaseAgent):  # fallback
        def __init__(self): super().__init__("research_agent", "researcher")
        def process_message(self, m): return None
        def execute_task(self, ctx: AgentContext): return {"status": "success"}

try:
    from app.agents.budget_agent import BudgetAgent  
except ImportError as e:
    class BudgetAgent(BaseAgent):
        def __init__(self): super().__init__("budget_agent", "budget_manager")
        def process_message(self, m): return None
        def execute_task(self, ctx: AgentContext): return {"status": "success"}

try:
    from app.agents.gap_agent import GapAgent  
except ImportError as e:
    class GapAgent(BaseAgent):
        def __init__(self): super().__init__("gap_agent", "gap_filler")
        def process_message(self, m): return None
        def execute_task(self, ctx: AgentContext): return {"status": "success"}
        def identify_missing_data(self, state: Dict[str, Any]): return []

try:
    from app.agents.output_agent import OutputAgent  
except ImportError as e:
    class OutputAgent(BaseAgent):
        def __init__(self): super().__init__("output_agent", "response_formatter")
        def process_message(self, m): return None
        def execute_task(self, ctx: AgentContext): return {
            "status": "success",
            "message": "No output agent present."
        }

MAX_RESEARCH_RETRIES = 2
MAX_BUDGET_RETRIES = 2


class AgentCoordinator:
    """LangGraph coordinator with message-driven communication, canonical state, telemetry, and SLA handling."""

    def __init__(self):
        """Initialize the coordinator with communication protocols and memory system."""
        self.agents: Dict[str, BaseAgent] = {}
        self.communication_protocols = {}
        self.coordination_strategies = {
            "sequential": self._sequential_coordination,
            "parallel": self._parallel_coordination,
            "collaborative": self._collaborative_coordination,
        }
        # Initialize memory system
        self.memory_system = MemorySystem()
        # Optional Mongo store for per-agent outputs/errors
        try:
            self.store = MongoStore()
        except Exception:
            self.store = None
        self.setup_coordination_protocols()

    def setup_coordination_protocols(self):
        """Set up communication protocols between agents with timeouts and required fields."""
        # Metadata (docs/telemetry)
        self.communication_protocols = {
            "planning_to_research": {
                "message_type": "research_request",
                "required_fields": ["plan", "tool_plan", "user_request"],
                "response_expected": True,
                "timeout": 300,
            },
            "research_to_budget": {
                "message_type": "budget_request",
                "required_fields": ["research_results", "cost_data"],
                "response_expected": True,
                "timeout": 300,
            },
            "budget_to_response": {
                "message_type": "response_request",
                "required_fields": ["optimized_itinerary", "cost_analysis"],
                "response_expected": True,
                "timeout": 300,
            },
        }

    def register_agent(self, agent_id: str, agent: BaseAgent):
        """Register an agent with the coordinator."""
        self.agents[agent_id] = agent

    def create_initial_state(
        self, user_request: str, user_id: str = "anonymous", context: Any = None
    ) -> AgentState:
        """Create initial agent state with queues/counters primed."""
        session_id = str(uuid.uuid4())
        
        # Extract conversation history from context if available
        conversation_history = []
        if context and hasattr(context, 'conversation_history'):
            conversation_history = context.conversation_history
        
        return AgentState(
            session_id=session_id,
            user_request=user_request,
            conversation_history=conversation_history,
            agent_statuses={},
            agent_memories={},
            message_queue=[],            # central queue
            message_history=[],
            user_id=user_id,
            planning_data={},
            research_data={},            # canonical buckets live here
            budget_data={},
            final_response=None,
            current_agent="planning_agent",
            next_agent=None,
            coordination_strategy="sequential",
            error_handling_mode="retry",
            start_time=datetime.now(),
            processing_steps=[],
            performance_metrics={}
        )

    # ---------- Graph ----------

    def build_agent_graph(self) -> StateGraph:
        """Build the LangGraph state machine with all agent nodes and routing logic."""
        g = StateGraph(AgentState)

        g.add_node("coordinator", self.coordinator_node)
        g.add_node("planning_agent", self.planning_agent_node)
        g.add_node("research_agent", self.research_agent_node)
        g.add_node("budget_agent", self.budget_agent_node)
        g.add_node("response_agent", self.response_agent_node)
        g.add_node("gap_agent", self.gap_agent_node)
        g.add_node("learning_agent", self.learning_agent_node)
        g.add_node("error_handler", self.error_handler_node)

        g.set_entry_point("coordinator")
        g.add_edge("coordinator", "planning_agent")

        g.add_conditional_edges(
            "planning_agent",
            self.route_after_planning,
            {
                "research_agent": "research_agent",
                "gap_agent": "gap_agent",
                "error_handler": "error_handler",
                "response_agent": "response_agent",
            },
        )
        g.add_conditional_edges(
            "research_agent",
            self.route_after_research,
            {
                "budget_agent": "budget_agent",
                "gap_agent": "gap_agent",
                "research_agent": "research_agent",
                "error_handler": "error_handler",
                "response_agent": "response_agent",
            },
        )
        g.add_conditional_edges(
            "budget_agent",
            self.route_after_budget,
            {
                "budget_agent": "budget_agent",
                "gap_agent": "gap_agent",
                "response_agent": "response_agent",
                "error_handler": "error_handler",
            },
        )

        g.add_edge("gap_agent", "budget_agent")  # after patching, continue to budget
        g.add_edge("response_agent", "learning_agent")  # learn from the completed workflow
        g.add_edge("learning_agent", END)
        g.add_edge("error_handler", END)

        return g.compile()

    # Back-compat alias (older callers)
    def build_coordination_graph(self):
        """Backward compatibility alias for build_agent_graph."""
        return self.build_agent_graph()

    # ---------- Node implementations (message-driven + telemetry) ----------

    def planning_agent_node(self, state: AgentState) -> AgentState:
        """Execute planning agent to interpret user request and create execution plan."""
        t0 = datetime.now()
        try:
            self._set_status(state, "planning_agent", "working", "interpret_user_request")
            agent = self._require("planning_agent")

            # seed a task request
            self._enqueue(state, AgentMessage(
                sender="coordinator",
                recipient="planning_agent",
                message_type="task_request",
                content={"user_request": state.get("user_request", "")},
                requires_response=False
            ))
            self._drain_queue(state, max_steps=4)

            # execute planning
            ctx = self._ctx(state)
            result = agent.execute_task(ctx) or {}
            
            # Sync context changes back to state
            self._sync_context_to_state(state, ctx)
            try:
                pd = state.get("planning_data", {}) or {}
                print(f"[TRACE] Coordinator after planning: planning_data keys={list(pd.keys())}; cities={pd.get('cities')} countries_count={len(pd.get('countries', []))}")
            except Exception:
                pass
            
            # Store planning data properly
            planning_data = result.get("planning_data")
            if planning_data is not None:
                state["planning_data"] = planning_data
            else:
                state["planning_data"] = result

            # Persist tool_plan to state and embed into planning_data 
            if "tool_plan" in result:
                state["tool_plan"] = result["tool_plan"]
            elif "tool_plan" in ctx.shared_data:
                state["tool_plan"] = ctx.shared_data["tool_plan"]
            if isinstance(state.get("planning_data"), dict):
                state["planning_data"]["tool_plan"] = state.get("tool_plan", [])
            # -----------------------------------------------------------------------

            # Store comprehensive memory for planning agent
            state["agent_memories"]["planning_agent"] = AgentMemory(
                agent_id="planning_agent", 
                session_data=result,
                conversation_history=state.get("conversation_history", []),
                learned_preferences=result.get("learned_preferences", {}),
                performance_metrics={
                    "execution_time": (datetime.now() - t0).total_seconds(),
                    "success": True,
                    "data_quality": len(result.get("planning_data", {}))
                }
            )
            # Persist per-agent output
            try:
                if self.store:
                    self.store.log_agent_output(
                        run_id=ctx.shared_data.get("run_id"),
                        agent_name="planning_agent",
                        payload={"status": "success", "output": result},
                        step="planning",
                    )
            except Exception:
                pass

            # notify research
            self._enqueue(state, AgentMessage(
                sender="planning_agent",
                recipient="research_agent",
                message_type="research_request",
                content=result,
                requires_response=True
            ))
            self._drain_queue(state, max_steps=4)

            state["next_agent"] = "research_agent"
            self._telemetry(state, "planning_agent", "planning", True, (datetime.now() - t0).total_seconds())
        except Exception as e:
            self._set_error(state, "planning_agent", str(e))
            state["next_agent"] = "error_handler"
            self._telemetry(state, "planning_agent", "planning", False, (datetime.now() - t0).total_seconds())
            # Persist structured error metadata
            try:
                if hasattr(self, 'store') and self.store:
                    import traceback, hashlib
                    tb = traceback.format_exc()
                    digest = hashlib.sha256(tb.encode("utf-8")).hexdigest()
                    run_ref = state.get("run_id") or state.get("session_id")
                    self.store.append_log(
                        run_ref,
                        {
                            "level": "error",
                            "agent": "planning_agent",
                            "step": "planning",
                            "message": str(e),
                            "trace_hash": digest,
                        },
                    )
            except Exception:
                pass
            return state
        # Ensure mutated state is returned so graph persists changes
        return state

    def research_agent_node(self, state: AgentState) -> AgentState:
        """Execute research agent to gather data using external tools."""
        t0 = datetime.now()
        try:
            self._set_status(state, "research_agent", "working", "gather_research_data")
            agent = self._require("research_agent")

            # deliver any pending research_request first
            self._drain_queue(state, max_steps=8)

            # execute research
            ctx = self._ctx(state)
            result = agent.execute_task(ctx) or {}
            
            # Sync context changes back to state
            self._sync_context_to_state(state, ctx)
            try:
                pd = state.get("planning_data", {}) or {}
                rd = state.get("research_data", {}) or {}
                print(f"[TRACE] Coordinator after research: planning_cities={pd.get('cities')} research_keys={list(rd.keys())}")
            except Exception:
                pass
            
            # merge canonical research outputs (agent returns {"status","research_data",...})
            research_data = result.get("research_data")
            if research_data is not None:
                state["research_data"] = research_data
            else:
                if hasattr(ctx, 'shared_data') and ctx.shared_data.get("research_data"):
                    state["research_data"] = ctx.shared_data["research_data"]
                else:
                    print(f"[DEBUG] No research data found in result or context")
                    print(f"[DEBUG] Result keys: {list(result.keys())}")
                    print(f"[DEBUG] Context shared_data keys: {list(ctx.shared_data.keys())}")

            # Store comprehensive memory for research agent
            # ----  Robust POI counting for list/dict variants ----
            poi_by_city = state["research_data"].get("poi", {}).get("poi_by_city", {})
            pois_found = 0
            for v in poi_by_city.values():
                if isinstance(v, dict):
                    pois_found += len(v.get("pois", []))
                elif isinstance(v, list):
                    pois_found += len(v)
            # ----------------------------------------------------------------
            state["agent_memories"]["research_agent"] = AgentMemory(
                agent_id="research_agent", 
                session_data=state["research_data"],
                conversation_history=state.get("conversation_history", []),
                learned_preferences=state["research_data"].get("learned_preferences", {}),
                performance_metrics={
                    "execution_time": (datetime.now() - t0).total_seconds(),
                    "success": True,
                    "data_quality": len(state["research_data"]),
                    "cities_found": len(state["research_data"].get("cities", [])),
                    "pois_found": pois_found
                }
            )
            try:
                if self.store:
                    self.store.log_agent_output(
                        run_id=ctx.shared_data.get("run_id"),
                        agent_name="research_agent",
                        payload={"status": "success", "output": state.get("research_data", {})},
                        step="research",
                    )
            except Exception:
                pass

            # notify budget (SLA shortcut handled in routing)
            self._enqueue(state, AgentMessage(
                sender="research_agent",
                recipient="budget_agent",
                message_type="budget_request",
                content=state["research_data"],
                requires_response=True
            ))
            self._drain_queue(state, max_steps=8)

            state["next_agent"] = "budget_agent"
            self._telemetry(state, "research_agent", "research", True, (datetime.now() - t0).total_seconds())
        except Exception as e:
            self._set_error(state, "research_agent", str(e))
            state["next_agent"] = "error_handler"
            self._telemetry(state, "research_agent", "research", False, (datetime.now() - t0).total_seconds())
            try:
                if hasattr(self, 'store') and self.store:
                    import traceback, hashlib
                    tb = traceback.format_exc()
                    digest = hashlib.sha256(tb.encode("utf-8")).hexdigest()
                    run_ref = state.get("run_id") or state.get("session_id")
                    self.store.append_log(
                        run_ref,
                        {
                            "level": "error",
                            "agent": "research_agent",
                            "step": "research",
                            "message": str(e),
                            "trace_hash": digest,
                        },
                    )
            except Exception:
                pass
            return state
        # Ensure mutated state is returned so graph persists changes
        return state

    def budget_agent_node(self, state: AgentState) -> AgentState:
        """Execute budget agent to optimize costs and create detailed itineraries."""
        t0 = datetime.now()
        try:
            self._set_status(state, "budget_agent", "working", "optimize_budget")
            agent = self._require("budget_agent")

            # deliver pending budget_request
            self._drain_queue(state, max_steps=8)

            # execute budget optimization
            ctx = self._ctx(state)
            result = agent.execute_task(ctx) or {}
            
            # Sync context changes back to state
            self._sync_context_to_state(state, ctx)
            
            # Store all budget-related data
            if result.get("budget_data"):
                state["budget_data"] = result["budget_data"]
                print(f"[DEBUG] Budget agent - stored budget_data: {list(result['budget_data'].keys()) if isinstance(result['budget_data'], dict) else 'not dict'}")
            if result.get("geocost_data"):
                state["geocost_data"] = result["geocost_data"]
                print(f"[DEBUG] Budget agent - stored geocost_data: {list(result['geocost_data'].keys()) if isinstance(result['geocost_data'], dict) else 'not dict'}")
            if result.get("optimized_data"):
                state["optimized_data"] = result["optimized_data"]
                print(f"[DEBUG] Budget agent - stored optimized_data: {list(result['optimized_data'].keys()) if isinstance(result['optimized_data'], dict) else 'not dict'}")
            if result.get("trip_data"):
                state["trip_data"] = result["trip_data"]
                print(f"[DEBUG] Budget agent - stored trip_data: {list(result['trip_data'].keys()) if isinstance(result['trip_data'], dict) else 'not dict'}")
                if isinstance(result['trip_data'], dict) and result['trip_data'].get('request', {}).get('trip', {}).get('days'):
                    print(f"[DEBUG] Budget agent - trip has {len(result['trip_data']['request']['trip']['days'])} days")

            # Store comprehensive memory for budget agent
            state["agent_memories"]["budget_agent"] = AgentMemory(
                agent_id="budget_agent", 
                session_data=state["budget_data"],
                conversation_history=state.get("conversation_history", []),
                learned_preferences=state["budget_data"].get("learned_preferences", {}),
                performance_metrics={
                    "execution_time": (datetime.now() - t0).total_seconds(),
                    "success": True,
                    "data_quality": len(state["budget_data"]),
                    "trip_created": bool(state.get("trip_data")),
                    "optimization_success": bool(state.get("optimized_data"))
                }
            )
            try:
                if self.store:
                    self.store.log_agent_output(
                        run_id=ctx.shared_data.get("run_id"),
                        agent_name="budget_agent",
                        payload={
                            "status": "success",
                            "output": {
                                "budget_data": state.get("budget_data"),
                                "geocost_data": state.get("geocost_data"),
                                "optimized_data": state.get("optimized_data"),
                                "trip_data": state.get("trip_data"),
                            },
                        },
                        step="budget",
                    )
            except Exception:
                pass

            # notify response
            self._enqueue(state, AgentMessage(
                sender="budget_agent",
                recipient="response_agent",
                message_type="response_request",
                content=state["budget_data"],
                requires_response=False
            ))
            self._drain_queue(state, max_steps=4)

            state["next_agent"] = "response_agent"
            self._telemetry(state, "budget_agent", "budget", True, (datetime.now() - t0).total_seconds())
        except Exception as e:
            self._set_error(state, "budget_agent", str(e))
            state["next_agent"] = "error_handler"
            self._telemetry(state, "budget_agent", "budget", False, (datetime.now() - t0).total_seconds())
            try:
                if hasattr(self, 'store') and self.store:
                    import traceback, hashlib
                    tb = traceback.format_exc()
                    digest = hashlib.sha256(tb.encode("utf-8")).hexdigest()
                    run_ref = state.get("run_id") or state.get("session_id")
                    self.store.append_log(
                        run_ref,
                        {
                            "level": "error",
                            "agent": "budget_agent",
                            "step": "budget",
                            "message": str(e),
                            "trace_hash": digest,
                        },
                    )
            except Exception:
                pass
            return state
        # Ensure mutated state is returned so graph persists changes
        return state

    def response_agent_node(self, state: AgentState) -> AgentState:
        """Execute response agent to generate final user response."""
        try:
            self._set_status(state, "response_agent", "working", "generate_final_response")

            # Prefer OutputAgent if registered
            if "output_agent" in self.agents:
                ctx = self._ctx(state)
                response = self.agents["output_agent"].execute_task(ctx)
            else:
                response = self._fallback_response(state)

            state["final_response"] = response
            self._set_status(state, "response_agent", "completed", None)
            try:
                if self.store:
                    self.store.log_agent_output(
                        run_id=state.get("session_id"),  # fallback if run_id missing in ctx
                        agent_name="output_agent",
                        payload={"status": "success", "output": response},
                        step="output",
                    )
            except Exception:
                pass
        except Exception as e:
            self._set_error(state, "response_agent", str(e))
            try:
                if hasattr(self, 'store') and self.store:
                    import traceback, hashlib
                    tb = traceback.format_exc()
                    digest = hashlib.sha256(tb.encode("utf-8")).hexdigest()
                    run_ref = state.get("run_id") or state.get("session_id")
                    self.store.append_log(
                        run_ref,
                        {
                            "level": "error",
                            "agent": "response_agent",
                            "step": "output",
                            "message": str(e),
                            "trace_hash": digest,
                        },
                    )
            except Exception:
                pass
        return state

    def error_handler_node(self, state: AgentState) -> AgentState:
        """Handle errors and provide fallback response."""
        error_agents = [aid for aid, s in state["agent_statuses"].items() if s.status == "error"]
        if error_agents:
            error_details = {
                "failed_agents": error_agents,
                "error_messages": [state["agent_statuses"][aid].error_message for aid in error_agents],
                "session_id": state["session_id"],
            }
            state["final_response"] = {
                "status": "error",
                "message": "Error processing request",
                "details": error_details,
            }
        return state

    def gap_agent_node(self, state: AgentState) -> AgentState:
        """Execute gap agent to identify and fill missing data gaps."""
        try:
            if "gap_agent" not in self.agents:
                state["next_agent"] = "budget_agent"
                return state

            # Prevent multiple gap passes in same run
            if state.get("gap_filling_completed", False):
                state["next_agent"] = "budget_agent"
                return state

            gap: GapAgent = self.agents["gap_agent"]  # type: ignore
            snapshot = self._snapshot(state)
            missing = gap.identify_missing_data(snapshot) or []

            if not missing:
                state["next_agent"] = "budget_agent"
                return state

            # Execute gap inline (no message roundtrip) so patches are applied inside execute_task
            ctx = self._ctx(state)
            result = gap.execute_task(ctx) or {}

            # Sync context changes back to state
            self._sync_context_to_state(state, ctx)

            # Mark as completed to prevent any further gap calls this run
            state["gap_filling_completed"] = True

            # If the gap agent applied patches to research_data via context, refresh in state
            if isinstance(ctx.shared_data.get("research_data"), dict):
                state["research_data"] = ctx.shared_data["research_data"]

            state["next_agent"] = "budget_agent"
            return state

        except Exception as e:
            self._set_error(state, "gap_agent", str(e))
            state["next_agent"] = "error_handler"
            try:
                if hasattr(self, 'store') and self.store:
                    import traceback, hashlib
                    tb = traceback.format_exc()
                    digest = hashlib.sha256(tb.encode("utf-8")).hexdigest()
                    run_ref = state.get("run_id") or state.get("session_id")
                    self.store.append_log(
                        run_ref,
                        {
                            "level": "error",
                            "agent": "gap_agent",
                            "step": "gap",
                            "message": str(e),
                            "trace_hash": digest,
                        },
                    )
            except Exception:
                pass
        return state

    def learning_agent_node(self, state: AgentState) -> AgentState:
        """Execute learning agent to analyze performance and learn from interactions."""
        try:
            if "learning_agent" not in self.agents:
                return state

            learning: LearningAgent = self.agents["learning_agent"]  # type: ignore
            context = AgentContext(
                session_id=state.get("session_id", "unknown"),
                user_request=state.get("user_request", ""),
                conversation_history=state.get("conversation_history", []),
                shared_data=state,
                goals=[],
                constraints=[]
            )
            result = learning.execute_task(context)
            if result.get("status") == "success":
                state["learning_analysis"] = result.get("system_analysis", {})
                state["learning_insights"] = result.get("learning_insights", {})

        except Exception as e:
            print(f"[DEBUG] Learning agent error: {e}")
        return state

    def coordinator_node(self, state: AgentState) -> AgentState:
        """Initialize the coordination workflow and set up agent states."""
        for agent_id in self.agents:
            state["agent_memories"][agent_id] = AgentMemory(agent_id=agent_id)
            state["agent_statuses"][agent_id] = AgentStatus(agent_id=agent_id)

        if "processing_steps" not in state:
            state["processing_steps"] = []
        if "coordination_strategy" not in state:
            state["coordination_strategy"] = "sequential"

        state["processing_steps"].append({
            "step": "coordination_start",
            "timestamp": datetime.now(),
            "details": {"strategy": state["coordination_strategy"]}
        })
        state["research_retries"] = 0
        state["budget_retries"] = 0

        # SLA: allow setting later via context; default None
        state["sla_seconds"] = state.get("sla_seconds", None)

        # Seed a user_request message so Planning can consume it
        self._enqueue(state, AgentMessage(
            sender="user",
            recipient="planning_agent",
            message_type="user_request",
            content={"text": state.get("user_request", "")},
            requires_response=False
        ))
        return state

    # ---------- Routers (bounded retries + gap checks + SLA) ----------

    def route_after_planning(self, state: AgentState) -> str:
        """Route after planning agent completion."""
        if state["agent_statuses"]["planning_agent"].status == "error":
            return "error_handler"
        # Always research first; checking gaps before research causes "everything missing" loops
        return "research_agent"

    def route_after_research(self, state: AgentState) -> str:
        """Route after research agent completion with gap detection and SLA handling."""
        if state["agent_statuses"]["research_agent"].status == "error":
            return "error_handler"

        if self._needs_gap(state):
            return "gap_agent"

        # SLA: if basics are ready and SLA nearly exhausted, go to response
        sla = state.get("sla_seconds")
        if isinstance(sla, (int, float)) and sla > 0:
            if self._elapsed_seconds(state) > max(5.0, sla * 0.9):  # 90% of SLA
                rs = state.get("research_data", {})
                if rs.get("cities") and (rs.get("poi") or rs.get("city_fares") or rs.get("restaurants")):
                    state["next_agent"] = "response_agent"
                    return "response_agent"

        nxt = state.get("next_agent")
        if nxt == "research_agent":
            state["research_retries"] = int(state.get("research_retries", 0)) + 1
            return "research_agent" if state["research_retries"] <= MAX_RESEARCH_RETRIES else "error_handler"
        if nxt == "budget_agent":
            return "budget_agent"
        if nxt == "response_agent":
            return "response_agent"
        return "budget_agent"

    def route_after_budget(self, state: AgentState) -> str:
        """Route after budget agent completion with gap detection and retry logic."""
        if state["agent_statuses"]["budget_agent"].status == "error":
            return "error_handler"

        # If we already have a plan, do not open a new gap cycle
        if state.get("trip_data") or state.get("optimized_data"):
            return "response_agent"

        if self._needs_gap(state):
            return "gap_agent"

        nxt = state.get("next_agent")
        if nxt == "budget_agent":
            state["budget_retries"] = int(state.get("budget_retries", 0)) + 1
            return "budget_agent" if state["budget_retries"] <= MAX_BUDGET_RETRIES else "error_handler"
        return "response_agent"

    # ---------- Message pump ----------

    def _enqueue(self, state: AgentState, msg: AgentMessage):
        """Add message to queue and history."""
        state["message_queue"].append(msg)
        state["message_history"].append(msg)

    def _deliver(self, state: AgentState, msg: AgentMessage):
        """Deliver message to recipient agent."""
        recipient = msg.recipient
        agent = self.agents.get(recipient)
        if not agent:
            return
        try:
            response = agent.receive_message(msg)  # may return reply
            if response:
                state["message_history"].append(response)
                state["message_queue"].append(response)
        except Exception as e:
            self._set_error(state, recipient, f"message delivery failed: {e}")

    def _drain_queue(self, state: AgentState, max_steps: int = 8):
        """Process messages in queue up to max_steps."""
        steps = 0
        while state["message_queue"] and steps < max_steps:
            msg = state["message_queue"].pop(0)
            self._deliver(state, msg)
            steps += 1

    # ---------- Helpers ----------

    def _ctx(self, state: AgentState) -> AgentContext:
        """Create agent context from state with shared data and learned preferences."""
        # Build a new dict but reuse nested dicts from state (so agents can mutate nested data)
        shared = {
            "session_id": state["session_id"],
            "user_request": state.get("user_request"),
            "user_id": state.get("user_id"), 
            "planning_data": state.get("planning_data", {}),
            "research_data": state.get("research_data", {}),
            "trip_data": state.get("trip_data", {}),
            "geocost_data": state.get("geocost_data", {}),
            "optimized_data": state.get("optimized_data", {}),
            "budget_data": state.get("budget_data", {}),
            "gap_data": state.get("gap_data", {}),
            "output_data": state.get("output_data", {}),
            "fx_data": state.get("fx_data", {}),
            "processing_steps": state.get("processing_steps", []),
            "sla_seconds": state.get("sla_seconds"),
            "agent_memories": state.get("agent_memories", {}),
            "tool_plan": state.get("tool_plan", []),  
            "run_id": state.get("run_id"),
        }
        
        # Extract learned preferences from memory
        learned_preferences = {}
        for agent_id, memory in state.get("agent_memories", {}).items():
            if hasattr(memory, 'learned_preferences') and memory.learned_preferences:
                learned_preferences.update(memory.learned_preferences)
        
        return AgentContext(
            session_id=state["session_id"],
            user_request=state.get("user_request", ""),
            conversation_history=state.get("conversation_history", []),
            shared_data=shared,
            goals=[],
            constraints=learned_preferences,  # Use learned preferences as constraints
        )
    
    def _sync_context_to_state(self, state: AgentState, context: AgentContext) -> None:
        """Sync changes from context back to main state."""
        shared_data = context.shared_data
        
        # Update state with any changes made in context
        for key in ["planning_data", "research_data", "trip_data", "geocost_data", 
                   "optimized_data", "budget_data", "gap_data", "output_data", "fx_data", "tool_plan"]:
            if key in shared_data:
                state[key] = shared_data[key]

    def _create_agent_context(self, state: AgentState, task_type: str = None) -> AgentContext:
        """Create agent context from state with task type."""
        shared = {
            "session_id": state["session_id"],
            "user_request": state.get("user_request"),
            "planning_data": state.get("planning_data", {}),
            "research_data": state.get("research_data", {}),
            "trip_data": state.get("trip_data", {}),
            "geocost_data": state.get("geocost_data", {}),
            "optimized_data": state.get("optimized_data", {}),
            "budget_data": state.get("budget_data", {}),
            "gap_data": state.get("gap_data", {}),
            "output_data": state.get("output_data", {}),
            "processing_steps": state.get("processing_steps", []),
            "sla_seconds": state.get("sla_seconds"),
            "task_type": task_type
        }
        return AgentContext(
            session_id=state["session_id"],
            user_request=state.get("user_request", ""),
            conversation_history=state.get("conversation_history", []),
            shared_data=shared,
            goals=[],
            constraints={},
        )

    def _fallback_response(self, state: AgentState) -> Dict[str, Any]:
        """Create fallback response when output agent is not available."""
        return {
            "status": "success",
            "summary": "Final response (fallback assembler).",
            "planning": state.get("planning_data", {}),
            "research": state.get("research_data", {}),
            "budget": state.get("budget_data", {}),
        }

    def _snapshot(self, state: AgentState) -> Dict[str, Any]:
        """Flatten relevant parts of state for gap analysis."""
        snap = {
            "planning_data": state.get("planning_data", {}),
            "research_data": state.get("research_data", {}),
            "budget_data": state.get("budget_data", {}),
        }
        additional_items = {}
        for bucket in snap.values():
            if isinstance(bucket, dict):
                for k, v in bucket.items():
                    if k not in snap:
                        additional_items[k] = v
        snap.update(additional_items)
        return snap

    def _needs_gap(self, state: AgentState) -> bool:
        """Check if gap filling is needed based on current state."""
        # Prevent recursion in same run
        if state.get("gap_filling_completed", False):
            return False

        # Only consider gaps once research_data exists (avoid "everything missing")
        if not state.get("research_data"):
            return False

        # Only try once
        gap_attempts = state.get("gap_filling_attempts", 0)
        if gap_attempts >= 1:
            return False

        if "gap_agent" not in self.agents:
            return False
        try:
            gap: GapAgent = self.agents["gap_agent"]  # type: ignore
            snapshot = self._snapshot(state)
            missing = gap.identify_missing_data(snapshot)
            if missing:
                state["gap_filling_attempts"] = gap_attempts + 1
            return bool(missing)
        except Exception as e:
            return False

    def _merge(self, dest: Dict[str, Any], src: Dict[str, Any]):
        """Shallow merge for canonical research_data updates."""
        if not isinstance(src, dict):
            return
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dest.get(k), dict):
                dest[k].update(v)
            else:
                dest[k] = v

    def _telemetry(self, state: AgentState, agent_id: str, task_type: str, success: bool, response_time: float):
        """Emit performance data to learning agent for analysis."""
        if "learning_agent" not in self.agents:
            return
        msg = AgentMessage(
            sender=agent_id,
            recipient="learning_agent",
            message_type="performance_data",
            content={
                "agent_id": agent_id,
                "task_type": task_type,
                "success": success,
                "response_time": response_time,
                "context": {"session_id": state["session_id"]},
            },
            requires_response=False,
        )
        self._enqueue(state, msg)
        self._drain_queue(state, max_steps=2)

    def _elapsed_seconds(self, state: AgentState) -> float:
        """Calculate elapsed time since workflow start."""
        try:
            return (datetime.now() - state["start_time"]).total_seconds()
        except Exception:
            return 0.0

    def _set_status(self, state: AgentState, agent_id: str, status: str, task: Optional[str]):
        """Set agent status in state."""
        state["agent_statuses"][agent_id] = AgentStatus(
            agent_id=agent_id, status=status, current_task=task
        )

    def _set_error(self, state: AgentState, agent_id: str, msg: str):
        """Set agent error status in state."""
        state["agent_statuses"][agent_id] = AgentStatus(
            agent_id=agent_id, status="error", error_message=msg
        )

    def _require(self, agent_id: str) -> BaseAgent:
        """Require agent to be registered, raise error if not found."""
        if agent_id not in self.agents:
            raise RuntimeError(f"{agent_id} not registered")
        return self.agents[agent_id]

    # strategy placeholders
    def _sequential_coordination(self, *args, **kwargs): 
        """Placeholder for sequential coordination strategy."""
        pass
    def _parallel_coordination(self, *args, **kwargs): 
        """Placeholder for parallel coordination strategy."""
        pass
    def _collaborative_coordination(self, *args, **kwargs): 
        """Placeholder for collaborative coordination strategy."""
        pass
