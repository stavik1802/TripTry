# Advanced Multi-Agent System with LangGraph Integration (steps 1–4)
from typing import Any, Dict, Optional
from datetime import datetime

from .agent_coordinator import AgentCoordinator
from .base_agent import AgentContext
from .memory_system import MemorySystem
from .learning_agent import LearningAgent

# robust imports for agent classes used during registration
from .planning_agent import PlanningAgent
try:
    from .research_agent import ResearchAgent
except Exception:
    from .reasearch_agent import ResearchAgent
from .budget_agent import BudgetAgent
from .gap_agent import GapAgent
from .output_agent import OutputAgent


class AdvancedMultiAgentSystem:
    """Advanced multi-agent system with full coordination, learning, and SLA-aware routing"""

    def __init__(self, sla_seconds: Optional[float] = None):
        self.coordinator = AgentCoordinator()
        self.memory_system = MemorySystem(mongo_uri="mongodb+srv://stavos114_db_user:dgtOtRZs3MimkTcK@cluster0.bzqyrad.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", db_name="agent_memory")
        self.learning_agent = LearningAgent()
        self.session_id = None
        self.current_state: Optional[Dict[str, Any]] = None
        self.sla_seconds = sla_seconds

        # Initialize and register agents
        self.agents = {
            "planning_agent": PlanningAgent(),
            "research_agent": ResearchAgent(),
            "budget_agent": BudgetAgent(),
            "gap_agent": GapAgent(),
            "output_agent": OutputAgent(),
            "learning_agent": self.learning_agent,
        }
        for agent_id, agent in self.agents.items():
            self.coordinator.register_agent(agent_id, agent)

        print("[Advanced Multi-Agent System] Initialized with agents:",
              ", ".join(self.agents.keys()))

    def process_request(
        self,
        user_request: str,
        user_id: str = "anonymous",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a user request through the multi-agent LangGraph pipeline"""
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[Advanced Multi-Agent System] Processing request: {user_request[:120]}...")

        try:
            # Create initial agent context (for reference and memory only)
            agent_context = AgentContext(
                session_id=self.session_id,
                user_request=user_request,
                conversation_history=[],
                shared_data={
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "sla_seconds": self.sla_seconds,
                    **(context or {}),
                },
                goals=[],
                constraints={},
            )

            # Create initial LangGraph state
            initial_state = self.coordinator.create_initial_state(
                user_request=user_request,
                user_id=user_id,
                context=agent_context,
            )
            # Pass SLA to state (if provided)
            if self.sla_seconds:
                initial_state["sla_seconds"] = self.sla_seconds

            # Build and run the LangGraph
            graph = self.coordinator.build_coordination_graph()
            final_state: Dict[str, Any] = graph.invoke(initial_state)
            self.current_state = final_state

            # Extract final response
            final_response = self._extract_final_response(final_state)

            # Learn from the interaction
            self._learn_from_session(user_id, user_request, final_response)

            return {
                "status": "success",
                "response": final_response,
                "session_id": self.session_id,
                "agents_used": list(self.agents.keys()),
                "learning_insights": self.learning_agent.get_learning_insights(),
            }

        except Exception as e:
            print(f"[Advanced Multi-Agent System] Error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "session_id": self.session_id,
            }

    def _extract_final_response(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the final response from the final LangGraph state"""
        if isinstance(final_state, dict) and "final_response" in final_state:
            return final_state["final_response"] or {"message": "No response generated"}
        return {"message": "No response generated"}

    def _learn_from_session(self, user_id: str, user_request: str, response: Dict[str, Any]):
        """Learn from the session"""
        # Store session memory
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

        # Learn user preferences (best-effort if present)
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
        """Get status of agents"""
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

        # Return all agent statuses
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
        """Get comprehensive system insights"""
        return {
            "total_agents": len(self.agents),
            "active_agents": len([a for a in self.agents.values() if a.status == "working"]),
            "memory_stats": self._get_memory_stats(),
            "learning_metrics": self.learning_agent.get_performance_insights("learning_agent"),
            "coordination_protocols": len(self.coordinator.communication_protocols),
        }

    def _get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics (placeholder)"""
        return {
            "total_memories": "N/A",
            "active_learning": True,
            "consolidation_status": "operational",
        }

    def reset_system(self):
        """Reset the system state"""
        self.session_id = None
        self.current_state = None
