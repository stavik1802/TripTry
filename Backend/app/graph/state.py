from pydantic import BaseModel
from typing import Any, Dict, List, Annotated
from operator import add as list_concat

# -------- Deep, no-clobber merge for dicts --------
def _deep_merge(dst: Any, src: Any) -> Any:
    # Scalars or None: prefer existing non-null
    if not isinstance(dst, (dict, list)) or not isinstance(src, (dict, list)):
        return dst if dst is not None else src

    # Dicts: recursive, no-clobber
    if isinstance(dst, dict) and isinstance(src, dict):
        out: Dict[str, Any] = dict(dst)
        for k, v in src.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    # Lists: union w/ order preserved
    if isinstance(dst, list) and isinstance(src, list):
        seen = set()
        out: List[Any] = []
        for x in dst + src:
            key = repr(x)
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out

    # Fallback
    return dst if dst is not None else src

def _merge_dict(a: Dict[str, Any] | None, b: Dict[str, Any] | None) -> Dict[str, Any]:
    """Reducer hook: deep merge b into a without clobbering existing non-null values."""
    return _deep_merge(a or {}, b or {}) or {}

def _keep_first(a: str | None, b: str | None) -> str:
    return a or (b or "")

def _or_bool(a: bool | None, b: bool | None) -> bool:
    return bool(a) or bool(b)

class AppState(BaseModel):
    # Reducers let LangGraph merge parallel branches safely
    run_id: Annotated[str, _keep_first] = ""
    mode: Annotated[str, _keep_first] = "structured"

    request: Annotated[Dict[str, Any], _merge_dict] = {}
    itinerary: Annotated[Dict[str, Any], _merge_dict] = {}
    caps: Annotated[Dict[str, Any], _merge_dict] = {}
    meta: Annotated[Dict[str, Any], _merge_dict] = {}

    logs: Annotated[List[str], list_concat] = []
    done: Annotated[bool, _or_bool] = False
