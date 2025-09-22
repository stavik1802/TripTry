"""
Advanced Multi-Agent System with LangGraph Integration

This is the main orchestrator for the TripPlanner multi-agent system. It coordinates
a team of specialized AI agents to process user trip planning requests through a
sophisticated workflow pipeline.

ARCHITECTURE OVERVIEW:
=====================
The system uses a LangGraph-based workflow where each agent is a node in the graph:

1. PLANNING AGENT    - Interprets user requests and creates execution plans
2. RESEARCH AGENT    - Gathers data using external tools (POIs, restaurants, fares)
3. GAP AGENT        - Identifies and fills missing data gaps
4. BUDGET AGENT     - Optimizes costs and creates detailed itineraries
5. OUTPUT AGENT     - Generates human-readable responses using AI
6. LEARNING AGENT   - Learns from interactions and improves over time


KEY FEATURES:
=============
- SLA-aware processing with timeout handling
- Memory system for conversation history and learning
- Robust error handling and recovery
- Comprehensive logging for debugging
- Adaptive gap filling for missing data
- Learning from user interactions

USAGE:
======
system = AdvancedMultiAgentSystem(sla_seconds=300)
result = system.process_request("Plan a 5-day trip to Paris with $2000 budget")
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
import os

# Core coordination and memory systems
from .coordinator_graph import AgentCoordinator
from app.agents.base_agent import AgentContext
from app.agents.utils.memory_system import MemorySystem
from app.agents.learning_agent import LearningAgent

from app.agents.planning_agent import PlanningAgent
from app.agents.reasearch_agent import ResearchAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.gap_agent import GapAgent
from app.agents.output_agent import OutputAgent


class AdvancedMultiAgentSystem:
    """
    Advanced Multi-Agent System for Trip Planning
    
    This is the main entry point for the TripPlanner system. It orchestrates a team
    of specialized AI agents to process complex trip planning requests (or more simple free text requests) through a
    sophisticated LangGraph-based workflow.
    
    The system provides:
    - Intelligent request interpretation
    - Comprehensive data gathering
    - Cost optimization and itinerary creation
    - Human-readable response generation
    - Learning from user interactions
    - Robust error handling and recovery
    
    Attributes:
        coordinator: LangGraph coordinator managing agent workflow
        memory_system: Persistent memory for conversations and learning
        learning_agent: Agent responsible for learning and adaptation
        agents: Dictionary of all registered agents
        sla_seconds: Service Level Agreement timeout in seconds
        session_id: Current session identifier
        current_state: Current state of the LangGraph execution
    """

    def __init__(self, sla_seconds: Optional[float] = None):
        """
        Initialize the Advanced Multi-Agent System
        
        Args:
            sla_seconds: Service Level Agreement timeout in seconds (default: None for no limit)
        """
        # Initialize the LangGraph coordinator that manages agent workflow
        self.coordinator = AgentCoordinator()

        # Initialize memory system with MongoDB connection
        mongo_uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("MONGODB_DB", "agent_memory")

        # Create memory system with fallback for different versions
        try:
            self.memory_system = MemorySystem(mongo_uri=mongo_uri, db_name=db_name)  
        except TypeError:
            # not really needed but just in case
            self.memory_system = MemorySystem()  

        # Load existing memories from database (non-fatal if fails)
        try:
            self.memory_system.load_from_database()
        except Exception:
            pass

        # Initialize learning agent for adaptive behavior
        self.learning_agent = LearningAgent()
        
        # System state tracking
        self.session_id: Optional[str] = None
        self.current_state: Optional[Dict[str, Any]] = None
        self.sla_seconds = sla_seconds

        # Initialize all specialized agents
        self.agents = {
            "planning_agent": PlanningAgent(),    # Interprets user requests
            "research_agent": ResearchAgent(),    # Gathers data via tools
            "budget_agent": BudgetAgent(),        # Optimizes costs and itineraries
            "gap_agent": GapAgent(),              # Fills missing data gaps
            "output_agent": OutputAgent(),        # Generates human responses
            "learning_agent": self.learning_agent, # Learns from interactions
        }
        
        # Register all agents with the coordinator
        for agent_id, agent in self.agents.items():
            self.coordinator.register_agent(agent_id, agent)

        # Inject shared memory system into agents that support it
        for agent in self.agents.values():
            if hasattr(agent, "memory_system"):
                agent.memory_system = self.memory_system  

    def process_request(
        self,
        user_request: str,
        user_id: str = "anonymous",
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user request through the multi-agent LangGraph pipeline
        
        This is the main entry point for processing trip planning requests. It orchestrates
        the entire workflow from request interpretation to final response generation.
        
        Args:
            user_request: The user's trip planning request (e.g., "Plan a 5-day trip to Paris")
            user_id: Unique identifier for the user (default: "anonymous")
            session_id: Session identifier for conversation continuity (optional)
            context: Additional context data for the request (optional)
            
        Returns:
            Dict containing:
                - status: "success" or "error"
                - response: The generated trip plan or error message
                - session_id: Session identifier for follow-up requests
                - agents_used: List of agents that participated
                - learning_insights: Insights from the learning agent
                - logging: Context data for debugging and analytics
        """
        # Generate or use provided session ID for conversation continuity
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Retrieve conversation history for context-aware processing
            conversation_history: List[Dict[str, Any]] = []
            if self.session_id:
                conversation_history = self.memory_system.get_conversation_history(
                    session_id=self.session_id, user_id=user_id, limit=5
                )

            # Fallback: get recent conversations if no session history
            if not conversation_history and user_id != "anonymous":
                recent_conversations = self.memory_system.get_recent_conversations(
                    user_id=user_id, hours_back=24, limit=3
                )
                conversation_history = recent_conversations

            # Create agent context with conversation history and metadata
            agent_context = AgentContext(
                session_id=self.session_id,
                user_request=user_request,
                conversation_history=conversation_history,
                shared_data={
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "sla_seconds": self.sla_seconds,
                    "is_follow_up": len(conversation_history) > 0,
                    **(context or {}),
                },
                goals=[],
                constraints={},
            )

            # Create initial LangGraph state for the workflow
            initial_state = self.coordinator.create_initial_state(
                user_request=user_request,
                user_id=user_id,
                context=agent_context,
            )
            
            # Pass SLA timeout to state if provided
            if self.sla_seconds:
                initial_state["sla_seconds"] = self.sla_seconds

            # Execute the LangGraph workflow with high recursion limit
            graph = self.coordinator.build_coordination_graph()
            try:
                final_state: Dict[str, Any] = graph.invoke(
                    initial_state,
                    config={"recursion_limit": 200}  # Allow complex workflows
                )
                self.current_state = final_state
            except Exception as e:
                if "recursion limit" in str(e).lower():
                    # Handle recursion limit gracefully with helpful error message
                    error_msg = f"Processing took too many steps (hit recursion limit). Try breaking down your request into smaller parts. Original error: {str(e)}"
                    return {
                        "status": "error",
                        "error": error_msg,
                        "session_id": self.session_id,
                        "logging": {
                            "context": {
                                "session_id": self.session_id,
                                "user_id": user_id,
                                "error": error_msg
                            },
                            "agents": {}
                        }
                    }
                else:
                    # Re-raise other exceptions for proper error handling
                    raise

            # Extract the final response from the workflow state
            final_response = self._extract_final_response(final_state)

            # Store conversation turn for future follow-up requests
            if final_response and self.session_id:
                conversation_turn = len(conversation_history) + 1
                self.memory_system.store_conversation_turn(
                    session_id=self.session_id,
                    user_id=user_id,
                    user_request=user_request,
                    agent_response=final_response,
                    conversation_turn=conversation_turn
                )

            # Learn from the interaction to improve future responses
            self._learn_from_session(user_id, user_request, final_response)

            # Build logging context for analytics and debugging
            logging_context = self._build_logging_context(
                user_id=user_id,
                agent_context=agent_context,
                final_state=final_state,
                final_response=final_response,
            )

            # Return comprehensive result with all relevant information
            return {
                "status": "success",
                "response": final_response,
                "session_id": self.session_id,
                "agents_used": list(self.agents.keys()),
                "learning_insights": self.learning_agent.get_learning_insights(),
                "logging": {
                    "context": logging_context,   # Used by server for MongoDB logging
                    "agents": {},                 # Placeholder for per-agent metrics
                },
            }

        except Exception as e:
            # Handle any unexpected errors gracefully
            return {
                "status": "error",
                "error": str(e),
                "session_id": self.session_id,
                "logging": {
                    "context": {
                        "session_id": self.session_id,
                        "user_id": user_id,
                        "error": str(e),
                    },
                    "agents": {},
                },
            }

    def _extract_final_response(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the final response from the LangGraph execution state
        
        Args:
            final_state: The final state returned by the LangGraph workflow
            
        Returns:
            The final response data or a default message if not found
        """
        if isinstance(final_state, dict) and "final_response" in final_state:
            return final_state["final_response"] or {"message": "No response generated"}
        return {"message": "No response generated"}

    def _learn_from_session(self, user_id: str, user_request: str, response: Dict[str, Any]):
        """
        Learn from the session interaction to improve future responses
        
        This method stores session memories and extracts user preferences
        for continuous learning and personalization.
        
        Args:
            user_id: Unique identifier for the user
            user_request: The original user request
            response: The generated response
        """
        # Store episodic memory of the session for future reference
        self.memory_system.store_memory(
            agent_id="system",
            memory_type="episodic",
            content={
                "user_id": user_id,
                "user_request": user_request,
                "response": response,
                "session_id": self.session_id,
            },
            importance=0.8,
            tags=["session", "user_interaction", user_id],
        )

        # Extract and learn user preferences from the response
        if isinstance(response, dict) and "preferences" in response:
            for pref_type, pref_value in response["preferences"].items():
                self.memory_system.learn_user_preference(
                    user_id=user_id,
                    preference_type=pref_type,
                    preference_value=pref_value,
                    confidence=0.7,
                    session_id=self.session_id,
                )

    def get_agent_status(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status and performance metrics for agents
        
        Args:
            agent_id: Specific agent to query (optional, returns all if None)
            
        Returns:
            Dictionary containing agent status, capabilities, and performance metrics
        """
        if agent_id:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                return {
                    "agent_id": agent_id,
                    "status": agent.status,
                    "capabilities": getattr(agent, "capabilities", []),
                    "performance": agent.get_performance_metrics()
                    if hasattr(agent, "get_performance_metrics")
                    else {},
                }
            else:
                return {"error": f"Agent {agent_id} not found"}

        # Return status for all agents
        return {
            agent_id: {
                "status": agent.status,
                "capabilities": getattr(agent, "capabilities", []),
                "performance": agent.get_performance_metrics()
                if hasattr(agent, "get_performance_metrics")
                else {},
            }
            for agent_id, agent in self.agents.items()
        }

    def get_system_insights(self) -> Dict[str, Any]:
        """
        Get comprehensive system insights and metrics
        
        Returns:
            Dictionary containing system-wide statistics and performance metrics
        """
        return {
            "total_agents": len(self.agents),
            "active_agents": len([a for a in self.agents.values() if a.status == "working"]),
            "memory_stats": self._get_memory_stats(),
            "learning_metrics": self.learning_agent.get_performance_insights("learning_agent"),
            "coordination_protocols": len(self.coordinator.communication_protocols),
        }

    def _get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory system statistics
        
        Returns:
            Dictionary containing memory system status and metrics
        """
        return {
            "total_memories": "N/A",
            "active_learning": True,
            "consolidation_status": "operational",
        }

    def reset_system(self):
        """
        Reset the system state for a fresh start
        
        Clears session ID and current state, useful for testing or
        when starting a completely new conversation flow.
        """
        self.session_id = None
        self.current_state = None

    # ---------- LOGGING AND ANALYTICS HELPERS ----------

    def _build_logging_context(
        self,
        *,
        user_id: str,
        agent_context: AgentContext,
        final_state: Dict[str, Any],
        final_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build comprehensive logging context for analytics and debugging
        
        This method extracts structured trip planning data from various sources
        in the workflow to create a comprehensive context for logging and
        analytics purposes.
        
        Args:
            user_id: Unique identifier for the user
            agent_context: Context from the agent workflow
            final_state: Final state from LangGraph execution
            final_response: The generated response
            
        Returns:
            Dictionary containing structured context data for logging
        """
        # Initialize with basic context information
        ctx: Dict[str, Any] = {
            "session_id": self.session_id,
            "user_id": user_id,
            "is_follow_up": agent_context.shared_data.get("is_follow_up"),
            "timestamp": agent_context.shared_data.get("timestamp"),
            "target_currency": agent_context.shared_data.get("target_currency", "USD"),
        }

        # Define sources to search for structured trip data
        candidates = [
            final_state.get("final_response") if isinstance(final_state, dict) else None,
            final_state,
            final_response,
            agent_context.shared_data,
        ]

        # Helper function to safely extract values from dictionaries
        def pull(obj: Any, key: str, default):
            if isinstance(obj, dict) and key in obj:
                return obj[key]
            return default

        # Extract trip planning data from various sources
        for src in candidates:
            if not isinstance(src, dict):
                continue
            if "countries" not in ctx:
                ctx["countries"] = pull(src, "countries", [])
            if "cities" not in ctx:
                ctx["cities"] = pull(src, "cities", [])
            if "dates" not in ctx:
                ctx["dates"] = pull(src, "dates", {})
            if "travelers" not in ctx:
                ctx["travelers"] = pull(src, "travelers", {})
            if "preferences" not in ctx:
                ctx["preferences"] = pull(src, "preferences", {})
            if "budget_caps" not in ctx:
                ctx["budget_caps"] = pull(src, "budget_caps", {})

        # Ensure all required fields have default values
        ctx.setdefault("countries", [])
        ctx.setdefault("cities", [])
        ctx.setdefault("dates", {})
        ctx.setdefault("travelers", {})
        ctx.setdefault("preferences", {})
        ctx.setdefault("budget_caps", {})

        return ctx
