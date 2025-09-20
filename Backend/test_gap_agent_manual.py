#!/usr/bin/env python3
"""
Test gap agent with manually created state that has proper data structure
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

def test_gap_agent_with_manual_state():
    print("=== TESTING GAP AGENT WITH MANUAL STATE ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Create a state with proper data structure that should trigger gap detection
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
        "restaurants": {
            "names_by_city": {
                "Paris": {
                    "fine_dining": [
                        {
                            "name": "Le Jules Verne",
                            "cuisine": "French",
                            # Missing: url
                        }
                    ]
                }
            }
        },
        "city_fares": {
            "city_fares": {
                "Paris": {
                    "transit": {
                        "single": {"amount": 2.10, "currency": "EUR"},
                        "day_pass": {"amount": 8.45, "currency": "EUR"},
                        # Missing: weekly_pass
                    },
                    "taxi": {
                        "base": 4.00,
                        "per_km": 1.50,
                        "per_min": 0.50,
                        "currency": "EUR"
                    }
                }
            }
        },
        "intercity": {
            "hops": {
                "Paris -> Lyon": {
                    "rail": {
                        "duration_min": 120,
                        "price": {"amount": 45.00, "currency": "EUR"}
                    },
                    "bus": {
                        "duration_min": 180,
                        "price": {"amount": 25.00, "currency": "EUR"}
                    }
                    # Missing: flight
                }
            }
        },
        "done_tools": ["poi.discovery", "restaurants.discovery", "fares.city", "fares.intercity"]
    }
    
    print(f"📋 Initial state:")
    print(f"   Cities: {test_state['cities']}")
    print(f"   POI data: {test_state['poi']['poi_by_city']['Paris']['pois'][0]}")
    print(f"   Restaurant data: {test_state['restaurants']['names_by_city']['Paris']['fine_dining'][0]}")
    print(f"   City fares: {test_state['city_fares']['city_fares']['Paris']['transit']}")
    print(f"   Intercity: {test_state['intercity']['hops']['Paris -> Lyon']}")
    
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
        
        # Show gap results details
        items = gap_results.get('items', [])
        if items:
            print(f"\n📋 Gap filling details:")
            for item in items:
                print(f"   - {item.get('path')}: {item.get('value')}")
    else:
        print(f"   ❌ Gap filling failed: {result.get('error')}")

if __name__ == "__main__":
    test_gap_agent_with_manual_state()

