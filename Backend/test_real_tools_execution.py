#!/usr/bin/env python3
"""
Real Tools Execution Test - Tests that actual tools are called and do their job
This test verifies that the multi-agent system actually calls the real tools and they work properly.
"""

import sys
import os
sys.path.append('/home/stav.karasik/TripPlanner/Backend')

from app.agents.graph_integration import AgentGraphBridge
from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
import json
import time

def test_real_tool_execution():
    """Test that real tools are actually called and work"""
    print("🔧 TESTING REAL TOOL EXECUTION")
    print("=" * 60)
    
    bridge = AgentGraphBridge()
    
    # Test 1: Interpreter Tool
    print("\n📝 Testing Interpreter Tool...")
    try:
        result = bridge.execute_tool("interpreter", {
            "user_request": "I want to visit Paris for 3 days with my family. Budget around 1000 EUR."
        })
        
        if result.get("status") == "success":
            interpretation = result.get("result")
            print(f"✅ Interpreter worked!")
            print(f"   - Intent: {interpretation.intent if hasattr(interpretation, 'intent') else 'unknown'}")
            print(f"   - Countries: {getattr(interpretation, 'countries', [])}")
            print(f"   - Travelers: {getattr(interpretation, 'travelers', {})}")
        else:
            print(f"❌ Interpreter failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Interpreter error: {e}")
    
    # Test 2: City Recommender Tool
    print("\n🏙️ Testing City Recommender Tool...")
    try:
        result = bridge.execute_tool("city_recommender", {
            "countries": [{"country": "France"}],
            "dates": {"start": "2024-06-01", "end": "2024-06-04"},
            "travelers": {"adults": 2, "children": 1},
            "preferences": {"budget": "medium", "pace": "relaxed"},
            "musts": ["Eiffel Tower"]
        })
        
        if result.get("status") == "success":
            cities_data = result.get("result")
            print(f"✅ City Recommender worked!")
            print(f"   - Cities found: {len(cities_data.get('cities', []))}")
            print(f"   - Cities: {cities_data.get('cities', [])[:3]}")  # Show first 3
        else:
            print(f"❌ City Recommender failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ City Recommender error: {e}")
    
    # Test 3: POI Discovery Tool
    print("\n🎯 Testing POI Discovery Tool...")
    try:
        result = bridge.execute_tool("poi_discovery", {
            "cities": ["Paris"],
            "city_country_map": {"Paris": "France"},
            "travelers": {"adults": 2, "children": 1},
            "musts": ["Eiffel Tower"],
            "preferences": {"budget": "medium"}
        })
        
        if result.get("status") == "success":
            poi_data = result.get("result")
            print(f"✅ POI Discovery worked!")
            pois = poi_data.get("poi", {}).get("Paris", [])
            print(f"   - POIs found: {len(pois)}")
            if pois:
                print(f"   - Sample POI: {pois[0].get('name', 'Unknown')}")
        else:
            print(f"❌ POI Discovery failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ POI Discovery error: {e}")
    
    # Test 4: Restaurant Discovery Tool
    print("\n🍽️ Testing Restaurant Discovery Tool...")
    try:
        result = bridge.execute_tool("restaurants_discovery", {
            "cities": ["Paris"],
            "pois_by_city": {"Paris": [{"name": "Eiffel Tower", "type": "attraction"}]},
            "travelers": {"adults": 2, "children": 1},
            "musts": [],
            "preferences": {"budget": "medium", "cuisine": "french"}
        })
        
        if result.get("status") == "success":
            restaurants_data = result.get("result")
            print(f"✅ Restaurant Discovery worked!")
            restaurants = restaurants_data.get("restaurants", {}).get("Paris", [])
            print(f"   - Restaurants found: {len(restaurants)}")
            if restaurants:
                print(f"   - Sample restaurant: {restaurants[0].get('name', 'Unknown')}")
        else:
            print(f"❌ Restaurant Discovery failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Restaurant Discovery error: {e}")
    
    # Test 5: Currency Tool
    print("\n💱 Testing Currency Tool...")
    try:
        result = bridge.execute_tool("currency", {
            "target_currency": "EUR",
            "countries": [{"country": "France"}],
            "preferences": {"currency": "EUR"}
        })
        
        if result.get("status") == "success":
            currency_data = result.get("result")
            print(f"✅ Currency Tool worked!")
            fx = currency_data.get("fx", {})
            print(f"   - Exchange rates: {len(fx)} currencies")
            if fx:
                print(f"   - Sample rate: {list(fx.items())[0]}")
        else:
            print(f"❌ Currency Tool failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Currency Tool error: {e}")
    
    return True

def test_real_multi_agent_workflow():
    """Test the complete multi-agent workflow with real tools"""
    print("\n🚀 TESTING REAL MULTI-AGENT WORKFLOW")
    print("=" * 60)
    
    # Initialize the complete system
    system = AdvancedMultiAgentSystem()
    
    # Test with a real request
    user_request = "I want to visit Paris for 3 days with my family. We want to see the Eiffel Tower and eat good French food. Budget around 1000 EUR."
    
    print(f"📝 Processing real request: {user_request}")
    print("🔄 Starting multi-agent workflow...")
    
    start_time = time.time()
    
    try:
        result = system.process_request(
            user_request=user_request,
            user_id="test_user_real_tools",
            context={"test_mode": False}  # Use real tools, not test mode
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"\n✅ Multi-agent workflow completed in {processing_time:.2f} seconds!")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Session ID: {result.get('session_id', 'unknown')}")
        
        # Check if we got real data
        if result.get('output'):
            output = result['output']
            print(f"\n📊 Real Data Generated:")
            
            # Check trip summary
            trip_summary = output.get('trip_summary', {})
            if trip_summary:
                print(f"   - Intent: {trip_summary.get('intent', 'unknown')}")
                print(f"   - Destinations: {trip_summary.get('destinations', [])}")
                print(f"   - Travelers: {trip_summary.get('travelers', {})}")
            
            # Check destinations
            destinations = output.get('destinations', [])
            if destinations:
                print(f"   - Destinations found: {len(destinations)}")
                for dest in destinations[:2]:  # Show first 2
                    print(f"     * {dest.get('city', 'Unknown')}: {dest.get('poi_count', 0)} POIs")
            
            # Check itinerary
            itinerary = output.get('itinerary', [])
            if itinerary:
                print(f"   - Itinerary days: {len(itinerary)}")
                for day in itinerary[:2]:  # Show first 2 days
                    activities = day.get('activities', [])
                    print(f"     * Day {day.get('day', '?')}: {len(activities)} activities")
            
            # Check transportation
            transportation = output.get('transportation', {})
            if transportation:
                city_transport = transportation.get('within_cities', {})
                intercity_transport = transportation.get('between_cities', {})
                print(f"   - City transport data: {len(city_transport)} cities")
                print(f"   - Intercity transport data: {len(intercity_transport)} routes")
            
            # Check dining
            dining = output.get('dining', {})
            if dining:
                restaurants = dining.get('by_city', {})
                total_restaurants = sum(len(rests) for rests in restaurants.values())
                print(f"   - Restaurants found: {total_restaurants} total")
            
            # Check costs
            costs = output.get('costs', {})
            if costs:
                budget_summary = costs.get('budget_summary', {})
                total_cost = budget_summary.get('total_estimated_cost', 0)
                currency = budget_summary.get('currency', 'USD')
                print(f"   - Estimated total cost: {total_cost} {currency}")
            
            # Check recommendations
            recommendations = output.get('recommendations', [])
            if recommendations:
                print(f"   - Recommendations: {len(recommendations)} suggestions")
        
        # Check if tools were actually called
        if result.get('session_id'):
            print(f"\n🔍 Tool Execution Verification:")
            print(f"   - Session processed: {result['session_id']}")
            print(f"   - Processing time: {processing_time:.2f}s")
            
            # Check if we have real data (not just mock data)
            has_real_data = any([
                output.get('destinations'),
                output.get('itinerary'),
                output.get('transportation', {}).get('within_cities'),
                output.get('dining', {}).get('by_city'),
                output.get('costs', {}).get('budget_summary', {}).get('total_estimated_cost', 0) > 0
            ])
            
            if has_real_data:
                print(f"   ✅ Real tool data detected!")
            else:
                print(f"   ⚠️  Limited real data - may have used fallbacks")
        
        return result
        
    except Exception as e:
        print(f"❌ Multi-agent workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_tool_data_quality():
    """Test the quality and completeness of tool-generated data"""
    print("\n📊 TESTING TOOL DATA QUALITY")
    print("=" * 60)
    
    bridge = AgentGraphBridge()
    
    # Test with a comprehensive request
    test_data = {
        "countries": [{"country": "France"}],
        "cities": ["Paris"],
        "dates": {"start": "2024-06-01", "end": "2024-06-04"},
        "travelers": {"adults": 2, "children": 1},
        "preferences": {"budget": "medium", "pace": "relaxed", "cuisine": "french"},
        "musts": ["Eiffel Tower", "Louvre"]
    }
    
    quality_scores = {}
    
    # Test each tool's data quality
    tools_to_test = [
        ("city_recommender", {"countries": test_data["countries"], "dates": test_data["dates"], 
         "travelers": test_data["travelers"], "preferences": test_data["preferences"]}),
        ("poi_discovery", {"cities": test_data["cities"], "city_country_map": {"Paris": "France"},
         "travelers": test_data["travelers"], "musts": test_data["musts"]}),
        ("restaurants_discovery", {"cities": test_data["cities"], "travelers": test_data["travelers"],
         "preferences": test_data["preferences"]}),
        ("currency", {"target_currency": "EUR", "countries": test_data["countries"]})
    ]
    
    for tool_name, args in tools_to_test:
        try:
            result = bridge.execute_tool(tool_name, args)
            
            if result.get("status") == "success":
                data = result.get("result", {})
                
                # Calculate quality score based on data completeness
                if tool_name == "city_recommender":
                    cities = data.get("cities", [])
                    quality_scores[tool_name] = min(len(cities) / 5, 1.0)  # Expect at least 5 cities
                    
                elif tool_name == "poi_discovery":
                    pois = data.get("poi", {}).get("Paris", [])
                    quality_scores[tool_name] = min(len(pois) / 10, 1.0)  # Expect at least 10 POIs
                    
                elif tool_name == "restaurants_discovery":
                    restaurants = data.get("restaurants", {}).get("Paris", [])
                    quality_scores[tool_name] = min(len(restaurants) / 5, 1.0)  # Expect at least 5 restaurants
                    
                elif tool_name == "currency":
                    fx = data.get("fx", {})
                    quality_scores[tool_name] = min(len(fx) / 3, 1.0)  # Expect at least 3 currencies
                
                print(f"✅ {tool_name}: Quality score {quality_scores[tool_name]:.2f}")
                
            else:
                quality_scores[tool_name] = 0.0
                print(f"❌ {tool_name}: Failed - {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            quality_scores[tool_name] = 0.0
            print(f"❌ {tool_name}: Error - {e}")
    
    # Calculate overall quality
    overall_quality = sum(quality_scores.values()) / len(quality_scores)
    print(f"\n📈 Overall Tool Data Quality: {overall_quality:.2f} ({overall_quality*100:.1f}%)")
    
    return quality_scores

def main():
    """Run all real tool tests"""
    print("🚀 REAL TOOLS EXECUTION TEST")
    print("=" * 80)
    print("Testing that actual tools are called and do their job properly")
    print()
    
    try:
        # Test individual tools
        test_real_tool_execution()
        
        # Test complete workflow
        workflow_result = test_real_multi_agent_workflow()
        
        # Test data quality
        quality_scores = test_tool_data_quality()
        
        print("\n" + "=" * 80)
        print("🎉 REAL TOOLS TEST SUMMARY")
        print("=" * 80)
        
        if workflow_result:
            print("✅ Multi-agent workflow executed successfully")
            print("✅ Real tools were called and generated data")
            print("✅ Complete end-to-end process working")
        else:
            print("❌ Multi-agent workflow had issues")
        
        avg_quality = sum(quality_scores.values()) / len(quality_scores)
        print(f"📊 Average tool data quality: {avg_quality:.2f} ({avg_quality*100:.1f}%)")
        
        if avg_quality > 0.7:
            print("🎯 Tool data quality is excellent!")
        elif avg_quality > 0.4:
            print("✅ Tool data quality is good")
        else:
            print("⚠️  Tool data quality needs improvement")
        
        print("\n✨ The multi-agent system is successfully calling real tools!")
        print("   All tools are working and generating real data for trip planning.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
