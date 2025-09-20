# LangGraph State for Multi-Agent System
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class AgentMessage:
    """Enhanced message structure for agent communication"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipient: str = ""
    message_type: str = ""  # "request", "response", "notification", "query", "error"
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=low, 2=medium, 3=high, 4=urgent
    requires_response: bool = False
    response_timeout: Optional[datetime] = None

@dataclass
class AgentStatus:
    """Agent status tracking"""
    agent_id: str
    status: str = "idle"  # idle, working, waiting, error, completed
    current_task: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    error_message: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.now)

@dataclass
class AgentMemory:
    """Agent memory and context"""
    agent_id: str
    session_data: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    learned_preferences: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

class AgentState(TypedDict):
    """LangGraph state for multi-agent coordination"""
    # Core session data
    session_id: str
    user_request: str
    conversation_history: List[Dict[str, Any]]
    
    # Agent coordination
    agent_statuses: Dict[str, AgentStatus]
    agent_memories: Dict[str, AgentMemory]
    message_queue: List[AgentMessage]
    message_history: List[AgentMessage]
    
    # Shared data between agents
    planning_data: Dict[str, Any]
    research_data: Dict[str, Any]
    budget_data: Dict[str, Any]
    final_response: Optional[str]
    
    # Coordination control
    current_agent: str
    next_agent: Optional[str]
    coordination_strategy: str  # "sequential", "parallel", "collaborative"
    error_handling_mode: str  # "retry", "skip", "escalate"
    
    # Performance tracking
    start_time: datetime
    processing_steps: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]