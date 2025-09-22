"""
Base Agent Framework for TripPlanner Multi-Agent System

This module provides the foundational framework for all agents in the TripPlanner
multi-agent system. It defines the base classes, communication protocols, and
core functionality that all specialized agents inherit from.

The module includes:
- BaseAgent: Abstract base class defining the agent interface and common functionality
- AgentMessage: Message structure for inter-agent communication
- AgentContext: Shared context and data structure for agent coordination
- AgentCommunication: Centralized communication hub for message routing

This framework enables consistent agent behavior, standardized communication,
and provides the foundation for building specialized agents with specific capabilities.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class AgentMessage:
    """Message structure for agent communication"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipient: str = ""
    message_type: str = ""  # "request", "response", "notification", "query"
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=low, 2=medium, 3=high, 4=urgent

@dataclass
class AgentContext:
    """Shared context between agents"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_request: str = ""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)

class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.status = "idle"  # idle, working, waiting, error
        self.memory = {}  # Simple memory for now
        self.capabilities = []
        self.dependencies = []  # Other agents this agent depends on
        
    def send_message(self, recipient: str, message_type: str, content: Dict[str, Any], priority: int = 1) -> AgentMessage:
        """Send a message to another agent"""
        message = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            message_type=message_type,
            content=content,
            priority=priority
        )
        return message
    
    def receive_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Receive and process a message from another agent"""
        self.memory[f"message_{message.id}"] = {
            "timestamp": message.timestamp,
            "sender": message.sender,
            "type": message.message_type,
            "content": message.content
        }
        return self.process_message(message)
    
    @abstractmethod
    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming messages - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def execute_task(self, context: AgentContext) -> Dict[str, Any]:
        """Execute the agent's main task - must be implemented by subclasses"""
        pass
    
    def update_status(self, status: str):
        """Update agent status"""
        self.status = status
    
    def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """Log agent activity"""
        log_entry = {
            "timestamp": datetime.now(),
            "agent": self.agent_id,
            "activity": activity,
            "details": details or {}
        }
        self.memory[f"activity_{len(self.memory)}"] = log_entry

class AgentCommunication:
    """Centralized communication hub for agents"""
    
    def __init__(self):
        self.agents = {}
        self.message_queue = []
        self.message_history = []
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the communication hub"""
        self.agents[agent.agent_id] = agent
    
    def send_message(self, message: AgentMessage):
        """Send a message between agents"""
        if message.recipient in self.agents:
            response = self.agents[message.recipient].receive_message(message)
            self.message_history.append(message)
            if response:
                self.message_history.append(response)
            return response
        else:
            return None
    
    def broadcast_message(self, sender: str, message_type: str, content: Dict[str, Any], exclude: List[str] = None):
        """Broadcast a message to all agents except sender"""
        exclude = exclude or [sender]
        for agent_id in self.agents:
            if agent_id not in exclude:
                message = AgentMessage(
                    sender=sender,
                    recipient=agent_id,
                    message_type=message_type,
                    content=content
                )
                self.send_message(message)