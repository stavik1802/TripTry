#!/usr/bin/env python3
"""
Test Script for Trip Interpreter with Mock Data

This script loads mock data and tests the trip interpreter functionality
to verify that the build graph works correctly with the generated data.

Usage:
    python test_trip_interpreter.py --mock-file mock_state_snapshot.json
    python test_trip_interpreter.py --scenario europe_trip
    python test_trip_interpreter.py --scenario asia_trip --test-interpreter
"""

import json
import argparse
import sys
import os
from pathlib import Path

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mock_data_generator import MockDataGenerator, create_scenario_configs
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan, build_appstate_from_travel_state


def load_mock_data(file_path: str) -> dict:
    """Load mock data from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_trip_interpreter(state_snapshot: dict, user_message: str = None) -> dict:
    """Test the trip interpreter with mock data"""
    print("=" * 60)
    print("TESTING TRIP INTERPRETER")
    print("=" * 60)
    
    if user_message is None:
        user_message = state_snapshot.get("user_message", "Plan my trip")
    
    print(f"User message: {user_message}")
    print(f"Available cities: {state_snapshot.get('cities', [])}")
    print(f"Target currency: {state_snapshot.get('fx_meta', {}).get('target', 'Unknown')}")
    
    # Test the trip interpreter
    try:
        result = interpret_trip_plan(user_message, state_snapshot)
        print(f"\nTrip interpreter result:")
        print(f"Tool plan: {result.get('tool_plan', [])}")
        print(f"Notes: {result.get('notes', '')}")
        return result
    except Exception as e:
        print(f"Error in trip interpreter: {e}")
        return {"tool_plan": [], "notes": f"Error: {e}"}


def test_appstate_builder(state_snapshot: dict) -> dict:
    """Test the AppState builder with mock data"""
    print("\n" + "=" * 60)
    print("TESTING APPSTATE BUILDER")
    print("=" * 60)
    
    try:
        appstate = build_appstate_from_travel_state(state_snapshot)
        print(f"AppState created successfully!")
        print(f"Request keys: {list(appstate.request.keys())}")
        print(f"Logs: {len(appstate.logs)} entries")
        print(f"Meta: {list(appstate.meta.keys())}")
        
        # Print detailed request structure
        print(f"\nDetailed request structure:")
        for key, value in appstate.request.items():
            if isinstance(value, dict):
                print(f"  {key}: {len(value)} items")
                if key == "discovery" and "cities" in value:
                    for city, data in value["cities"].items():
                        poi_count = len(data.get("pois", []))
                        rest_count = len(data.get("restaurants", []))
                        print(f"    {city}: {poi_count} POIs, {rest_count} restaurants")
            elif isinstance(value, list):
                print(f"  {key}: {len(value)} items")
            else:
                print(f"  {key}: {value}")
        
        return appstate
    except Exception as e:
        print(f"Error building AppState: {e}")
        return None


def validate_state_snapshot(state_snapshot: dict) -> bool:
    """Validate that the state snapshot has all required fields"""
    print("\n" + "=" * 60)
    print("VALIDATING STATE SNAPSHOT")
    print("=" * 60)
    
    required_fields = [
        "interp", "cities", "city_country_map", "fx_meta",
        "poi", "restaurants", "city_fares", "intercity"
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in state_snapshot:
            missing_fields.append(field)
        else:
            print(f"✓ {field}: Present")
    
    if missing_fields:
        print(f"✗ Missing fields: {missing_fields}")
        return False
    
    # Validate specific structures
    print(f"\nDetailed validation:")
    
    # Check cities
    cities = state_snapshot.get("cities", [])
    print(f"  Cities: {len(cities)} - {cities}")
    
    # Check POI data
    poi_data = state_snapshot.get("poi", {})
    poi_by_city = poi_data.get("poi_by_city", {})
    total_pois = sum(len(city_data.get("pois", [])) for city_data in poi_by_city.values())
    print(f"  POIs: {total_pois} across {len(poi_by_city)} cities")
    
    # Check restaurant data
    rest_data = state_snapshot.get("restaurants", {})
    names_by_city = rest_data.get("names_by_city", {})
    total_restaurants = sum(
        len(restaurants) 
        for city_restaurants in names_by_city.values() 
        for restaurants in city_restaurants.values()
    )
    print(f"  Restaurants: {total_restaurants} across {len(names_by_city)} cities")
    
    # Check city fares
    city_fares = state_snapshot.get("city_fares", {})
    fare_cities = city_fares.get("city_fares", {})
    print(f"  City fares: {len(fare_cities)} cities")
    
    # Check intercity data
    intercity = state_snapshot.get("intercity", {})
    hops = intercity.get("hops", [])
    print(f"  Intercity hops: {len(hops)} connections")
    
    # Check FX data
    fx_meta = state_snapshot.get("fx_meta", {})
    target_currency = fx_meta.get("target", "Unknown")
    to_target = fx_meta.get("to_target", {})
    print(f"  FX: Target {target_currency}, {len(to_target)} conversion rates")
    
    print(f"\n✓ State snapshot validation passed!")
    return True


def test_build_graph_integration(state_snapshot: dict) -> bool:
    """Test integration with the build graph"""
    print("\n" + "=" * 60)
    print("TESTING BUILD GRAPH INTEGRATION")
    print("=" * 60)
    
    try:
        # Import the build graph
        from app.graph.build_graph import build_graph, TravelState
        
        # Create a TravelState from our mock data
        travel_state: TravelState = {
            "user_message": state_snapshot.get("user_message", "Plan my trip"),
            "interp": state_snapshot.get("interp", {}),
            "cities": state_snapshot.get("cities", []),
            "city_country_map": state_snapshot.get("city_country_map", {}),
            "fx_meta": state_snapshot.get("fx_meta", {}),
            "poi": state_snapshot.get("poi", {}),
            "restaurants": state_snapshot.get("restaurants", {}),
            "city_fares": state_snapshot.get("city_fares", {}),
            "intercity": state_snapshot.get("intercity", {}),
            "logs": state_snapshot.get("logs", []),
            "errors": state_snapshot.get("errors", []),
            "plan_queue": state_snapshot.get("plan_queue", []),
            "done_tools": state_snapshot.get("done_tools", []),
            "last_tool": state_snapshot.get("last_tool", None)
        }
        
        print(f"TravelState created with {len(travel_state.get('cities', []))} cities")
        
        # Build the graph
        graph = build_graph()
        print(f"Graph built successfully with {len(graph.nodes)} nodes")
        
        # Test the trip interpreter node specifically
        from app.graph.build_graph import node_trip_interpret
        
        # Run the trip interpreter node
        result_state = node_trip_interpret(travel_state)
        
        print(f"Trip interpreter node executed successfully!")
        print(f"Trip plan queue: {result_state.get('trip_plan_queue', [])}")
        print(f"Trip AppState created: {'trip_appstate' in result_state}")
        
        if 'trip_appstate' in result_state:
            appstate = result_state['trip_appstate']
            print(f"AppState request keys: {list(appstate.request.keys())}")
        
        return True
        
    except Exception as e:
        print(f"Error in build graph integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test trip interpreter with mock data")
    parser.add_argument("--mock-file", help="Path to mock data JSON file")
    parser.add_argument("--scenario", choices=list(create_scenario_configs().keys()), 
                       help="Generate and test a specific scenario")
    parser.add_argument("--test-interpreter", action="store_true", 
                       help="Test the trip interpreter function")
    parser.add_argument("--test-appstate", action="store_true", 
                       help="Test the AppState builder")
    parser.add_argument("--test-integration", action="store_true", 
                       help="Test build graph integration")
    parser.add_argument("--validate-only", action="store_true", 
                       help="Only validate the mock data structure")
    parser.add_argument("--user-message", help="Custom user message for testing")
    
    args = parser.parse_args()
    
    # Load or generate mock data
    if args.scenario:
        print(f"Generating mock data for scenario: {args.scenario}")
        config = create_scenario_configs()[args.scenario]
        generator = MockDataGenerator(config)
        state_snapshot = generator.generate_complete_state_snapshot()
    elif args.mock_file:
        print(f"Loading mock data from: {args.mock_file}")
        state_snapshot = load_mock_data(args.mock_file)
    else:
        print("Error: Must specify either --mock-file or --scenario")
        return 1
    
    # Validate the data
    if not validate_state_snapshot(state_snapshot):
        print("State snapshot validation failed!")
        return 1
    
    if args.validate_only:
        print("Validation complete!")
        return 0
    
    # Run tests based on arguments
    success = True
    
    if args.test_interpreter or not any([args.test_appstate, args.test_integration]):
        result = test_trip_interpreter(state_snapshot, args.user_message)
        if not result.get("tool_plan"):
            success = False
    
    if args.test_appstate or not any([args.test_interpreter, args.test_integration]):
        appstate = test_appstate_builder(state_snapshot)
        if appstate is None:
            success = False
    
    if args.test_integration or not any([args.test_interpreter, args.test_appstate]):
        if not test_build_graph_integration(state_snapshot):
            success = False
    
    if success:
        print(f"\n{'='*60}")
        print("ALL TESTS PASSED! ✓")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("SOME TESTS FAILED! ✗")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    exit(main())
