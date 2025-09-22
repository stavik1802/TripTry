"""
MongoDB Storage for TripPlanner Multi-Agent System

This module provides MongoDB-based storage for the TripPlanner system, handling
persistent storage of trip planning runs, session data, and system state.
It includes connection management, indexing, and data persistence operations.

Key features:
- MongoDB connection and database management
- Trip planning run storage and retrieval
- Session data persistence
- Automatic indexing for performance optimization
- Error handling and connection validation

The storage system enables persistent data management across sessions,
allowing the system to maintain state and provide continuity between requests.
"""

from __future__ import annotations
import os, time
from typing import Any, Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from dotenv import load_dotenv

load_dotenv()

class MongoStore:
    def __init__(self):
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise ValueError("MONGODB_URI environment variable is required")
        db_name = os.environ.get("MONGODB_DB", "agent_memory")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        self.client.admin.command("ping")
        self.db = self.client[db_name]
        self.runs: Collection = self.db[os.environ.get("RUNS_COLLECTION", "runs")]
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.runs.create_index([("created_at", DESCENDING)])
        self.runs.create_index([("session_id", ASCENDING)])
        self.runs.create_index([("status", ASCENDING)])
        self.runs.create_index([("intent", ASCENDING)])
        self.runs.create_index([("context.cities", ASCENDING)])

    def start_run(self, *, session_id: str, user_query: str, intent: str, context: Dict[str, Any]) -> Any:
        doc = {
            "session_id": session_id,
            "user_query": user_query,
            "intent": intent,
            "context": context,
            "agents": {},
            "logs": [],
            "status": "running",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "timing": {"t0": time.time()},
        }
        return self.runs.insert_one(doc).inserted_id

    def log_agent_output(self, run_id: Any, agent_name: str, payload: Dict[str, Any], *, step: Optional[str] = None):
        update = {"$set": {f"agents.{agent_name}": payload, "updated_at": datetime.utcnow()}}
        if step:
            update["$push"] = {"logs": {"ts": datetime.utcnow(), "step": step}}
        self.runs.update_one({"_id": run_id}, update)

    def append_log(self, run_id: Any, message: str):
        self.runs.update_one(
            {"_id": run_id},
            {"$push": {"logs": {"ts": datetime.utcnow(), "msg": message}},
             "$set": {"updated_at": datetime.utcnow()}}
        )

    def finish_run(self, run_id: Any, *, final: Dict[str, Any], status: str = "success", error: Optional[str] = None):
        set_fields = {"final": final, "status": status, "updated_at": datetime.utcnow()}
        if error:
            set_fields["error"] = str(error)
        self.runs.update_one({"_id": run_id}, {"$set": set_fields, "$currentDate": {"finished_at": True}})

    # optional for a quick demo page
    def latest(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self.runs.find({}, {"logs": {"$slice": -6}}).sort("created_at", DESCENDING).limit(limit)
        return list(cur)
