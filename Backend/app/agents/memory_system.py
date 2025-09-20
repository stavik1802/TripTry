# Advanced Memory & Learning System for Multi-Agent System
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

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("Warning: pymongo not available. Install with: pip install pymongo")

@dataclass
class MemoryEntry:
    """Individual memory entry"""
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
    """Learning performance metrics"""
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
    """User preference learning"""
    user_id: str
    preference_type: str  # "budget", "accommodation", "activities", "food"
    preference_value: Any
    confidence: float = 0.5
    learned_from: List[str] = field(default_factory=list)  # Session IDs
    last_reinforced: datetime = field(default_factory=datetime.now)

class MemorySystem:
    """Advanced memory system with multiple memory types using MongoDB"""
    
    def __init__(self, mongo_uri: str = "mongodb+srv://stavos114_db_user:dgtOtRZs3MimkTcK@cluster0.bzqyrad.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", db_name: str = "agent_memory"):
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
        """Setup MongoDB database for persistent memory"""
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
            print(f"[Memory System] Connected to MongoDB: {self.mongo_uri}/{self.db_name}")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"Warning: Could not connect to MongoDB: {e}")
            print("Using in-memory storage only.")
            self.client = None
            self.db = None
    
    def _ensure_indexes(self):
        """Ensure proper indexes exist for efficient queries"""
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
        """Store a memory entry"""
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
        """Retrieve memories based on criteria"""
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
        """Learn from agent interactions"""
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
        """Learn user preferences from interactions"""
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
        """Get learned user preferences"""
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
        """Get learning metrics for agents"""
        if agent_id:
            return {k: v for k, v in self.learning_metrics.items() if k[0] == agent_id}
        return self.learning_metrics
    
    def consolidate_memories(self, agent_id: str = None):
        """Consolidate and optimize memories"""
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
        
        print(f"[Memory System] Consolidated memories for {agent_id or 'all agents'}")
    
    def _generate_memory_id(self, agent_id: str, content: Dict[str, Any]) -> str:
        """Generate unique memory ID"""
        content_str = json.dumps(content, sort_keys=True)
        hash_input = f"{agent_id}_{content_str}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def _persist_memory(self, memory: MemoryEntry):
        """Persist memory to MongoDB"""
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
        """Persist learning metrics to MongoDB"""
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
        """Persist user preference to MongoDB"""
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
        """Load memories from MongoDB into in-memory cache"""
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
            
            total = (
                len(self.episodic_memory)
                + len(self.semantic_memory)
                + len(self.procedural_memory)
                + len(self.working_memory)
            )
            print(f"[Memory System] Loaded {total} memories from MongoDB")
            
        except Exception as e:
            print(f"Warning: Could not load from MongoDB: {e}")
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("[Memory System] MongoDB connection closed")
