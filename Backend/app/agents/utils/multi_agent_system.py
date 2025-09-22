# Multi-Agent System Coordinator with memory and learning
#used before the agent coordinator was implemented
from typing import Any, Dict, List
from ..base_agent import BaseAgent, AgentContext, AgentCommunication
from ..planning_agent import PlanningAgent
from ..reasearch_agent import ResearchAgent
from ..budget_agent import BudgetAgent

class MultiAgentSystem:
    """Main coordinator for the multi-agent system"""
    
    def __init__(self):
        self.communication = AgentCommunication()
        self.agents = {}
        self.session_contexts = {}
        self.setup_agents()
    
    def setup_agents(self):
        """Initialize all agents"""
        # Create agents
        planning_agent = PlanningAgent()
        research_agent = ResearchAgent()
        budget_agent = BudgetAgent()
        
        # Register agents
        self.communication.register_agent(planning_agent)
        self.communication.register_agent(research_agent)
        self.communication.register_agent(budget_agent)
        
        # Store references
        self.agents = {
            "planning": planning_agent,
            "research": research_agent,
            "budget": budget_agent
        }
    
    def process_user_request(self, user_request: str) -> Dict[str, Any]:
        """Process a user request through the multi-agent system"""
        # Create session context
        context = AgentContext(user_request=user_request)
        session_id = context.session_id
        self.session_contexts[session_id] = context
        
        # Start with planning agent
        planning_result = self.agents["planning"].execute_task(context)
        
        # The planning agent will coordinate with other agents via messages
        # The communication system will handle the message flow
        
        return {
            "session_id": session_id,
            "planning_result": planning_result,
            "status": "processing"
        }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            agent_id: {
                "status": agent.status,
                "capabilities": agent.capabilities,
                "dependencies": agent.dependencies
            }
            for agent_id, agent in self.agents.items()
        }
    
    def get_message_history(self) -> List[Dict[str, Any]]:
        """Get communication history"""
        return [
            {
                "sender": msg.sender,
                "recipient": msg.recipient,
                "type": msg.message_type,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in self.communication.message_history
        ]