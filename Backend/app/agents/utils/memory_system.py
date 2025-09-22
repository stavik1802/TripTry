"""
Advanced Memory & Learning System for Multi-Agent TripPlanner

This module implements a sophisticated memory system that provides persistent storage,
learning capabilities, and intelligent caching for the TripPlanner multi-agent system.
It supports multiple memory types, user preference learning, performance tracking,
and conversation history management.

ARCHITECTURE OVERVIEW:
=====================
The memory system consists of four main components:

1. MEMORY TYPES - Multiple specialized memory stores:
   - Episodic Memory: Event-based memories and experiences
   - Semantic Memory: Fact-based knowledge and learned information
   - Procedural Memory: How-to knowledge and procedures
   - Working Memory: Temporary active memory for current tasks

2. LEARNING SYSTEM - Adaptive intelligence features:
   - Performance Metrics: Track agent success rates and response times
   - User Preferences: Learn from user interactions and preferences
   - Interaction Learning: Analyze and improve from each agent interaction

3. PERSISTENCE LAYER - MongoDB integration:
   - Automatic persistence of all memory types
   - Efficient indexing for fast retrieval
   - Connection management with fallback to in-memory storage

4. CACHING SYSTEM - Performance optimization:
   - Result caching with fingerprinting
   - Conversation history management
   - Intelligent cache invalidation

FEATURES:
=========
- **Multi-Type Memory**: Episodic, semantic, procedural, and working memory
- **Learning Analytics**: Track agent performance and improvement over time
- **User Preference Learning**: Learn and adapt to user preferences
- **Conversation Context**: Maintain conversation history for follow-up questions
- **Result Caching**: Cache successful results to improve response times
- **MongoDB Persistence**: Reliable storage with automatic backup and recovery
- **Memory Consolidation**: Automatic optimization and cleanup of memory stores
- **Tagged Retrieval**: Fast memory retrieval using tags and associations

MEMORY TYPES:
============
- **Episodic Memory**: Stores specific events, experiences, and interactions
- **Semantic Memory**: Stores facts, knowledge, and learned information
- **Procedural Memory**: Stores how-to knowledge and procedures
- **Working Memory**: Stores temporary information for current tasks

LEARNING CAPABILITIES:
=====================
- **Performance Tracking**: Monitor agent success rates, response times, and error rates
- **User Preference Learning**: Learn user preferences from interactions
- **Interaction Analysis**: Analyze patterns in user-agent interactions
- **Adaptive Improvement**: Use learned data to improve future responses

USAGE:
======
memory_system = MemorySystem()
memory_system.store_memory("agent_id", "episodic", {"event": "data"})
memories = memory_system.retrieve_memories(agent_id="agent_id")
memory_system.learn_from_interaction("agent_id", "task_type", True, 1.5, {})
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import pickle
from pathlib import Path
import hashlib
from datetime import datetime, timedelta
# import numpy as np  # Commented out for testing without numpy
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple
import copy  # <-- added for deep copy in cache helpers

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("Warning: pymongo not available. Install with: pip install pymongo")

@dataclass
class MemoryEntry:
    """Individual memory entry with metadata and access tracking."""
    id: str
    timestamp: datetime
    agent_id: str
    memory_type: str  # "episodic", "semantic", "procedural", "working"
    content: Dict[str, Any]
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    associations: List[str] = field(default_factory=list)

@dataclass
class LearningMetrics:
    """Learning performance metrics for tracking agent improvement."""
    agent_id: str
    task_type: str
    success_rate: float = 0.0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    improvement_trend: float = 0.0
    total_tasks: int = 0
    successful_tasks: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class UserPreference:
    """User preference learning with confidence tracking."""
    user_id: str
    preference_type: str  # "budget", "accommodation", "activities", "food"
    preference_value: Any
    confidence: float = 0.5
    learned_from: List[str] = field(default_factory=list)  # Session IDs
    last_reinforced: datetime = field(default_factory=datetime.now)

class MemorySystem:
    """Advanced memory system with multiple memory types using MongoDB."""
    
    def __init__(self, mongo_uri: str = "mongodb+srv://stavos114_db_user:dgtOtRZs3MimkTcK@cluster0.bzqyrad.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", db_name: str = "agent_memory"):
        """Initialize memory system with MongoDB connection and in-memory caches."""
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.episodic_memory = {}  # Event-based memories (in-memory cache)
        self.semantic_memory = {}  # Fact-based knowledge (in-memory cache)
        self.procedural_memory = {}  # How-to knowledge (in-memory cache)
        self.working_memory = {}  # Temporary active memory (in-memory cache)
        self.user_preferences = {}
        self.learning_metrics = {}
        self.memory_index = defaultdict(list)  # For fast retrieval
        self.client = None
        self.db = None
        self.setup_database()
    
    def setup_database(self):
        """Setup MongoDB database connection and indexes."""
        if not MONGODB_AVAILABLE:
            print("Warning: MongoDB not available. Using in-memory storage only.")
            return
        
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.server_info()
            self.db = self.client[self.db_name]
            
            # Create collections and indexes
            self._ensure_indexes()
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.client = None
            self.db = None
    
    def _ensure_indexes(self):
        """Create MongoDB indexes for efficient memory queries."""
        if self.db is None:
            return
        
        try:
            # Indexes for memories collection
            self.db.memories.create_index("agent_id")
            self.db.memories.create_index("memory_type")
            self.db.memories.create_index("tags")
            self.db.memories.create_index("timestamp")
            self.db.memories.create_index("importance")
            
            # Indexes for learning_metrics collection
            self.db.learning_metrics.create_index([("agent_id", 1), ("task_type", 1)], unique=True)
            self.db.learning_metrics.create_index("agent_id")
            
            # Indexes for user_preferences collection
            self.db.user_preferences.create_index([("user_id", 1), ("preference_type", 1)], unique=True)
            self.db.user_preferences.create_index("user_id")
            
        except Exception as e:
            print(f"Warning: Could not create indexes: {e}")
    
    def store_memory(self, agent_id: str, memory_type: str, content: Dict[str, Any], 
                    importance: float = 0.5, tags: List[str] = None) -> str:
        """Store a memory entry in the appropriate memory type."""
        memory_id = self._generate_memory_id(agent_id, content)
        
        memory = MemoryEntry(
            id=memory_id,
            timestamp=datetime.now(),
            agent_id=agent_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            tags=tags or []
        )
        
        # Store in appropriate memory type
        if memory_type == "episodic":
            self.episodic_memory[memory_id] = memory
        elif memory_type == "semantic":
            self.semantic_memory[memory_id] = memory
        elif memory_type == "procedural":
            self.procedural_memory[memory_id] = memory
        elif memory_type == "working":
            self.working_memory[memory_id] = memory
        
        # Index for retrieval
        for tag in memory.tags:
            self.memory_index[tag].append(memory_id)
        
        # Persist to database
        self._persist_memory(memory)
        
        return memory_id
    
    def retrieve_memories(self, agent_id: str = None, memory_type: str = None, 
                         tags: List[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve memories based on agent, type, tags, and other criteria."""
        all_memories = {}
        all_memories.update(self.episodic_memory)
        all_memories.update(self.semantic_memory)
        all_memories.update(self.procedural_memory)
        all_memories.update(self.working_memory)
        
        filtered_memories = []
        
        for memory in all_memories.values():
            # Filter by agent
            if agent_id and memory.agent_id != agent_id:
                continue
            
            # Filter by type
            if memory_type and memory.memory_type != memory_type:
                continue
            
            # Filter by tags
            if tags and not any(tag in memory.tags for tag in tags):
                continue
            
            filtered_memories.append(memory)
        
        # Sort by importance and recency
        filtered_memories.sort(key=lambda m: (m.importance, m.timestamp), reverse=True)
        
        # Update access count
        for memory in filtered_memories[:limit]:
            memory.access_count += 1
            memory.last_accessed = datetime.now()
        
        return filtered_memories[:limit]
    
    def learn_from_interaction(self, agent_id: str, task_type: str, 
                             success: bool, response_time: float, context: Dict[str, Any]):
        """Learn from agent interactions and update performance metrics."""
        # Update learning metrics
        if (agent_id, task_type) not in self.learning_metrics:
            self.learning_metrics[(agent_id, task_type)] = LearningMetrics(
                agent_id=agent_id,
                task_type=task_type
            )
        
        metrics = self.learning_metrics[(agent_id, task_type)]
        metrics.total_tasks += 1
        
        if success:
            metrics.successful_tasks += 1
        
        # Update rates
        metrics.success_rate = metrics.successful_tasks / metrics.total_tasks
        metrics.average_response_time = (
            (metrics.average_response_time * (metrics.total_tasks - 1) + response_time) 
            / metrics.total_tasks
        )
        metrics.error_rate = 1.0 - metrics.success_rate
        metrics.last_updated = datetime.now()
        
        # Store episodic memory
        self.store_memory(
            agent_id=agent_id,
            memory_type="episodic",
            content={
                "task_type": task_type,
                "success": success,
                "response_time": response_time,
                "context": context,
                "metrics": {
                    "success_rate": metrics.success_rate,
                    "average_response_time": metrics.average_response_time
                }
            },
            importance=0.7,
            tags=[task_type, "learning", "performance"]
        )
        
        # Persist metrics
        self._persist_learning_metrics(metrics)
    
    def learn_user_preference(self, user_id: str, preference_type: str, 
                            preference_value: Any, confidence: float = 0.5, 
                            session_id: str = None):
        """Learn and update user preferences from interactions."""
        key = (user_id, preference_type)
        
        if key not in self.user_preferences:
            self.user_preferences[key] = UserPreference(
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value,
                confidence=confidence
            )
        
        preference = self.user_preferences[key]
        
        # Reinforce existing preference or update
        if preference.preference_value == preference_value:
            # Reinforce existing preference
            preference.confidence = min(1.0, preference.confidence + 0.1)
        else:
            # Update preference with new evidence
            preference.preference_value = preference_value
            preference.confidence = confidence
        
        if session_id:
            preference.learned_from.append(session_id)
        
        preference.last_reinforced = datetime.now()
        
        # Store semantic memory
        self.store_memory(
            agent_id="system",
            memory_type="semantic",
            content={
                "user_id": user_id,
                "preference_type": preference_type,
                "preference_value": preference_value,
                "confidence": preference.confidence
            },
            importance=0.8,
            tags=["user_preference", preference_type, user_id]
        )
        
        # Persist preference
        self._persist_user_preference(preference)
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get all learned user preferences for a specific user."""
        preferences = {}
        for key, preference in self.user_preferences.items():
            if key[0] == user_id:
                preferences[preference.preference_type] = {
                    "value": preference.preference_value,
                    "confidence": preference.confidence,
                    "last_reinforced": preference.last_reinforced
                }
        return preferences
    
    def get_learning_metrics(self, agent_id: str = None) -> Dict[str, LearningMetrics]:
        """Get learning metrics for specific agent or all agents."""
        if agent_id:
            return {k: v for k, v in self.learning_metrics.items() if k[0] == agent_id}
        return self.learning_metrics
    
    def consolidate_memories(self, agent_id: str = None):
        """Consolidate and optimize memories by removing old working memories."""
        # Remove old working memories
        cutoff_time = datetime.now() - timedelta(hours=24)
        old_working = [
            mid for mid, memory in self.working_memory.items()
            if memory.timestamp < cutoff_time
        ]
        for mid in old_working:
            del self.working_memory[mid]
        
        # Promote important working memories to episodic
        important_working = [
            memory for memory in self.working_memory.values()
            if memory.importance > 0.8 and memory.access_count > 5
        ]
        
        for memory in important_working:
            # Move to episodic memory
            memory.memory_type = "episodic"
            self.episodic_memory[memory.id] = memory
            del self.working_memory[memory.id]
        
    
    def _generate_memory_id(self, agent_id: str, content: Dict[str, Any]) -> str:
        """Generate unique memory ID using content hash."""
        content_str = json.dumps(content, sort_keys=True)
        hash_input = f"{agent_id}_{content_str}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def _persist_memory(self, memory: MemoryEntry):
        """Persist memory entry to MongoDB database."""
        if self.db is None:
            return
        
        try:
            memory_doc = {
                "_id": memory.id,
                "timestamp": memory.timestamp,
                "agent_id": memory.agent_id,
                "memory_type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
                "access_count": memory.access_count,
                "last_accessed": memory.last_accessed,
                "tags": memory.tags,
                "associations": memory.associations
            }
            
            self.db.memories.replace_one(
                {"_id": memory.id},
                memory_doc,
                upsert=True
            )
        except Exception as e:
            print(f"Warning: Could not persist memory to MongoDB: {e}")
    
    def _persist_learning_metrics(self, metrics: LearningMetrics):
        """Persist learning metrics to MongoDB database."""
        if self.db is None:
            return
        
        try:
            metrics_doc = {
                "agent_id": metrics.agent_id,
                "task_type": metrics.task_type,
                "success_rate": metrics.success_rate,
                "average_response_time": metrics.average_response_time,
                "error_rate": metrics.error_rate,
                "improvement_trend": metrics.improvement_trend,
                "total_tasks": metrics.total_tasks,
                "successful_tasks": metrics.successful_tasks,
                "last_updated": metrics.last_updated
            }
            
            self.db.learning_metrics.replace_one(
                {"agent_id": metrics.agent_id, "task_type": metrics.task_type},
                metrics_doc,
                upsert=True
            )
        except Exception as e:
            print(f"Warning: Could not persist learning metrics to MongoDB: {e}")
    
    def _persist_user_preference(self, preference: UserPreference):
        """Persist user preference to MongoDB database."""
        if self.db is None:
            return
        
        try:
            preference_doc = {
                "user_id": preference.user_id,
                "preference_type": preference.preference_type,
                "preference_value": preference.preference_value,
                "confidence": preference.confidence,
                "learned_from": preference.learned_from,
                "last_reinforced": preference.last_reinforced
            }
            
            self.db.user_preferences.replace_one(
                {"user_id": preference.user_id, "preference_type": preference.preference_type},
                preference_doc,
                upsert=True
            )
        except Exception as e:
            print(f"Warning: Could not persist user preference to MongoDB: {e}")
    
    def load_from_database(self):
        """Load all memories from MongoDB into in-memory cache."""
        if self.db is None:
            return
        
        try:
            # Load memories
            for memory_doc in self.db.memories.find():
                memory = MemoryEntry(
                    id=memory_doc["_id"],
                    timestamp=memory_doc["timestamp"],
                    agent_id=memory_doc["agent_id"],
                    memory_type=memory_doc["memory_type"],
                    content=memory_doc["content"],
                    importance=memory_doc["importance"],
                    access_count=memory_doc["access_count"],
                    last_accessed=memory_doc["last_accessed"],
                    tags=memory_doc["tags"],
                    associations=memory_doc["associations"]
                )
                
                # Store in appropriate memory type
                if memory.memory_type == "episodic":
                    self.episodic_memory[memory.id] = memory
                elif memory.memory_type == "semantic":
                    self.semantic_memory[memory.id] = memory
                elif memory.memory_type == "procedural":
                    self.procedural_memory[memory.id] = memory
                elif memory.memory_type == "working":
                    self.working_memory[memory.id] = memory
                
                # Rebuild index
                for tag in memory.tags:
                    self.memory_index[tag].append(memory.id)
            
            # Load learning metrics
            for metrics_doc in self.db.learning_metrics.find():
                metrics = LearningMetrics(
                    agent_id=metrics_doc["agent_id"],
                    task_type=metrics_doc["task_type"],
                    success_rate=metrics_doc["success_rate"],
                    average_response_time=metrics_doc["average_response_time"],
                    error_rate=metrics_doc["error_rate"],
                    improvement_trend=metrics_doc["improvement_trend"],
                    total_tasks=metrics_doc["total_tasks"],
                    successful_tasks=metrics_doc["successful_tasks"],
                    last_updated=metrics_doc["last_updated"]
                )
                self.learning_metrics[(metrics.agent_id, metrics.task_type)] = metrics
            
            # Load user preferences
            for pref_doc in self.db.user_preferences.find():
                preference = UserPreference(
                    user_id=pref_doc["user_id"],
                    preference_type=pref_doc["preference_type"],
                    preference_value=pref_doc["preference_value"],
                    confidence=pref_doc["confidence"],
                    learned_from=pref_doc["learned_from"],
                    last_reinforced=pref_doc["last_reinforced"]
                )
                self.user_preferences[(preference.user_id, preference.preference_type)] = preference
            
            total_memories = len(self.episodic_memory) + len(self.semantic_memory) + len(self.procedural_memory) + len(self.working_memory)
            
        except Exception as e:
            print(f"Warning: Could not load from MongoDB: {e}")
    
    def close_connection(self):
        """Close MongoDB connection and cleanup resources."""
        if self.client:
            self.client.close()

    # ---------------------- NEW: small caching helpers ----------------------

    def make_fingerprint(self, user_id: str, task_type: str, user_request: str) -> str:
        """Generate stable fingerprint for caching user requests."""
        key = f"{(user_id or '').strip().lower()}|{(task_type or '').strip().lower()}|{(user_request or '').strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    def save_cached_result(self, *, agent_id: str, user_id: str, task_type: str, user_request: str, result: dict) -> str:
        """Store cached result in episodic memory for future retrieval."""
        fp = self.make_fingerprint(user_id, task_type, user_request)
        memory_id = self.store_memory(
            agent_id=agent_id,
            memory_type="episodic",
            content={
                "kind": "cache",
                "fingerprint": fp,
                "user_id": user_id,
                "task_type": task_type,
                "user_request": user_request,
                "result": copy.deepcopy(result),  # deep copy on write
            },
            importance=0.6,
            tags=["cache", user_id, task_type, fp]
        )
        return memory_id

    def load_cached_result(self, *, user_id: str, task_type: str, user_request: str, max_age_hours: int = 24) -> Optional[dict]:
        """Load cached result if present and fresh, otherwise return None."""
        fp = self.make_fingerprint(user_id, task_type, user_request)
        now = datetime.now()
        for mem in self.episodic_memory.values():
            if mem.memory_type != "episodic":
                continue
            if "cache" not in mem.tags:
                continue
            if fp not in mem.tags:
                continue
            age_hours = (now - mem.timestamp).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                continue
            data = mem.content or {}
            if data.get("kind") == "cache" and data.get("fingerprint") == fp and isinstance(data.get("result"), dict):
                return copy.deepcopy(data["result"])  # deep copy on read
        return None

    def store_conversation_turn(self, *, session_id: str, user_id: str, user_request: str, agent_response: dict, conversation_turn: int = 1) -> str:
        """Store conversation turn for maintaining context across interactions."""
        memory_id = self.store_memory(
            agent_id="system",
            memory_type="episodic",
            content={
                "kind": "conversation_turn",
                "session_id": session_id,
                "user_id": user_id,
                "user_request": user_request,
                "agent_response": copy.deepcopy(agent_response),
                "conversation_turn": conversation_turn,
                "timestamp": datetime.now().isoformat()
            },
            importance=0.8,
            tags=["conversation", session_id, user_id, f"turn_{conversation_turn}"]
        )
        return memory_id

    def get_conversation_history(self, *, session_id: str = None, user_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve conversation history for context in follow-up questions."""
        # Prefer querying persistent store to avoid cross-worker cache gaps
        if self.db is not None and session_id:
            try:
                cur = self.db.memories.find(
                    {
                        "tags": {"$in": ["conversation", session_id]},
                        "content.kind": "conversation_turn",
                        "content.session_id": session_id,
                    },
                    projection={
                        "_id": 0,
                        "content.user_request": 1,
                        "content.agent_response": 1,
                        "content.timestamp": 1,
                        "content.session_id": 1,
                        "content.conversation_turn": 1,
                    },
                ).sort([("content.conversation_turn", -1)]).limit(limit)
                out: List[Dict[str, Any]] = []
                for doc in cur:
                    c = doc.get("content", {})
                    out.append({
                        "turn": c.get("conversation_turn", 0),
                        "user_request": c.get("user_request", ""),
                        "agent_response": c.get("agent_response", {}),
                        "timestamp": c.get("timestamp", ""),
                        "session_id": c.get("session_id", ""),
                    })
                return out
            except Exception:
                # fall back to in-memory
                pass

        conversation_memories = []
        for mem in self.episodic_memory.values():
            if mem.memory_type != "episodic":
                continue
            if "conversation" not in mem.tags:
                continue
            data = mem.content or {}
            if data.get("kind") != "conversation_turn":
                continue
            if session_id and data.get("session_id") != session_id:
                continue
            if user_id and data.get("user_id") != user_id:
                continue
            conversation_memories.append({
                "turn": data.get("conversation_turn", 0),
                "user_request": data.get("user_request", ""),
                "agent_response": data.get("agent_response", {}),
                "timestamp": data.get("timestamp", ""),
                "session_id": data.get("session_id", "")
            })
        conversation_memories.sort(key=lambda x: x["turn"], reverse=True)
        return conversation_memories[:limit]

    def get_recent_conversations(self, *, user_id: str, hours_back: int = 24, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversations for user to provide context in new interactions."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        if self.db is not None:
            try:
                cur = self.db.memories.find(
                    {
                        "tags": {"$in": ["conversation", user_id]},
                        "content.kind": "conversation_turn",
                        "content.user_id": user_id,
                        "timestamp": {"$gte": cutoff_time},
                    },
                    projection={
                        "_id": 0,
                        "content.user_request": 1,
                        "content.agent_response": 1,
                        "content.timestamp": 1,
                        "content.session_id": 1,
                        "content.conversation_turn": 1,
                    },
                ).sort([("content.timestamp", -1)]).limit(limit)
                out: List[Dict[str, Any]] = []
                for doc in cur:
                    c = doc.get("content", {})
                    out.append({
                        "session_id": c.get("session_id", ""),
                        "user_request": c.get("user_request", ""),
                        "agent_response": c.get("agent_response", {}),
                        "timestamp": c.get("timestamp", ""),
                        "turn": c.get("conversation_turn", 0),
                    })
                return out
            except Exception:
                pass

        recent_conversations = []
        for mem in self.episodic_memory.values():
            if mem.memory_type != "episodic":
                continue
            if "conversation" not in mem.tags:
                continue
            if mem.timestamp < cutoff_time:
                continue
            data = mem.content or {}
            if data.get("kind") != "conversation_turn":
                continue
            if data.get("user_id") != user_id:
                continue
            recent_conversations.append({
                "session_id": data.get("session_id", ""),
                "user_request": data.get("user_request", ""),
                "agent_response": data.get("agent_response", {}),
                "timestamp": data.get("timestamp", ""),
                "turn": data.get("conversation_turn", 0)
            })
        recent_conversations.sort(key=lambda x: x["timestamp"], reverse=True)
        return recent_conversations[:limit]
