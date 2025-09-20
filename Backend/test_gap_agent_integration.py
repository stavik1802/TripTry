#!/usr/bin/env python3
"""
Integration test for GapAgent using real APIs
Tests gap detection and filling with actual data
"""

import os
import sys
import asyncio
from typing import Dict, Any

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

# Set API keys for testing
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"


def create_test_context() -> AgentContext:
    """Create a test context with incomplete research data"""
    return AgentContext(
        session_id="test-gap-integration",
        user_request="Plan a 3-day trip to Paris, France. I want to visit the Eiffel Tower and Louvre Museum.",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                # Missing POI data - this should trigger gap detection
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": []  # Empty - should be filled by gap agent
                        }
                    }
                },
                # Missing restaurant data
                "restaurants": {
                    "names_by_city": {
                        "Paris": []  # Empty - should be filled
                    }
                },
                # Missing city fares
                "city_fares": {
                    "city_fares": {
                        "Paris": {}  # Empty - should be filled
                    }
                },
                # Missing intercity data
                "intercity": {
                    "hops": []  # Empty - should be filled
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "travelers": {"adults": 2, "children": 0},
                "dates": {"start": "2024-06-01", "end": "2024-06-04"},
                "preferences": {"pace": "normal", "budget": "medium"},
                "musts": ["Eiffel Tower", "Louvre Museum"],
                "tool_plan": ["poi_discovery", "restaurants_discovery", "city_fare", "intercity_fare"]
            }
        },
        goals=[],
        constraints={}
    )


def print_data_structure(data: Dict[str, Any], prefix: str = "", max_depth: int = 3, current_depth: int = 0):
    """Pretty print data structure for debugging"""
    if current_depth >= max_depth:
        print(f"{prefix}... (max depth reached)")
        return
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                print(f"{prefix}{key}:")
                print_data_structure(value, prefix + "  ", max_depth, current_depth + 1)
            else:
                print(f"{prefix}{key}: {type(value).__name__} = {value}")
    elif isinstance(data, list):
        print(f"{prefix}[list with {len(data)} items]")
        for i, item in enumerate(data[:3]):  # Show first 3 items
            print(f"{prefix}[{i}]:")
            print_data_structure(item, prefix + "  ", max_depth, current_depth + 1)
        if len(data) > 3:
            print(f"{prefix}... and {len(data) - 3} more items")


async def test_gap_detection():
    """Test gap detection without filling"""
    print("🔍 Testing Gap Detection...")
    print("=" * 50)
    
    agent = GapAgent()
    ctx = create_test_context()
    
    # Test gap detection
    missing_items = agent.identify_missing_data(ctx.shared_data["research_data"], ctx.shared_data["planning_data"])
    
    print(f"Found {len(missing_items)} missing items:")
    for i, item in enumerate(missing_items, 1):
        print(f"  {i}. {item.get('path', 'unknown')} - {item.get('description', 'no description')}")
    
    return missing_items


async def test_gap_filling():
    """Test gap filling with real APIs"""
    print("\n🔧 Testing Gap Filling with Real APIs...")
    print("=" * 50)
    
    agent = GapAgent()
    ctx = create_test_context()
    
    print("Initial research data structure:")
    print_data_structure(ctx.shared_data["research_data"])
    
    print(f"\nExecuting gap filling task...")
    result = agent.execute_task(ctx)
    
    print(f"\nGap filling result:")
    print(f"  Status: {result.get('status')}")
    print(f"  Filled items: {result.get('filled_items', 0)}")
    print(f"  Patches applied: {result.get('patches_applied', 0)}")
    
    if result.get('status') == 'success':
        print(f"\nUpdated research data structure:")
        print_data_structure(ctx.shared_data["research_data"])
        
        # Check specific improvements
        research_data = ctx.shared_data["research_data"]
        
        # Check POI data
        pois = research_data.get("poi", {}).get("poi_by_city", {}).get("Paris", {}).get("pois", [])
        print(f"\nPOI data filled: {len(pois)} POIs found")
        for poi in pois[:5]:  # Show first 5
            print(f"  - {poi.get('name', 'Unknown')}")
        
        # Check restaurant data
        restaurants = research_data.get("restaurants", {}).get("names_by_city", {}).get("Paris", [])
        print(f"\nRestaurant data filled: {len(restaurants)} restaurants found")
        for restaurant in restaurants[:5]:  # Show first 5
            print(f"  - {restaurant}")
        
        # Check city fares
        city_fares = research_data.get("city_fares", {}).get("city_fares", {}).get("Paris", {})
        print(f"\nCity fares data filled: {len(city_fares)} fare types")
        for fare_type, fare_data in city_fares.items():
            print(f"  - {fare_type}: {fare_data}")
        
        # Check intercity data
        intercity_hops = research_data.get("intercity", {}).get("hops", [])
        print(f"\nIntercity data filled: {len(intercity_hops)} routes")
        for hop in intercity_hops[:3]:  # Show first 3
            print(f"  - {hop.get('from_city', 'Unknown')} → {hop.get('to_city', 'Unknown')}")
    
    return result


async def main():
    """Run the integration tests"""
    print("🚀 Gap Agent Integration Test")
    print("=" * 50)
    
    try:
        # Test 1: Gap Detection
        missing_items = await test_gap_detection()
        
        if missing_items:
            # Test 2: Gap Filling
            result = await test_gap_filling()
            
            if result.get('status') == 'success':
                print(f"\n✅ Gap Agent Integration Test PASSED")
                print(f"   - Detected {len(missing_items)} missing items")
                print(f"   - Successfully filled gaps using real APIs")
            else:
                print(f"\n❌ Gap Agent Integration Test FAILED")
                print(f"   - Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"\n⚠️  No gaps detected - test data may be complete")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
