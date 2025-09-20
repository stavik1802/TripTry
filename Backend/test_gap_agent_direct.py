#!/usr/bin/env python3
"""
Direct test of the Gap Agent to debug why it's not working
"""

import os
import sys
import json
from typing import Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

def test_gap_agent_direct():
    """Test the gap agent directly with sample data"""
    
    print("=== DIRECT GAP AGENT TEST ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    print(f"✅ Created GapAgent: {gap_agent.agent_id}")
    
    # Sample research data with missing fields (like what POI discovery would return)
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
                            "hours": None,  # MISSING - should be detected
                            "price": None,  # MISSING - should be detected
                            "coords": None,  # MISSING - should be detected
                            "source_urls": ["http://example.com"],
                            "source_note": "tavily:search",
                            "score": 0.0
                        },
                        {
                            "city": "Paris",
                            "name": "Louvre Museum",
                            "category": "Museum",
                            "official_url": "https://www.louvre.fr/en",
                            "other_urls": None,
                            "hours": None,  # MISSING - should be detected
                            "price": None,  # MISSING - should be detected
                            "coords": None,  # MISSING - should be detected
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
    
    print(f"\n📊 Test Data:")
    print(f"  - Cities: {research_data['cities']}")
    print(f"  - POIs found: {len(research_data['poi']['poi_by_city']['Paris']['pois'])}")
    print(f"  - Tool plan: {planning_data['tool_plan']}")
    
    # Test 1: Direct method call
    print(f"\n🔍 TEST 1: Direct identify_missing_data call")
    print("-" * 40)
    
    try:
        missing_items = gap_agent.identify_missing_data(research_data, planning_data)
        print(f"✅ identify_missing_data succeeded")
        print(f"📊 Found {len(missing_items)} missing items")
        
        if missing_items:
            print(f"\n🔍 Missing items details:")
            for i, item in enumerate(missing_items[:5]):  # Show first 5
                print(f"  {i+1}. Path: {item.get('path', 'unknown')}")
                print(f"     Description: {item.get('description', 'no description')}")
                print(f"     Context keys: {list(item.get('context', {}).keys())}")
                print()
        else:
            print("❌ No missing items found - this might be the problem!")
            
    except Exception as e:
        print(f"❌ identify_missing_data failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Execute task with context
    print(f"\n🔍 TEST 2: Execute task with AgentContext")
    print("-" * 40)
    
    try:
        # Create a mock context
        context = AgentContext(
            session_id="test_session",
            user_request="Tell me about the Eiffel Tower in Paris",
            shared_data={
                "research_data": research_data,
                "planning_data": planning_data
            }
        )
        
        result = gap_agent.execute_task(context)
        print(f"✅ execute_task succeeded")
        print(f"📊 Result: {result.get('status', 'unknown')}")
        print(f"📊 Message: {result.get('message', 'no message')}")
        
        if result.get('status') == 'success':
            print(f"✅ Gap agent completed successfully")
        else:
            print(f"❌ Gap agent failed: {result.get('error', 'unknown error')}")
            
    except Exception as e:
        print(f"❌ execute_task failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Check gap detection functions directly
    print(f"\n🔍 TEST 3: Test gap detection functions directly")
    print("-" * 40)
    
    try:
        from app.graph.gap.specs import _missing_pois
        
        # Structure state as expected by specs
        structured_state = {
            **research_data,
            **planning_data,
            "research_data": research_data,
            "planning_data": planning_data,
            "done_tools": planning_data.get("tool_plan", [])
        }
        
        print(f"📊 Structured state keys: {list(structured_state.keys())}")
        print(f"📊 Done tools: {structured_state.get('done_tools', [])}")
        print(f"📊 POI structure: {type(structured_state.get('poi', {}))}")
        
        missing_pois = _missing_pois(structured_state)
        print(f"✅ _missing_pois succeeded")
        print(f"📊 Found {len(missing_pois)} missing POI items")
        
        if missing_pois:
            print(f"\n🔍 Missing POI items:")
            for i, item in enumerate(missing_pois[:3]):
                print(f"  {i+1}. {item.get('path', 'unknown')} - {item.get('description', 'no description')}")
        else:
            print("❌ No missing POI items found - this might be the problem!")
            
    except Exception as e:
        print(f"❌ _missing_pois failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n" + "=" * 50)
    print("🎉 DIRECT GAP AGENT TEST COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    test_gap_agent_direct()
