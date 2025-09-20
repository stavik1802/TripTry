#!/usr/bin/env python3
"""
Test to see the actual data structure after gap filling
"""

import os
import sys
import json
from typing import Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

def test_gap_data_structure():
    """Test the actual data structure after gap filling"""
    
    print("=== GAP DATA STRUCTURE TEST ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Sample research data with missing fields
    research_data = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "city": "Paris",
                            "name": "Eiffel Tower",
                            "category": "Monument",
                            "official_url": "https://www.toureiffel.paris/en",
                            "other_urls": None,
                            "hours": None,  # MISSING
                            "price": None,  # MISSING
                            "coords": None,  # MISSING
                            "source_urls": ["http://example.com"],
                            "source_note": "tavily:search",
                            "score": 0.0
                        }
                    ],
                    "sources": ["http://example.com"]
                }
            }
        }
    }
    
    # Sample planning data
    planning_data = {
        "intent": "poi_lookup",
        "countries": [{"country": "France", "cities": ["Paris"]}],
        "tool_plan": ["poi.discovery"],
        "target_currency": "EUR"
    }
    
    print(f"📊 Original POI structure:")
    print(f"  - poi.poi_by_city.Paris.pois: {len(research_data['poi']['poi_by_city']['Paris']['pois'])} items")
    print(f"  - First POI: {research_data['poi']['poi_by_city']['Paris']['pois'][0]['name']}")
    print(f"  - Hours: {research_data['poi']['poi_by_city']['Paris']['pois'][0]['hours']}")
    print(f"  - Price: {research_data['poi']['poi_by_city']['Paris']['pois'][0]['price']}")
    print(f"  - Coords: {research_data['poi']['poi_by_city']['Paris']['pois'][0]['coords']}")
    
    # Test gap filling
    context = AgentContext(
        session_id="test_session",
        user_request="Tell me about the Eiffel Tower in Paris",
        shared_data={
            "research_data": research_data,
            "planning_data": planning_data
        }
    )
    
    print(f"\n🔍 Running gap filling...")
    result = gap_agent.execute_task(context)
    
    print(f"\n📊 After gap filling:")
    print(f"  - Result status: {result.get('status', 'unknown')}")
    print(f"  - Filled items: {result.get('filled_items', 0)}")
    print(f"  - Patches applied: {result.get('patches_applied', 0)}")
    
    # Check the actual data structure
    updated_research_data = context.shared_data["research_data"]
    print(f"\n📊 Updated POI structure:")
    print(f"  - poi keys: {list(updated_research_data['poi'].keys())}")
    print(f"  - poi_by_city keys: {list(updated_research_data['poi']['poi_by_city'].keys())}")
    print(f"  - Paris keys: {list(updated_research_data['poi']['poi_by_city']['Paris'].keys())}")
    
    # Check if the POI array still exists
    if "pois" in updated_research_data['poi']['poi_by_city']['Paris']:
        pois = updated_research_data['poi']['poi_by_city']['Paris']['pois']
        print(f"  - pois array length: {len(pois)}")
        if pois:
            print(f"  - First POI: {pois[0]['name']}")
            print(f"  - Hours: {pois[0].get('hours', 'NOT FOUND')}")
            print(f"  - Price: {pois[0].get('price', 'NOT FOUND')}")
            print(f"  - Coords: {pois[0].get('coords', 'NOT FOUND')}")
    else:
        print(f"  - ❌ 'pois' key missing!")
        print(f"  - Available keys: {list(updated_research_data['poi']['poi_by_city']['Paris'].keys())}")
    
    # Check for any new keys that might contain the filled data
    paris_data = updated_research_data['poi']['poi_by_city']['Paris']
    for key, value in paris_data.items():
        if key != "pois" and key != "sources":
            print(f"  - Found unexpected key '{key}': {type(value)}")
            if isinstance(value, dict):
                print(f"    - Keys: {list(value.keys())}")
    
    print(f"\n" + "=" * 50)
    print("🎉 GAP DATA STRUCTURE TEST COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    test_gap_data_structure()
