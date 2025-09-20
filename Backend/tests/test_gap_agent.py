import os
import sys
import types
import pytest

# Ensure Backend/ is on the path so we can import app.*
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext


def _make_context(initial_research: dict | None = None, initial_planning: dict | None = None) -> AgentContext:
    return AgentContext(
        session_id="test-session",
        user_request="Plan a short Paris trip",
        conversation_history=[],
        shared_data={
            "research_data": initial_research or {},
            "planning_data": initial_planning or {},
        },
        goals=[],
        constraints={},
    )


def test_gap_agent_applies_patches_success(monkeypatch):
    """
    Verifies that when the gap tool returns patches, GapAgent applies them
    into context.shared_data["research_data"] using dot-paths.
    """
    agent = GapAgent()

    # Seed minimal state: cities known but POIs missing
    ctx = _make_context(
        initial_research={
            "cities": ["Paris"],
            # no poi key yet → should be created by patches
        },
        initial_planning={
            "countries": [{"country": "France", "cities": ["Paris"]}],
            "tool_plan": ["poi_discovery"],
        },
    )

    # Force identify_missing_data to return a specific gap path
    missing_items = [
        {
            "path": "poi.poi_by_city.Paris.pois",
            "description": "POIs for Paris are missing",
        }
    ]

    monkeypatch.setattr(agent, "identify_missing_data", lambda *args, **kwargs: missing_items)

    # Mock bridge.execute_tool to return patches for the missing path
    def _mock_execute_tool(name, args):
        assert name == "gap_data"
        assert isinstance(args, dict)
        return {
            "status": "success",
            "result": {
                "items": [
                    {
                        "path": "poi.poi_by_city.Paris.pois",
                        "filled": True,
                    }
                ],
                "patches": {
                    "poi.poi_by_city.Paris.pois": [
                        {"name": "Eiffel Tower"},
                        {"name": "Louvre Museum"},
                    ]
                },
            },
        }

    monkeypatch.setattr(agent.graph_bridge, "execute_tool", _mock_execute_tool)

    # Execute
    result = agent.execute_task(ctx)

    # Assertions
    assert result.get("status") == "success"
    rd = ctx.shared_data.get("research_data", {})
    assert "poi" in rd
    assert "poi_by_city" in rd["poi"]
    assert "Paris" in rd["poi"]["poi_by_city"]
    pois = rd["poi"]["poi_by_city"]["Paris"].get("pois", [])
    assert any(p.get("name") == "Eiffel Tower" for p in pois)
    assert any(p.get("name") == "Louvre Museum" for p in pois)


def test_gap_agent_synthesizes_patches_on_error(monkeypatch):
    """
    Verifies that when the gap tool errors out, GapAgent synthesizes neutral patches
    to unblock the pipeline and still returns success.
    """
    agent = GapAgent()

    ctx = _make_context(
        initial_research={
            "cities": ["Paris"],
        },
        initial_planning={
            "countries": [{"country": "France", "cities": ["Paris"]}],
            "tool_plan": ["poi_discovery"],
        },
    )

    missing_items = [
        {
            "path": "poi.poi_by_city.Paris.pois",
            "description": "POIs for Paris are missing",
        },
        {
            "path": "city_fares.city_fares.Paris",
            "description": "City fares for Paris are missing",
        },
    ]

    monkeypatch.setattr(agent, "identify_missing_data", lambda *args, **kwargs: missing_items)

    # Simulate tool failure → GapAgent should synthesize patches
    def _mock_execute_tool(name, args):
        return {"status": "error", "error": "network_failure"}

    monkeypatch.setattr(agent.graph_bridge, "execute_tool", _mock_execute_tool)

    result = agent.execute_task(ctx)
    assert result.get("status") == "success"  # soft-success to keep pipeline moving

    rd = ctx.shared_data.get("research_data", {})
    # After synthesized patches, the paths should exist with neutral containers
    assert "poi" in rd
    assert "poi_by_city" in rd["poi"]
    assert "Paris" in rd["poi"]["poi_by_city"]
    assert isinstance(rd["poi"]["poi_by_city"]["Paris"].get("pois", []), list)

    assert "city_fares" in rd
    assert "Paris" in rd["city_fares"].get("city_fares", {}) or isinstance(
        rd["city_fares"], dict
    )


