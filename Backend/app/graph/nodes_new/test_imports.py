# app/agents/tools_smoketest.py
from __future__ import annotations
from pathlib import Path
import sys
import importlib

# ensure root on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graph.nodes_new.data_fetcher import _TOOL_REGISTRY, _import_tool

def main():
    print("== Tool import smoketest ==")
    ok = 0
    fail = 0
    for tool_id, qual in _TOOL_REGISTRY.items():
        logs = []
        fn = _import_tool(qual, logs)
        if fn:
            print(f"[OK]   {tool_id:22} -> {qual}")
            ok += 1
        else:
            print(f"[FAIL] {tool_id:22} -> {qual}")
            for l in logs:
                print("     ", l)
            fail += 1
    print(f"\nSummary: {ok} ok, {fail} failed")

if __name__ == "__main__":
    main()
