#!/usr/bin/env python3
"""
Direct Test of Final Tools (Trip Interpreter + Final Tools)

This script directly tests the final tools without going through the build graph.
It creates the necessary AppState and tests each final tool individually.

Usage:
    python test_final_tools_direct.py --scenario europe_trip
    python test_final_tools_direct.py --mock-file mock_data.json --test-all
"""

import json
import argparse
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mock_data_generator import MockDataGenerator, create_scenario_configs
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan, build_appstate_from_travel_state


def test_trip_interpreter_direct(mock_data: Dict[str, Any], user_message: str = None) -> Dict[str, Any]:
    """Test the trip interpreter function directly"""
    print("=" * 60)
    print("TESTING TRIP INTERPRETER (DIRECT)")
    print("=" * 60)
    
    if user_message is None:
        user_message = mock_data.get("user_message", "Plan my trip")
    
    print(f"User message: {user_message}")
    print(f"Available cities: {mock_data.get('cities', [])}")
    print(f"Target currency: {mock_data.get('fx_meta', {}).get('target', 'Unknown')}")
    
    try:
        result = interpret_trip_plan(user_message, mock_data)
        print(f"✓ Trip interpreter executed successfully!")
        print(f"  Tool plan: {result.get('tool_plan', [])}")
        print(f"  Notes: {result.get('notes', '')}")
        return result
    except Exception as e:
        print(f"✗ Error in trip interpreter: {e}")
        import traceback
        traceback.print_exc()
        return {"tool_plan": [], "notes": f"Error: {e}"}


def test_appstate_builder(mock_data: Dict[str, Any]) -> Any:
    """Test the AppState builder"""
    print("\n" + "=" * 60)
    print("TESTING APPSTATE BUILDER")
    print("=" * 60)
    
    try:
        appstate = build_appstate_from_travel_state(mock_data)
        print(f"✓ AppState created successfully!")
        print(f"  Request keys: {list(appstate.request.keys())}")
        print(f"  Logs: {len(appstate.logs)} entries")
        
        # Show discovery data
        discovery = appstate.request.get("discovery", {})
        if "cities" in discovery:
            print(f"  Discovery cities: {list(discovery['cities'].keys())}")
            for city, data in discovery["cities"].items():
                poi_count = len(data.get("pois", []))
                rest_count = len(data.get("restaurants", []))
                print(f"    {city}: {poi_count} POIs, {rest_count} restaurants")
        
        # Show preferences
        preferences = appstate.request.get("preferences", {})
        print(f"  Preferences: {preferences}")
        
        return appstate
    except Exception as e:
        print(f"✗ Error building AppState: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_final_tool_direct(tool_name: str, appstate: Any) -> Any:
    """Test a final tool directly with AppState"""
    print(f"\n" + "=" * 60)
    print(f"TESTING {tool_name.upper()} (DIRECT)")
    print("=" * 60)
    
    try:
        # Import the tool functions
        from app.graph.build_graph import (
            _mock_discovery_costs, _mock_city_graph, 
            _mock_optimize, _mock_trip_maker
        )
        
        tool_functions = {
            "discovery.costs": _mock_discovery_costs,
            "city.graph": _mock_city_graph,
            "opt.greedy": _mock_optimize,
            "trip.maker": _mock_trip_maker
        }
        
        if tool_name not in tool_functions:
            print(f"✗ Unknown tool: {tool_name}")
            return None
        
        # Run the tool
        result_appstate = tool_functions[tool_name](appstate)
        
        print(f"✓ {tool_name} executed successfully!")
        
        # Show what was added/modified
        if tool_name == "discovery.costs":
            discovery = result_appstate.request.get("discovery", {})
            if discovery:
                print(f"  Discovery data: {len(discovery.get('cities', {}))} cities")
        elif tool_name == "city.graph":
            geocost = result_appstate.request.get("geocost", {})
            if geocost:
                print(f"  Geo cost data: {len(geocost)} cities")
        elif tool_name == "opt.greedy":
            itinerary = result_appstate.request.get("itinerary", {})
            if itinerary:
                days = itinerary.get("days", [])
                print(f"  Itinerary: {len(days)} days planned")
                for day in days[:3]:  # Show first 3 days
                    print(f"    Day {day.get('day', '?')}: {day.get('city', '?')} - {day.get('plan', [])}")
        elif tool_name == "trip.maker":
            itinerary = result_appstate.request.get("itinerary", {})
            if itinerary:
                cards = itinerary.get("cards", [])
                print(f"  Trip cards: {len(cards)} cards created")
                for card in cards[:2]:  # Show first 2 cards
                    print(f"    {card.get('title', '?')}: {card.get('items', [])}")
        
        # Show logs
        new_logs = [log for log in result_appstate.logs if f'[{tool_name}]' in log]
        if new_logs:
            print(f"  New logs: {len(new_logs)} entries")
            for log in new_logs:
                print(f"    {log}")
        
        return result_appstate
        
    except Exception as e:
        print(f"✗ Error in {tool_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_complete_final_workflow(mock_data: Dict[str, Any], user_message: str = None) -> bool:
    """Test the complete final workflow"""
    print("\n" + "=" * 60)
    print("TESTING COMPLETE FINAL WORKFLOW")
    print("=" * 60)
    
    # Step 1: Trip Interpreter
    print("\n1. Running Trip Interpreter...")
    interpreter_result = test_trip_interpreter_direct(mock_data, user_message)
    if not interpreter_result.get("tool_plan"):
        print("✗ No tool plan generated!")
        return False
    
    tool_plan = interpreter_result["tool_plan"]
    print(f"  Tool plan: {tool_plan}")
    
    # Step 2: Build AppState
    print("\n2. Building AppState...")
    appstate = test_appstate_builder(mock_data)
    if not appstate:
        print("✗ Failed to build AppState!")
        return False
    
    # Step 3: Execute each tool in the plan
    print(f"\n3. Executing {len(tool_plan)} tools...")
    current_appstate = appstate
    
    for i, tool in enumerate(tool_plan):
        print(f"\n--- Tool {i+1}/{len(tool_plan)}: {tool} ---")
        result_appstate = test_final_tool_direct(tool, current_appstate)
        if not result_appstate:
            print(f"✗ Tool {tool} failed!")
            return False
        current_appstate = result_appstate
    
    # Step 4: Final result summary
    print(f"\n4. Final Result Summary:")
    print(f"  Tools executed: {tool_plan}")
    print(f"  Final AppState logs: {len(current_appstate.logs)} entries")
    
    # Show final itinerary if available
    itinerary = current_appstate.request.get("itinerary", {})
    if itinerary:
        print(f"  Itinerary created: ✓")
        if "days" in itinerary:
            print(f"    Days: {len(itinerary['days'])}")
        if "cards" in itinerary:
            print(f"    Cards: {len(itinerary['cards'])}")
    else:
        print(f"  Itinerary created: ✗")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Direct test of final tools")
    parser.add_argument("--mock-file", help="Path to mock data JSON file")
    parser.add_argument("--scenario", choices=list(create_scenario_configs().keys()), 
                       help="Generate and test a specific scenario")
    parser.add_argument("--test-interpreter", action="store_true", 
                       help="Test only the trip interpreter")
    parser.add_argument("--test-appstate", action="store_true", 
                       help="Test only the AppState builder")
    parser.add_argument("--test-tool", choices=["discovery.costs", "city.graph", "opt.greedy", "trip.maker"],
                       help="Test a specific final tool")
    parser.add_argument("--test-all", action="store_true", 
                       help="Test all final tools")
    parser.add_argument("--test-workflow", action="store_true", 
                       help="Test the complete final workflow")
    parser.add_argument("--user-message", help="Custom user message for testing")
    
    args = parser.parse_args()
    
    # Load or generate mock data
    if args.scenario:
        print(f"Generating mock data for scenario: {args.scenario}")
        config = create_scenario_configs()[args.scenario]
        generator = MockDataGenerator(config)
        mock_data = generator.generate_complete_state_snapshot()
    elif args.mock_file:
        print(f"Loading mock data from: {args.mock_file}")
        with open(args.mock_file, 'r', encoding='utf-8') as f:
            mock_data = json.load(f)
    else:
        print("Error: Must specify either --mock-file or --scenario")
        return 1
    
    print(f"Mock data loaded: {len(mock_data.get('cities', []))} cities")
    
    # Run tests based on arguments
    success = True
    
    if args.test_interpreter or not any([args.test_appstate, args.test_tool, args.test_all, args.test_workflow]):
        result = test_trip_interpreter_direct(mock_data, args.user_message)
        if not result.get("tool_plan"):
            success = False
    
    if args.test_appstate or args.test_workflow:
        appstate = test_appstate_builder(mock_data)
        if not appstate:
            success = False
    
    if args.test_tool:
        appstate = test_appstate_builder(mock_data)
        if appstate:
            result = test_final_tool_direct(args.test_tool, appstate)
            if not result:
                success = False
        else:
            success = False
    
    if args.test_all:
        appstate = test_appstate_builder(mock_data)
        if appstate:
            tools = ["discovery.costs", "city.graph", "opt.greedy", "trip.maker"]
            current_appstate = appstate
            for tool in tools:
                result = test_final_tool_direct(tool, current_appstate)
                if not result:
                    success = False
                    break
                current_appstate = result
        else:
            success = False
    
    if args.test_workflow:
        if not test_complete_final_workflow(mock_data, args.user_message):
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
