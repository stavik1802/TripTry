"""
Patch Utilities for TripPlanner Multi-Agent System

This module provides utilities for applying patches to data structures, supporting
complex path navigation including array indexing and selector-based access.
It enables the gap agent to seamlessly integrate discovered data into existing structures.

Key features:
- Selector-aware path navigation (e.g., foo.bar[name=Eiffel Tower].hours)
- Array indexing and element selection utilities
- Data structure patching and merging capabilities
- Complex path parsing and validation
- Safe data structure modification

The module enables sophisticated data patching that allows the gap agent to
precisely update specific parts of complex nested data structures.
"""

from __future__ import annotations
from typing import Any, Dict
import re

# Selector-aware utilities so we can read/write paths like: foo.bar[name=Eiffel Tower].hours
_SEL = re.compile(r"^(?P<key>[^[]+)(?:\[(?P<sk>[^=\]]+)=(?P<sv>[^\]]+)\])?$")

def exists_selector(root: Dict[str, Any], dotted: str) -> bool:
    cur: Any = root
    for tok in dotted.split("."):
        m = _SEL.match(tok)
        if not m or not isinstance(cur, dict):
            return False
        key, sk, sv = m.group("key"), m.group("sk"), m.group("sv")
        if sk is None:
            if key not in cur:
                return False
            cur = cur[key]
        else:
            arr = cur.get(key)
            if not isinstance(arr, list):
                return False
            found = None
            for it in arr:
                if isinstance(it, dict) and str(it.get(sk)) == sv:
                    found = it
                    break
            if found is None:
                return False
            cur = found
    return cur is not None

def _apply_one_selector(root: Dict[str, Any], dotted: str, value: Any) -> None:
    cur: Any = root
    parts = dotted.split(".")
    for i, tok in enumerate(parts):
        m = _SEL.match(tok)
        if not m:
            return
        key, sk, sv = m.group("key"), m.group("sk"), m.group("sv")
        last = (i == len(parts) - 1)
        if sk is None:
            if last:
                if isinstance(cur, dict):
                    cur[key] = value
                return
            if key not in cur or not isinstance(cur[key], (dict, list)):
                cur[key] = {}
            cur = cur[key]
        else:
            if not isinstance(cur, dict):
                return
            arr = cur.get(key)
            if not isinstance(arr, list):
                arr = []
                cur[key] = arr
            target = None
            for it in arr:
                if isinstance(it, dict) and str(it.get(sk)) == sv:
                    target = it
                    break
            if target is None:
                target = {sk: sv}
                arr.append(target)
            if last:
                if isinstance(value, dict):
                    target.update(value)
                else:
                    target["value"] = value
            else:
                cur = target

def apply_patches_selector(root: Dict[str, Any], patches: Dict[str, Any]) -> None:
    for path, val in patches.items():
        _apply_one_selector(root, path, val)
