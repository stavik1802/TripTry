#!/usr/bin/env python3
"""
Forced gap test - creates data structure that will definitely trigger gap detection
"""

import os
import sys

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

# Set API keys
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"


def test_forced_gap_detection():
    """Test gap detection with proper data structure that will trigger gaps"""
    print("🔍 Testing Forced Gap Detection...")
    
    agent = GapAgent()
    
    # Create context that will definitely trigger gap detection
    ctx = AgentContext(
        session_id="test-forced-gap",
        user_request="Plan a trip to Paris with Eiffel Tower and Louvre",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                # POI data with missing fields that should trigger gaps
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": [
                                {
                                    "name": "Eiffel Tower",
                                    # Missing price, hours, coords - should trigger gaps
                                },
                                {
                                    "name": "Louvre Museum",
                                    # Missing price, hours, coords - should trigger gaps
                                }
                            ]
                        }
                    }
                },
                # Restaurant data with missing details
                "restaurants": {
                    "names_by_city": {
                        "Paris": ["Café de Flore", "Le Comptoir du Relais"]
                    },
                    "links_by_city": {
                        "Paris": {}  # Missing links - should trigger gaps
                    },
                    "details_by_city": {
                        "Paris": {}  # Missing details - should trigger gaps
                    }
                },
                # City fares with missing data
                "city_fares": {
                    "city_fares": {
                        "Paris": {
                            "transit": {},  # Missing transit data
                            "taxi": {}      # Missing taxi data
                        }
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower", "Louvre"],
                "tool_plan": ["poi_discovery", "restaurants_discovery", "city_fare"]
            }
        },
        goals=[],
        constraints={}
    )
    
    print("Testing gap detection with data that has missing fields...")
    
    # Test gap detection directly
    missing_items = agent.identify_missing_data(ctx.shared_data["research_data"], ctx.shared_data["planning_data"])
    
    print(f"\nFound {len(missing_items)} missing items:")
    for i, item in enumerate(missing_items, 1):
        print(f"  {i}. {item.get('path', 'unknown')}")
        print(f"     Description: {item.get('description', 'no description')}")
        print(f"     Schema: {item.get('schema', 'no schema')}")
        print()
    
    return missing_items


def test_forced_gap_filling():
    """Test gap filling with forced gaps"""
    print("\n🔧 Testing Forced Gap Filling...")
    
    agent = GapAgent()
    
    # Create context with gaps that will be detected
    ctx = AgentContext(
        session_id="test-forced-filling",
        user_request="Find restaurants and POI details for Paris",
        conversation_history=[],
        shared_data={
            "research_data": {
                "cities": ["Paris"],
                "city_country_map": {"Paris": "France"},
                # POI data with missing fields
                "poi": {
                    "poi_by_city": {
                        "Paris": {
                            "pois": [
                                {
                                    "name": "Eiffel Tower",
                                    # Missing price, hours, coords
                                }
                            ]
                        }
                    }
                },
                # Restaurant data with missing details
                "restaurants": {
                    "names_by_city": {
                        "Paris": ["Café de Flore"]
                    },
                    "links_by_city": {
                        "Paris": {}  # Missing links
                    }
                }
            },
            "planning_data": {
                "countries": [{"country": "France", "cities": ["Paris"]}],
                "musts": ["Eiffel Tower"],
                "tool_plan": ["poi_discovery", "restaurants_discovery"]
            }
        },
        goals=[],
        constraints={}
    )
    
    print("Before gap filling:")
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    restaurants = ctx.shared_data["research_data"]["restaurants"]["names_by_city"]["Paris"]
    print(f"  Restaurants: {len(restaurants)}")
    print(f"  Restaurant links: {len(ctx.shared_data['research_data']['restaurants']['links_by_city']['Paris'])}")
    
    # Execute gap filling
    result = agent.execute_task(ctx)
    
    print(f"\nGap filling result: {result.get('status')}")
    print(f"Filled items: {result.get('filled_items', 0)}")
    print(f"Patches applied: {result.get('patches_applied', 0)}")
    
    # Check results
    pois = ctx.shared_data["research_data"]["poi"]["poi_by_city"]["Paris"]["pois"]
    print(f"\nAfter gap filling:")
    print(f"  POIs: {len(pois)}")
    for poi in pois:
        print(f"    - {poi.get('name')}: price={poi.get('price')}, hours={poi.get('hours')}")
    
    restaurants = ctx.shared_data["research_data"]["restaurants"]["names_by_city"]["Paris"]
    print(f"  Restaurants: {len(restaurants)}")
    print(f"  Restaurant links: {len(ctx.shared_data['research_data']['restaurants']['links_by_city']['Paris'])}")
    
    return result


def main():
    """Run the forced gap tests"""
    print("🧪 Forced Gap Agent Test - Real API Calls")
    print("=" * 50)
    
    try:
        # Test 1: Gap Detection
        missing_items = test_forced_gap_detection()
        
        if missing_items:
            # Test 2: Gap Filling
            result = test_forced_gap_filling()
            
            print(f"\n📊 Test Summary:")
            print(f"  Missing items detected: {len(missing_items)}")
            print(f"  Gap filling result: {result.get('status')}")
            print(f"  Items filled: {result.get('filled_items', 0)}")
            
            if result.get('status') == 'success':
                print(f"\n✅ Gap agent successfully processed missing data!")
            else:
                print(f"\n❌ Gap filling failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"\n⚠️  No gaps detected - trying with different data structure...")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
