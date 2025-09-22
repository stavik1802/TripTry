"""
Learning Agent for TripPlanner Multi-Agent System

This agent specializes in learning, adaptation, and system improvement. It analyzes
performance data, learns user preferences, and provides recommendations to optimize
the multi-agent system's effectiveness over time.

Key responsibilities:
- Analyze agent performance metrics and success rates
- Learn user preferences from feedback and interactions
- Generate improvement recommendations for other agents
- Track system-wide performance and identify optimization opportunities
- Implement reinforcement learning and pattern recognition

The agent uses multiple learning strategies including reinforcement learning,
pattern recognition, preference learning, and strategy optimization to continuously
improve the system's performance and user experience.
"""

from typing import Any, Dict, List, Optional
from .memory_enhanced_base_agent import MemoryEnhancedBaseAgent
from .base_agent import AgentMessage, AgentContext
from app.agents.utils.memory_system import MemorySystem, LearningMetrics, UserPreference
from datetime import datetime
import json

class LearningAgent(MemoryEnhancedBaseAgent):
    """Agent specialized in learning and adaptation"""
    
    def __init__(self):
        super().__init__("learning_agent", "learner")
        self.capabilities = ["analyze_performance", "learn_preferences", "adapt_strategies", "recommend_improvements"]
        self.dependencies = []
        # self.memory_system = MemorySystem()
        self.learning_strategies = {
            "reinforcement": self._reinforcement_learning,
            "pattern_recognition": self._pattern_recognition,
            "preference_learning": self._preference_learning,
            "strategy_optimization": self._strategy_optimization
        }
    
    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process learning-related messages"""
        if message.message_type == "performance_data":
            return self.handle_performance_data(message)
        elif message.message_type == "user_feedback":
            return self.handle_user_feedback(message)
        elif message.message_type == "learning_request":
            return self.handle_learning_request(message)
        elif message.message_type == "preference_update":
            return self.handle_preference_update(message)
        return None
    
    def handle_performance_data(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle performance data from other agents"""
        content = message.content
        agent_id = content.get("agent_id")
        task_type = content.get("task_type")
        success = content.get("success", False)
        response_time = content.get("response_time", 0.0)
        context = content.get("context", {})
        
        # Learn from performance data
        self.memory_system.learn_from_interaction(
            agent_id=agent_id,
            task_type=task_type,
            success=success,
            response_time=response_time,
            context=context
        )
        
        # Analyze and provide recommendations
        recommendations = self.analyze_performance(agent_id, task_type)
        
        return self.send_message(
            recipient=agent_id,
            message_type="learning_recommendations",
            content={
                "recommendations": recommendations,
                "performance_insights": self.get_performance_insights(agent_id)
            },
            priority=2
        )
    
    def handle_user_feedback(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle user feedback for learning"""
        content = message.content
        user_id = content.get("user_id", "anonymous")
        feedback_type = content.get("feedback_type")
        feedback_data = content.get("feedback_data", {})
        
        # Extract preferences from user feedback
        preferences = self.extract_preferences_from_feedback(feedback_data)
        
        for pref_type, pref_value in preferences.items():
            self.memory_system.learn_user_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence=0.8,
                session_id=content.get("session_id")
            )
        
        return self.send_message(
            recipient="planning_agent",
            message_type="preference_update",
            content={
                "user_id": user_id,
                "preferences": preferences
            },
            priority=2
        )
    
    def handle_learning_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle requests for learning insights"""
        content = message.content
        request_type = content.get("request_type")
        agent_id = content.get("agent_id")
        
        if request_type == "performance_analysis":
            insights = self.get_performance_insights(agent_id)
            recommendations = self.generate_recommendations(agent_id)
            
            return self.send_message(
                recipient=agent_id,
                message_type="learning_insights",
                content={
                    "insights": insights,
                    "recommendations": recommendations
                },
                priority=2
            )
        
        return None
    
    def handle_preference_update(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle preference updates"""
        content = message.content
        user_id = content.get("user_id")
        preferences = content.get("preferences", {})
        
        for pref_type, pref_data in preferences.items():
            self.memory_system.learn_user_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_data.get("value"),
                confidence=pref_data.get("confidence", 0.5)
            )
        
        return None
    
    def analyze_performance(self, agent_id: str, task_type: str) -> List[Dict[str, Any]]:
        """Analyze agent performance and provide recommendations"""
        metrics = self.memory_system.get_learning_metrics(agent_id)
        recommendations = []
        
        if (agent_id, task_type) in metrics:
            metric = metrics[(agent_id, task_type)]
            
            if metric.success_rate < 0.7:
                recommendations.append({
                    "type": "improve_success_rate",
                    "priority": "high",
                    "suggestion": "Review error patterns and improve task execution logic",
                    "metric": f"Success rate: {metric.success_rate:.2%}"
                })
            
            if metric.average_response_time > 30.0:  # 30 seconds threshold
                recommendations.append({
                    "type": "improve_response_time",
                    "priority": "medium",
                    "suggestion": "Optimize task execution or implement caching",
                    "metric": f"Average response time: {metric.average_response_time:.1f}s"
                })
            
            if metric.error_rate > 0.3:
                recommendations.append({
                    "type": "reduce_errors",
                    "priority": "high",
                    "suggestion": "Add more error handling and validation",
                    "metric": f"Error rate: {metric.error_rate:.2%}"
                })
        
        return recommendations
    
    def get_performance_insights(self, agent_id: str) -> Dict[str, Any]:
        """Get comprehensive performance insights"""
        metrics = self.memory_system.get_learning_metrics(agent_id)
        
        if not metrics:
            return {"message": "No performance data available"}
        
        insights = {
            "total_task_types": len(metrics),
            "overall_success_rate": sum(m.success_rate for m in metrics.values()) / len(metrics),
            "average_response_time": sum(m.average_response_time for m in metrics.values()) / len(metrics),
            "task_breakdown": {}
        }
        
        for (aid, task_type), metric in metrics.items():
            insights["task_breakdown"][task_type] = {
                "success_rate": metric.success_rate,
                "average_response_time": metric.average_response_time,
                "total_tasks": metric.total_tasks,
                "error_rate": metric.error_rate
            }
        
        return insights
    
    def generate_recommendations(self, agent_id: str) -> List[Dict[str, Any]]:
        """Generate improvement recommendations"""
        recommendations = []
        metrics = self.memory_system.get_learning_metrics(agent_id)
        
        for (aid, task_type), metric in metrics.items():
            if metric.success_rate < 0.8:
                recommendations.append({
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "recommendation": "Improve success rate",
                    "priority": "high",
                    "details": f"Current success rate: {metric.success_rate:.2%}"
                })
        
        return recommendations
    
    def extract_preferences_from_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user preferences from feedback"""
        preferences = {}
        
        # Analyze feedback for preference indicators
        if "budget" in feedback_data:
            preferences["budget_preference"] = feedback_data["budget"]
        
        if "accommodation_type" in feedback_data:
            preferences["accommodation_preference"] = feedback_data["accommodation_type"]
        
        if "activity_preferences" in feedback_data:
            preferences["activity_preference"] = feedback_data["activity_preferences"]
        
        if "food_preferences" in feedback_data:
            preferences["food_preference"] = feedback_data["food_preferences"]
        
        return preferences
    
    def _reinforcement_learning(self, agent_id: str, task_type: str, 
                              reward: float, context: Dict[str, Any]):
        """Implement reinforcement learning"""
        # Store reward-based learning data
        self.memory_system.store_memory(
            agent_id=agent_id,
            memory_type="procedural",
            content={
                "task_type": task_type,
                "reward": reward,
                "context": context,
                "learning_type": "reinforcement"
            },
            importance=reward,  # Higher reward = higher importance
            tags=["reinforcement_learning", task_type]
        )
    
    def _pattern_recognition(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Recognize patterns in agent behavior"""
        # Simple pattern recognition (can be enhanced with ML)
        patterns = {}
        
        # Analyze success patterns
        successful_tasks = [d for d in data if d.get("success", False)]
        if successful_tasks:
            patterns["success_patterns"] = {
                "common_contexts": self._find_common_contexts(successful_tasks),
                "optimal_conditions": self._find_optimal_conditions(successful_tasks)
            }
        
        return patterns
    
    def _preference_learning(self, user_id: str, interactions: List[Dict[str, Any]]):
        """Learn user preferences from interactions"""
        preferences = {}
        
        for interaction in interactions:
            # Extract preferences from interaction context
            context = interaction.get("context", {})
            
            if "budget" in context:
                preferences["budget_preference"] = context["budget"]
            
            if "travel_style" in context:
                preferences["travel_style"] = context["travel_style"]
        
        # Store learned preferences
        for pref_type, pref_value in preferences.items():
            self.memory_system.learn_user_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence=0.6
            )
    
    def _strategy_optimization(self, agent_id: str) -> Dict[str, Any]:
        """Optimize agent strategies based on performance"""
        metrics = self.memory_system.get_learning_metrics(agent_id)
        
        optimizations = {}
        for (aid, task_type), metric in metrics.items():
            if metric.success_rate < 0.7:
                optimizations[task_type] = {
                    "current_strategy": "default",
                    "recommended_strategy": "enhanced_error_handling",
                    "expected_improvement": 0.2
                }
        
        return optimizations
    
    def _find_common_contexts(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find common contexts in successful tasks"""
        contexts = {}
        for task in tasks:
            context = task.get("context", {})
            for key, value in context.items():
                if key not in contexts:
                    contexts[key] = []
                contexts[key].append(value)
        
        # Find most common values
        common = {}
        for key, values in contexts.items():
            if len(set(values)) < len(values):  # Has duplicates
                common[key] = max(set(values), key=values.count)
        
        return common
    
    def _find_optimal_conditions(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find optimal conditions for task success"""
        # Analyze conditions that lead to success
        conditions = {}
        
        for task in tasks:
            context = task.get("context", {})
            response_time = task.get("response_time", 0)
            
            # Track conditions with fast response times
            if response_time < 10:  # Fast response threshold
                for key, value in context.items():
                    if key not in conditions:
                        conditions[key] = {"fast": [], "slow": []}
                    conditions[key]["fast"].append(value)
        
        return conditions
    
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute learning task"""
        self.update_status("working")
        
        # Analyze system performance metrics
        all_metrics = self.memory_system.get_learning_metrics()
        system_analysis = {
            "total_agents": len(set(k[0] for k in all_metrics.keys())),
            "total_task_types": len(all_metrics),
            "overall_performance": self._calculate_overall_performance(all_metrics)
        }
        
        # Consolidate and optimize memories
        self.memory_system.consolidate_memories()
        
        return {
            "status": "success",
            "system_analysis": system_analysis,
            "learning_insights": self._generate_learning_insights(),
            "agent_id": self.agent_id
        }
    
    def _calculate_overall_performance(self, metrics: Dict) -> Dict[str, float]:
        """Calculate overall system performance"""
        if not metrics:
            return {"success_rate": 0.0, "avg_response_time": 0.0, "error_rate": 0.0}
        
        success_rates = [m.success_rate for m in metrics.values()]
        response_times = [m.average_response_time for m in metrics.values()]
        
        return {
            "success_rate": sum(success_rates) / len(success_rates),
            "avg_response_time": sum(response_times) / len(response_times),
            "error_rate": 1.0 - (sum(success_rates) / len(success_rates))
        }
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get learning insights for the system"""
        return self._generate_learning_insights()
    
    def _generate_learning_insights(self) -> Dict[str, Any]:
        """Generate insights about learning progress"""
        return {
            "memory_consolidation": "completed",
            "preference_learning": "active",
            "performance_tracking": "active",
            "recommendation_engine": "operational"
        }