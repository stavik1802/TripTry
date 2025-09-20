import json, os, threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# env toggles
STORE_BACKEND = os.getenv("STORE_BACKEND", "mongo")  # "mongo" | "local"
LOCAL_PATH = os.getenv("LOCAL_STORE_PATH", os.path.join(os.path.expanduser("~"), ".trip_planner_runs.json"))

# -------------- Local JSON store (no-DB mode) ------------------------
_lock = threading.Lock()

def _local_load() -> Dict[str, Any]:
    if not os.path.exists(LOCAL_PATH):
        return {"runs": {}}
    try:
        with open(LOCAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"runs": {}}

def _local_save(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LOCAL_PATH), exist_ok=True)
    with open(LOCAL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

# -------------- Mongo (optional) -------------------------------------
_mongo_ready = False
try:
    from pymongo import MongoClient, ASCENDING
    from app.config import settings  # will error if .env missing (fine in local mode)

    def _mongo():
        client = MongoClient(settings.mongodb_uri, appname="trip-planner")
        db = client[settings.mongodb_db_name]
        col = db["runs"]
        col.create_index([("status", ASCENDING)])
        col.create_index([("created_at", ASCENDING)])
        return col

    _COL = _mongo()
    _mongo_ready = True
except Exception:
    _mongo_ready = False

def _use_local() -> bool:
    if STORE_BACKEND.lower() == "local":
        return True
    return not _mongo_ready

# -------------- Public API -------------------------------------------
def create_run(doc: Dict[str, Any]) -> str:
    if _use_local():
        with _lock:
            data = _local_load()
            rid = doc["_id"]
            data["runs"][rid] = doc
            _local_save(data)
        return doc["_id"]
    else:
        _COL.insert_one(doc)
        return doc["_id"]

def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    if _use_local():
        with _lock:
            data = _local_load()
            return data["runs"].get(run_id)
    else:
        return _COL.find_one({"_id": run_id})

def update_run(run_id: str, fields: Dict[str, Any]) -> None:
    fields["updated_at"] = _now()
    if _use_local():
        with _lock:
            data = _local_load()
            if run_id in data["runs"]:
                data["runs"][run_id].update(fields)
                _local_save(data)
    else:
        _COL.update_one({"_id": run_id}, {"$set": fields})

def list_runs_by_status(status: str, limit: int = 10) -> List[Dict[str, Any]]:
    if _use_local():
        with _lock:
            data = _local_load()
            return [r for r in data["runs"].values() if r.get("status") == status][:limit]
    else:
        cur = _COL.find({"status": status}).sort("created_at", 1).limit(limit)
        return list(cur)
