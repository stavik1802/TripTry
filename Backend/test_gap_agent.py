#!/usr/bin/env python3
"""
Simple test to verify gap agent can fill missing fields
"""
import os
import sys
sys.path.append('/home/stav.karasik/TripPlanner/Backend')

# Set API keys
os.environ['TAVILY_API_KEY'] = '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'
os.environ['OPENAI_API_KEY'] = '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'

from app.agents.gap_agent import GapAgent
from app.agents.graph_integration import AgentGraphBridge
from app.agents.base_agent import AgentContext

def test_gap_agent():
    print("=== TESTING GAP AGENT WITH MISSING FIELD ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Create a state with some data but missing POI details
    test_state = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "name": "Eiffel Tower",
                            "description": "Iconic iron tower",
                            # Missing: official_url, hours, price, coords
                        }
                    ]
                }
            }
        },
        "done_tools": ["poi.discovery"]  # Mark POI discovery as done
    }
    
    print(f"📋 Initial state:")
    print(f"   Cities: {test_state['cities']}")
    print(f"   POI data: {test_state['poi']['poi_by_city']['Paris']['pois'][0]}")
    
    # Test gap detection
    print(f"\n🔍 Testing gap detection...")
    missing_items = gap_agent.identify_missing_data(test_state)
    print(f"   Found {len(missing_items)} missing items:")
    for item in missing_items:
        print(f"   - {item['path']}: {item['description']}")
    
    if not missing_items:
        print("   ❌ No missing items detected!")
        return
    
    # Test gap filling
    print(f"\n🔧 Testing gap filling...")
    context = AgentContext()
    context.shared_data = {"current_state": test_state}
    
    result = gap_agent.execute_task(context)
    
    print(f"\n📊 Gap filling result:")
    print(f"   Status: {result.get('status')}")
    print(f"   Filled items: {result.get('filled_items', 0)}")
    
    if result.get('status') == 'success':
        patched_state = result.get('patched_state', {})
        gap_results = result.get('gap_results', {})
        print(f"\n✅ Gap filling successful!")
        print(f"   Patched state keys: {list(patched_state.keys())}")
        print(f"   Gap results keys: {list(gap_results.keys())}")
        
        # Check if POI details were filled in patched state
        if 'poi' in patched_state:
            poi_data = patched_state['poi']
            if 'poi_by_city' in poi_data:
                paris_pois = poi_data['poi_by_city'].get('Paris', {}).get('pois', [])
                if paris_pois:
                    eiffel = paris_pois[0]
                    print(f"\n🏗️ Eiffel Tower data after filling:")
                    print(f"   Name: {eiffel.get('name')}")
                    print(f"   Official URL: {eiffel.get('official_url', 'Not filled')}")
                    print(f"   Hours: {eiffel.get('hours', 'Not filled')}")
                    print(f"   Price: {eiffel.get('price', 'Not filled')}")
                    print(f"   Coords: {eiffel.get('coords', 'Not filled')}")
        
        # Show gap results details
        items = gap_results.get('items', [])
        if items:
            print(f"\n📋 Gap filling details:")
            for item in items:
                print(f"   - {item.get('path')}: {item.get('value')}")
    else:
        print(f"   ❌ Gap filling failed: {result.get('error')}")

if __name__ == "__main__":
    test_gap_agent()
