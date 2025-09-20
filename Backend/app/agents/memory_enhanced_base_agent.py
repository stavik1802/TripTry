# Memory-Enhanced Base Agent with Learning Capabilities
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent, AgentMessage, AgentContext
from .memory_system import MemorySystem
from datetime import datetime
import time

class MemoryEnhancedBaseAgent(BaseAgent):
    """Base agent with integrated memory and learning capabilities"""
    
    def __init__(self, agent_id: str, agent_type: str):
        super().__init__(agent_id, agent_type)
        self.memory_system = MemorySystem()
        self.performance_tracker = {}
        self.user_contexts = {}
        self.learning_enabled = True
    
    def execute_task_with_learning(self, context: AgentContext, task_type: str = "general") -> Dict[str, Any]:
        """Execute task with integrated learning"""
        start_time = time.time()
        
        try:
            # Retrieve relevant memories
            relevant_memories = self._retrieve_relevant_memories(context, task_type)
            
            # Execute task
            result = self.execute_task(context)
            
            # Calculate performance metrics
            response_time = time.time() - start_time
            success = result.get("status") == "success"
            
            # Learn from interaction
            if self.learning_enabled:
                self._learn_from_interaction(task_type, success, response_time, context, result)
            
            # Store episodic memory
            self._store_episodic_memory(task_type, success, context, result)
            
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
        
        return user_memories + procedural_memories
    
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
        # Store error memory
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
            tags=["error", task_type, "learning"]
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
            tags=[task_type, "success" if success else "error"]
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
        
        # Store learned preferences
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
        
        # Merge preferences into context
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
