#!/usr/bin/env python3
"""
Test Script for Trip Interpreter Only (Bypassing Discovery Phase)

This script tests the trip interpreter functionality directly without running
the full build graph discovery phase. It loads mock data and tests only the
final phase tools.

Usage:
    python test_trip_interpreter_only.py --scenario europe_trip
    python test_trip_interpreter_only.py --mock-file mock_state_snapshot.json
"""

import json
import argparse
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mock_data_generator import MockDataGenerator, create_scenario_configs
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan, build_appstate_from_travel_state


def load_mock_data(file_path: str) -> dict:
    """Load mock data from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_trip_interpreter_direct(state_snapshot: dict, user_message: str = None) -> dict:
    """Test the trip interpreter directly with mock data"""
    print("=" * 60)
    print("TESTING TRIP INTERPRETER (DIRECT)")
    print("=" * 60)
    
    if user_message is None:
        user_message = state_snapshot.get("user_message", "Plan my trip")
    
    print(f"User message: {user_message}")
    print(f"Available cities: {state_snapshot.get('cities', [])}")
    print(f"Target currency: {state_snapshot.get('fx_meta', {}).get('target', 'Unknown')}")
    
    # Test the trip interpreter function directly
    try:
        result = interpret_trip_plan(user_message, state_snapshot)
        print(f"\nTrip interpreter result:")
        print(f"Tool plan: {result.get('tool_plan', [])}")
        print(f"Notes: {result.get('notes', '')}")
        return result
    except Exception as e:
        print(f"Error in trip interpreter: {e}")
        import traceback
        traceback.print_exc()
        return {"tool_plan": [], "notes": f"Error: {e}"}


def test_appstate_builder(state_snapshot: dict) -> Any:
    """Test the AppState builder with mock data"""
    print("\n" + "=" * 60)
    print("TESTING APPSTATE BUILDER")
    print("=" * 60)
    
    try:
        appstate = build_appstate_from_travel_state(state_snapshot)
        print(f"AppState created successfully!")
        print(f"Request keys: {list(appstate.request.keys())}")
        print(f"Logs: {len(appstate.logs)} entries")
        
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
        import traceback
        traceback.print_exc()
        return None


def test_final_tools_mock(appstate: Any) -> None:
    """Test the final tools with mock implementations"""
    print("\n" + "=" * 60)
    print("TESTING FINAL TOOLS (MOCK)")
    print("=" * 60)
    
    if appstate is None:
        print("Cannot test final tools - AppState is None")
        return
    
    # Import the mock functions from build_graph
    try:
        from app.graph.build_graph import (
            _mock_discovery_costs, _mock_city_graph, 
            _mock_optimize, _mock_trip_maker
        )
        
        print("Testing discovery.costs (mock)...")
        appstate = _mock_discovery_costs(appstate)
        print(f"  Discovery data added: {'discovery' in appstate.request}")
        
        print("Testing city.graph (mock)...")
        appstate = _mock_city_graph(appstate)
        print(f"  City graph added: {'geocost' in appstate.request}")
        
        print("Testing opt.greedy (mock)...")
        appstate = _mock_optimize(appstate)
        print(f"  Itinerary added: {'itinerary' in appstate.request}")
        
        print("Testing trip.maker (mock)...")
        appstate = _mock_trip_maker(appstate)
        print(f"  Trip cards added: {'cards' in appstate.request.get('itinerary', {})}")
        
        # Show final result
        print(f"\nFinal AppState request keys: {list(appstate.request.keys())}")
        if 'itinerary' in appstate.request:
            itinerary = appstate.request['itinerary']
            if 'days' in itinerary:
                print(f"  Itinerary days: {len(itinerary['days'])}")
                for day in itinerary['days']:
                    print(f"    Day {day.get('day', '?')}: {day.get('city', 'Unknown')} - {day.get('plan', [])}")
            if 'cards' in itinerary:
                print(f"  Trip cards: {len(itinerary['cards'])}")
                for card in itinerary['cards']:
                    print(f"    {card.get('title', 'Untitled')}: {len(card.get('items', []))} items")
        
        print(f"\nAppState logs:")
        for log in appstate.logs:
            print(f"  {log}")
        
    except Exception as e:
        print(f"Error testing final tools: {e}")
        import traceback
        traceback.print_exc()


def test_trip_interpreter_workflow(state_snapshot: dict, user_message: str = None) -> None:
    """Test the complete trip interpreter workflow"""
    print("\n" + "=" * 60)
    print("TESTING COMPLETE TRIP INTERPRETER WORKFLOW")
    print("=" * 60)
    
    # Step 1: Test trip interpreter
    interpreter_result = test_trip_interpreter_direct(state_snapshot, user_message)
    
    if not interpreter_result.get("tool_plan"):
        print("Skipping workflow test - no tools planned")
        return
    
    # Step 2: Build AppState
    appstate = test_appstate_builder(state_snapshot)
    
    if appstate is None:
        print("Skipping workflow test - AppState creation failed")
        return
    
    # Step 3: Test final tools
    test_final_tools_mock(appstate)
    
    print(f"\n✓ Complete workflow test finished!")


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


def main():
    parser = argparse.ArgumentParser(description="Test trip interpreter only (bypassing discovery phase)")
    parser.add_argument("--mock-file", help="Path to mock data JSON file")
    parser.add_argument("--scenario", choices=list(create_scenario_configs().keys()), 
                       help="Generate and test a specific scenario")
    parser.add_argument("--test-interpreter", action="store_true", 
                       help="Test the trip interpreter function only")
    parser.add_argument("--test-appstate", action="store_true", 
                       help="Test the AppState builder only")
    parser.add_argument("--test-final-tools", action="store_true", 
                       help="Test the final tools (mock) only")
    parser.add_argument("--test-workflow", action="store_true", 
                       help="Test the complete workflow")
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
    
    if args.test_interpreter or not any([args.test_appstate, args.test_final_tools, args.test_workflow]):
        result = test_trip_interpreter_direct(state_snapshot, args.user_message)
        if not result.get("tool_plan"):
            success = False
    
    if args.test_appstate or not any([args.test_interpreter, args.test_final_tools, args.test_workflow]):
        appstate = test_appstate_builder(state_snapshot)
        if appstate is None:
            success = False
    
    if args.test_final_tools or not any([args.test_interpreter, args.test_appstate, args.test_workflow]):
        appstate = test_appstate_builder(state_snapshot)
        if appstate is not None:
            test_final_tools_mock(appstate)
        else:
            success = False
    
    if args.test_workflow or not any([args.test_interpreter, args.test_appstate, args.test_final_tools]):
        test_trip_interpreter_workflow(state_snapshot, args.user_message)
    
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
