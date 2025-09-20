#!/usr/bin/env python3
"""
Debug the actual data structure in research_data
"""

import os
import sys
from typing import Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

def debug_data_structure():
    """Debug the actual data structure in research_data"""
    
    print("=== DATA STRUCTURE DEBUG ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Sample research data (from the test output)
    research_data = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "city": "Paris",
                            "name": "Champs-Élysées",
                            "category": "Avenue",
                            "official_url": None,
                            "other_urls": None,
                            "hours": None,
                            "price": None,
                            "coords": None,
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
    
    print(f"📊 Original research_data structure:")
    print(f"  - research_data keys: {list(research_data.keys())}")
    print(f"  - poi keys: {list(research_data['poi'].keys())}")
    print(f"  - poi_by_city keys: {list(research_data['poi']['poi_by_city'].keys())}")
    print(f"  - Paris keys: {list(research_data['poi']['poi_by_city']['Paris'].keys())}")
    print(f"  - pois array length: {len(research_data['poi']['poi_by_city']['Paris']['pois'])}")
    
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
    print(f"\n📊 Updated research_data structure:")
    print(f"  - research_data keys: {list(updated_research_data.keys())}")
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
    
    print(f"\n" + "=" * 50)
    print("🎉 DATA STRUCTURE DEBUG COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    debug_data_structure()
