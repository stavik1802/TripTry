from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from app.config import settings

_client: Optional[MongoClient] = None
_runs: Optional[Collection] = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, appname="trip-planner")
    return _client

def get_runs_collection() -> Collection:
    global _runs
    if _runs is None:
        db = get_client()[settings.mongodb_db_name]
        _runs = db["runs"]
    return _runs

def init_indexes() -> None:
    runs = get_runs_collection()
    runs.create_index([("status", ASCENDING)])
    runs.create_index([("created_at", ASCENDING)])
    runs.create_index([("mode", ASCENDING)])

def create_run(doc: Dict[str, Any]) -> str:
    runs = get_runs_collection()
    runs.insert_one(doc)
    return doc["_id"]

def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    runs = get_runs_collection()
    return runs.find_one({"_id": run_id})

def update_run(run_id: str, fields: Dict[str, Any]) -> None:
    runs = get_runs_collection()
    fields["updated_at"] = datetime.now(timezone.utc)
    runs.update_one({"_id": run_id}, {"$set": fields})
