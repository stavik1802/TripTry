"""
Memory-Enhanced Base Agent for TripPlanner Multi-Agent System

This module provides an enhanced base agent that integrates memory, learning, and caching
capabilities. It extends the basic BaseAgent with sophisticated memory management,
performance tracking, user preference learning, and result caching for improved efficiency.

Key features:
- Integrated memory system with episodic, semantic, and procedural memory
- Performance tracking and learning from interactions
- User preference extraction and learning
- Result caching with TTL for improved response times
- Error learning and analysis for system improvement
- Context enhancement with learned preferences

The agent automatically learns from each interaction, stores relevant memories,
and applies learned preferences to improve future responses.
"""

from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent, AgentMessage, AgentContext
from app.agents.utils.memory_system import MemorySystem
from datetime import datetime
import time
import copy  # For safe result annotation when using cache

class MemoryEnhancedBaseAgent(BaseAgent):
    """Base agent with integrated memory and learning capabilities"""
    
    def __init__(self, agent_id: str, agent_type: str):
        super().__init__(agent_id, agent_type)
        self.memory_system = MemorySystem()
        self.performance_tracker = {}
        self.user_contexts = {}
        self.learning_enabled = True
    
    def execute_task_with_learning(self, context: AgentContext, task_type: str = "general") -> Dict[str, Any]:
        """Execute task with integrated learning and cache reuse."""
        start_time = time.time()
        user_id = context.shared_data.get("user_id", "anonymous")

        # Try cached result first (deep-copied for safety)
        cached = self.memory_system.load_cached_result(
            user_id=user_id,
            task_type=task_type,
            user_request=context.user_request,
            max_age_hours=24,   # change to your preferred TTL
        )
        if cached:
            reused = copy.deepcopy(cached)
            if isinstance(reused, dict):
                reused.setdefault("_meta", {})["_reused_from_cache"] = True
            return reused
        
        try:
            # Retrieve relevant memories
            _ = self._retrieve_relevant_memories(context, task_type)
            
            # Execute task
            result = self.execute_task(context)
            
            # Calculate performance metrics
            response_time = time.time() - start_time
            success = result.get("status") == "success"
            
            # Learn from interaction if enabled
            if self.learning_enabled:
                self._learn_from_interaction(task_type, success, response_time, context, result)
            
            # Store episodic memory
            self._store_episodic_memory(task_type, success, context, result)

            # Save to cache if successful
            if success:
                try:
                    self.memory_system.save_cached_result(
                        agent_id=self.agent_id,
                        user_id=user_id,
                        task_type=task_type,
                        user_request=context.user_request,
                        result=result,
                    )
                except Exception:
                    # Cache failure should not break main flow
                    pass
            
            return result
            
        except Exception as e:
            # Handle errors and learn from them
            response_time = time.time() - start_time
            self._learn_from_error(task_type, str(e), response_time, context)
            raise
    
    def _retrieve_relevant_memories(self, context: AgentContext, task_type: str) -> List[Any]:
        """Retrieve memories relevant to current task"""
        # Get user-specific memories
        user_id = context.shared_data.get("user_id", "anonymous")
        user_memories = self.memory_system.retrieve_memories(
            agent_id=self.agent_id,
            tags=[task_type, user_id],
            limit=5
        )
        
        # Get procedural memories for this task type
        procedural_memories = self.memory_system.retrieve_memories(
            agent_id=self.agent_id,
            memory_type="procedural",
            tags=[task_type],
            limit=3
        )

        # Get global semantic preferences (no agent filter)
        semantic_prefs = self.memory_system.retrieve_memories(
            agent_id=None,                 # Critical: do not filter by agent
            memory_type="semantic",
            tags=[user_id],
            limit=5
        )
        
        return user_memories + procedural_memories + semantic_prefs
    
    def _learn_from_interaction(self, task_type: str, success: bool, response_time: float, 
                              context: AgentContext, result: Dict[str, Any]):
        """Learn from successful/failed interactions"""
        # Update performance metrics
        self.memory_system.learn_from_interaction(
            agent_id=self.agent_id,
            task_type=task_type,
            success=success,
            response_time=response_time,
            context=context.shared_data
        )
        
        # Extract user preferences if available
        user_id = context.shared_data.get("user_id")
        if user_id and success:
            self._extract_and_learn_preferences(user_id, context, result)
    
    def _learn_from_error(self, task_type: str, error_message: str, 
                         response_time: float, context: AgentContext):
        """Learn from errors"""
        user_id = context.shared_data.get("user_id", "anonymous")
        # Include user_id in tags for follow-up retrieval
        self.memory_system.store_memory(
            agent_id=self.agent_id,
            memory_type="episodic",
            content={
                "task_type": task_type,
                "error": error_message,
                "context": context.shared_data,
                "learning_type": "error_analysis"
            },
            importance=0.8,
            tags=["error", task_type, "learning", user_id]  # Added user_id for retrieval
        )
        
        # Update performance metrics
        self.memory_system.learn_from_interaction(
            agent_id=self.agent_id,
            task_type=task_type,
            success=False,
            response_time=response_time,
            context=context.shared_data
        )
    
    def _store_episodic_memory(self, task_type: str, success: bool, 
                             context: AgentContext, result: Dict[str, Any]):
        """Store episodic memory of the interaction"""
        importance = 0.7 if success else 0.9  # Errors are more important to remember
        user_id = context.shared_data.get("user_id", "anonymous")
        
        self.memory_system.store_memory(
            agent_id=self.agent_id,
            memory_type="episodic",
            content={
                "task_type": task_type,
                "success": success,
                "context": context.shared_data,
                "result": result,
                "timestamp": datetime.now().isoformat()
            },
            importance=importance,
            tags=[task_type, "success" if success else "error", user_id]  # Added user_id for retrieval
        )
    
    def _extract_and_learn_preferences(self, user_id: str, context: AgentContext, result: Dict[str, Any]):
        """Extract and learn user preferences from successful interactions"""
        # Extract preferences from context and result
        preferences = {}
        
        # Budget preferences
        if "budget" in context.shared_data:
            preferences["budget_preference"] = context.shared_data["budget"]
        
        # Travel style preferences
        if "travel_style" in context.shared_data:
            preferences["travel_style"] = context.shared_data["travel_style"]
        
        # Activity preferences from result
        if "activities" in result:
            preferences["activity_preference"] = result["activities"]
        
        # Store learned preferences in memory system
        for pref_type, pref_value in preferences.items():
            self.memory_system.learn_user_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence=0.6
            )
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get learned preferences for a user"""
        return self.memory_system.get_user_preferences(user_id)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this agent"""
        metrics = self.memory_system.get_learning_metrics(self.agent_id)
        return {
            task_type: metric for (agent_id, task_type), metric in metrics.items()
        }
    
    def apply_learned_preferences(self, context: AgentContext) -> AgentContext:
        """Apply learned user preferences to context"""
        user_id = context.shared_data.get("user_id")
        if not user_id:
            return context
        
        preferences = self.get_user_preferences(user_id)
        
        # Merge preferences into context for enhanced processing
        enhanced_context = AgentContext(
            session_id=context.session_id,
            user_request=context.user_request,
            conversation_history=context.conversation_history,
            shared_data={**context.shared_data, "learned_preferences": preferences},
            goals=context.goals,
            constraints=context.constraints
        )
        
        return enhanced_context
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights about learning progress"""
        metrics = self.get_performance_metrics()
        
        if not metrics:
            return {"message": "No learning data available"}
        
        total_tasks = sum(m.total_tasks for m in metrics.values())
        successful_tasks = sum(m.successful_tasks for m in metrics.values())
        
        return {
            "total_tasks": total_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "task_types": len(metrics),
            "learning_status": "active" if total_tasks > 0 else "initializing"
        }
