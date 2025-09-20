#!/usr/bin/env python3
"""
Test Script for Final Phase of Trip Planner (Trip Interpreter + Final Tools)

This script tests only the final phase of the build graph:
- Trip Interpreter
- Trip Router  
- Final Tools (discovery.costs, city.graph, opt.greedy, trip.maker)

It bypasses all the discovery nodes and starts directly with the trip interpreter phase.

Usage:
    python test_final_phase.py --scenario europe_trip
    python test_final_phase.py --mock-file mock_data.json --test-all-tools
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


def create_final_phase_state(mock_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a TravelState that starts at the final phase (trip interpreter)"""
    
    # Create the base state with all discovery data already populated
    travel_state = {
        "user_message": mock_data.get("user_message", "Plan my trip"),
        "interp": mock_data.get("interp", {}),
        "cities": mock_data.get("cities", []),
        "city_country_map": mock_data.get("city_country_map", {}),
        "fx_meta": mock_data.get("fx_meta", {}),
        "poi": mock_data.get("poi", {}),
        "restaurants": mock_data.get("restaurants", {}),
        "city_fares": mock_data.get("city_fares", {}),
        "intercity": mock_data.get("intercity", {}),
        "logs": mock_data.get("logs", []),
        "errors": mock_data.get("errors", []),
        
        # Discovery phase is complete
        "plan_queue": [],
        "done_tools": ["cities.recommender", "poi.discovery", "restaurants.discovery", "fares.city", "fares.intercity"],
        "last_tool": "fares.intercity",
        
        # Final phase state (empty initially)
        "trip_plan_queue": [],
        "trip_done_tools": [],
        "trip_appstate": None,
        "itinerary": {},
        "final_discovery": {},
        "final_geocost": {}
    }
    
    return travel_state


def test_trip_interpreter_node(travel_state: Dict[str, Any]) -> Dict[str, Any]:
    """Test the trip interpreter node"""
    print("=" * 60)
    print("TESTING TRIP INTERPRETER NODE")
    print("=" * 60)
    
    try:
        from app.graph.build_graph import node_trip_interpret
        
        # Run the trip interpreter node
        result_state = node_trip_interpret(travel_state)
        
        print(f"✓ Trip interpreter node executed successfully!")
        print(f"  Trip plan queue: {result_state.get('trip_plan_queue', [])}")
        print(f"  Trip AppState created: {'trip_appstate' in result_state}")
        print(f"  Logs added: {len([log for log in result_state.get('logs', []) if '[trip.interpret]' in log])}")
        
        if 'trip_appstate' in result_state:
            appstate = result_state['trip_appstate']
            print(f"  AppState request keys: {list(appstate.request.keys())}")
            
            # Show discovery data in AppState
            discovery = appstate.request.get("discovery", {})
            if "cities" in discovery:
                print(f"  Discovery cities: {list(discovery['cities'].keys())}")
                for city, data in discovery["cities"].items():
                    poi_count = len(data.get("pois", []))
                    rest_count = len(data.get("restaurants", []))
                    print(f"    {city}: {poi_count} POIs, {rest_count} restaurants")
        
        return result_state
        
    except Exception as e:
        print(f"✗ Error in trip interpreter node: {e}")
        import traceback
        traceback.print_exc()
        return travel_state


def test_trip_router(travel_state: Dict[str, Any]) -> str:
    """Test the trip router"""
    print("\n" + "=" * 60)
    print("TESTING TRIP ROUTER")
    print("=" * 60)
    
    try:
        from app.graph.build_graph import trip_router
        
        # Test the router
        next_tool = trip_router(travel_state)
        
        print(f"✓ Trip router executed successfully!")
        print(f"  Next tool: {next_tool}")
        print(f"  Trip plan queue: {travel_state.get('trip_plan_queue', [])}")
        print(f"  Trip done tools: {travel_state.get('trip_done_tools', [])}")
        
        return next_tool
        
    except Exception as e:
        print(f"✗ Error in trip router: {e}")
        import traceback
        traceback.print_exc()
        return "END"


def test_final_tools(travel_state: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    """Test individual final tools"""
    print(f"\n" + "=" * 60)
    print(f"TESTING {tool_name.upper()}")
    print("=" * 60)
    
    try:
        # Import the specific tool node
        from app.graph.build_graph import (
            node_discovery_costs, node_city_graph, 
            node_opt_greedy, node_trip_maker
        )
        
        tool_nodes = {
            "discovery.costs": node_discovery_costs,
            "city.graph": node_city_graph,
            "opt.greedy": node_opt_greedy,
            "trip.maker": node_trip_maker
        }
        
        if tool_name not in tool_nodes:
            print(f"✗ Unknown tool: {tool_name}")
            return travel_state
        
        # Run the tool
        result_state = tool_nodes[tool_name](travel_state)
        
        print(f"✓ {tool_name} executed successfully!")
        
        # Show detailed output for each tool
        if tool_name == "discovery.costs":
            if "final_discovery" in result_state:
                discovery = result_state["final_discovery"]
                print(f"  Final discovery data added:")
                if "cities" in discovery:
                    for city, data in discovery["cities"].items():
                        poi_count = len(data.get("pois", []))
                        rest_count = len(data.get("restaurants", []))
                        print(f"    {city}: {poi_count} POIs, {rest_count} restaurants")
                        # Show sample POIs
                        if data.get("pois"):
                            sample_pois = data["pois"][:3]
                            print(f"      Sample POIs: {[p.get('name', '?') for p in sample_pois]}")
                        # Show sample restaurants
                        if data.get("restaurants"):
                            sample_rests = data["restaurants"][:3]
                            print(f"      Sample restaurants: {[r.get('name', '?') for r in sample_rests]}")
        
        elif tool_name == "city.graph":
            if "final_geocost" in result_state:
                geocost = result_state["final_geocost"]
                print(f"  Geo cost data added:")
                for city, data in geocost.items():
                    nodes = data.get("nodes", [])
                    edges = data.get("edges", [])
                    print(f"    {city}: {len(nodes)} nodes, {len(edges)} edges")
                    if nodes:
                        print(f"      Sample nodes: {nodes[:5]}")
        
        elif tool_name == "opt.greedy":
            if "itinerary" in result_state:
                itinerary = result_state["itinerary"]
                days = itinerary.get("days", [])
                print(f"  Itinerary created with {len(days)} days:")
                for day in days:
                    print(f"    Day {day.get('day', '?')}: {day.get('city', '?')}")
                    plan = day.get("plan", [])
                    if plan:
                        print(f"      Plan: {plan}")
        
        elif tool_name == "trip.maker":
            if "itinerary" in result_state:
                itinerary = result_state["itinerary"]
                cards = itinerary.get("cards", [])
                print(f"  Trip cards created: {len(cards)} cards")
                for card in cards:
                    title = card.get("title", "Untitled")
                    items = card.get("items", [])
                    print(f"    {title}: {items}")
        
        # Show AppState request data if available
        if "trip_appstate" in result_state:
            appstate = result_state["trip_appstate"]
            request = appstate.request
            print(f"  AppState request updated:")
            print(f"    Keys: {list(request.keys())}")
            
            # Show specific data based on tool
            if tool_name == "discovery.costs" and "discovery" in request:
                discovery = request["discovery"]
                print(f"    Discovery cities: {list(discovery.get('cities', {}).keys())}")
            
            elif tool_name == "city.graph" and "geocost" in request:
                geocost = request["geocost"]
                print(f"    Geo cost cities: {list(geocost.keys())}")
            
            elif tool_name == "opt.greedy" and "itinerary" in request:
                itinerary = request["itinerary"]
                days = itinerary.get("days", [])
                print(f"    Itinerary days: {len(days)}")
            
            elif tool_name == "trip.maker" and "itinerary" in request:
                itinerary = request["itinerary"]
                cards = itinerary.get("cards", [])
                print(f"    Trip cards: {len(cards)}")
        
        # Show updated logs
        new_logs = [log for log in result_state.get('logs', []) if f'[{tool_name}]' in log]
        if new_logs:
            print(f"  New logs: {len(new_logs)} entries")
            for log in new_logs:
                print(f"    {log}")
        
        return result_state
        
    except Exception as e:
        print(f"✗ Error in {tool_name}: {e}")
        import traceback
        traceback.print_exc()
        return travel_state


def test_complete_final_phase(travel_state: Dict[str, Any]) -> Dict[str, Any]:
    """Test the complete final phase workflow"""
    print("\n" + "=" * 60)
    print("TESTING COMPLETE FINAL PHASE WORKFLOW")
    print("=" * 60)
    
    current_state = travel_state.copy()
    
    # Step 1: Trip Interpreter
    print("\n1. Running Trip Interpreter...")
    current_state = test_trip_interpreter_node(current_state)
    
    if not current_state.get('trip_plan_queue'):
        print("✗ No trip plan queue generated!")
        return current_state
    
    # Step 2: Execute all tools in the plan
    plan_queue = current_state.get('trip_plan_queue', [])
    print(f"\n2. Executing {len(plan_queue)} tools in plan: {plan_queue}")
    
    for i, tool in enumerate(plan_queue):
        print(f"\n--- Tool {i+1}/{len(plan_queue)}: {tool} ---")
        
        # Test the router first
        next_tool = test_trip_router(current_state)
        if next_tool != tool:
            print(f"⚠️  Router returned {next_tool}, expected {tool}")
        
        # Execute the tool
        current_state = test_final_tools(current_state, tool)
        
        # Update the queue (simulate what the router would do)
        if current_state.get('trip_plan_queue') and current_state['trip_plan_queue'][0] == tool:
            current_state['trip_plan_queue'] = current_state['trip_plan_queue'][1:]
        current_state.setdefault('trip_done_tools', []).append(tool)
    
    # Step 3: Final state summary
    print(f"\n3. Final State Summary:")
    print(f"  Trip done tools: {current_state.get('trip_done_tools', [])}")
    print(f"  Remaining queue: {current_state.get('trip_plan_queue', [])}")
    print(f"  Itinerary created: {'itinerary' in current_state and current_state['itinerary']}")
    print(f"  Final discovery: {'final_discovery' in current_state and current_state['final_discovery']}")
    print(f"  Final geocost: {'final_geocost' in current_state and current_state['final_geocost']}")
    
    # Step 4: Print complete final output
    print_final_output(current_state)
    
    return current_state


def print_final_output(travel_state: Dict[str, Any]) -> None:
    """Print the complete final output from all tools"""
    print(f"\n" + "=" * 60)
    print("COMPLETE FINAL OUTPUT")
    print("=" * 60)
    
    # Print final discovery data
    if "final_discovery" in travel_state and travel_state["final_discovery"]:
        discovery = travel_state["final_discovery"]
        print(f"\n📋 FINAL DISCOVERY DATA:")
        if "cities" in discovery:
            for city, data in discovery["cities"].items():
                print(f"  {city}:")
                pois = data.get("pois", [])
                restaurants = data.get("restaurants", [])
                print(f"    POIs ({len(pois)}): {[p.get('name', '?') for p in pois]}")
                print(f"    Restaurants ({len(restaurants)}): {[r.get('name', '?') for r in restaurants]}")
    
    # Print final geocost data
    if "final_geocost" in travel_state and travel_state["final_geocost"]:
        geocost = travel_state["final_geocost"]
        print(f"\n🗺️  FINAL GEOCOST DATA:")
        for city, data in geocost.items():
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            print(f"  {city}: {len(nodes)} nodes, {len(edges)} edges")
            if nodes:
                print(f"    Nodes: {nodes}")
    
    # Print final itinerary
    if "itinerary" in travel_state and travel_state["itinerary"]:
        itinerary = travel_state["itinerary"]
        print(f"\n📅 FINAL ITINERARY:")
        
        # Show days
        days = itinerary.get("days", [])
        if days:
            print(f"  Days ({len(days)}):")
            for day in days:
                print(f"    Day {day.get('day', '?')} in {day.get('city', '?')}: {day.get('plan', [])}")
        
        # Show cards
        cards = itinerary.get("cards", [])
        if cards:
            print(f"  Trip Cards ({len(cards)}):")
            for card in cards:
                print(f"    {card.get('title', 'Untitled')}: {card.get('items', [])}")
    
    # Print AppState request data
    if "trip_appstate" in travel_state and travel_state["trip_appstate"]:
        appstate = travel_state["trip_appstate"]
        request = appstate.request
        print(f"\n🔧 APPSTATE REQUEST DATA:")
        print(f"  Keys: {list(request.keys())}")
        
        # Show discovery in AppState
        if "discovery" in request:
            discovery = request["discovery"]
            if "cities" in discovery:
                print(f"  Discovery cities: {list(discovery['cities'].keys())}")
        
        # Show geocost in AppState
        if "geocost" in request:
            geocost = request["geocost"]
            print(f"  Geo cost cities: {list(geocost.keys())}")
        
        # Show itinerary in AppState
        if "itinerary" in request:
            itinerary = request["itinerary"]
            days = itinerary.get("days", [])
            cards = itinerary.get("cards", [])
            print(f"  Itinerary: {len(days)} days, {len(cards)} cards")
    
    # Print all logs
    logs = travel_state.get("logs", [])
    if logs:
        print(f"\n📝 ALL LOGS ({len(logs)} entries):")
        for log in logs:
            print(f"  {log}")
    
    print(f"\n" + "=" * 60)


def test_individual_trip_interpreter(mock_data: Dict[str, Any], user_message: str = None) -> Dict[str, Any]:
    """Test just the trip interpreter function (not the node)"""
    print("=" * 60)
    print("TESTING TRIP INTERPRETER FUNCTION")
    print("=" * 60)
    
    if user_message is None:
        user_message = mock_data.get("user_message", "Plan my trip")
    
    print(f"User message: {user_message}")
    print(f"Available cities: {mock_data.get('cities', [])}")
    print(f"Target currency: {mock_data.get('fx_meta', {}).get('target', 'Unknown')}")
    
    try:
        result = interpret_trip_plan(user_message, mock_data)
        print(f"✓ Trip interpreter function executed successfully!")
        print(f"  Tool plan: {result.get('tool_plan', [])}")
        print(f"  Notes: {result.get('notes', '')}")
        return result
    except Exception as e:
        print(f"✗ Error in trip interpreter function: {e}")
        import traceback
        traceback.print_exc()
        return {"tool_plan": [], "notes": f"Error: {e}"}


def main():
    parser = argparse.ArgumentParser(description="Test final phase of trip planner")
    parser.add_argument("--mock-file", help="Path to mock data JSON file")
    parser.add_argument("--scenario", choices=list(create_scenario_configs().keys()), 
                       help="Generate and test a specific scenario")
    parser.add_argument("--test-interpreter", action="store_true", 
                       help="Test only the trip interpreter function")
    parser.add_argument("--test-interpreter-node", action="store_true", 
                       help="Test the trip interpreter node")
    parser.add_argument("--test-router", action="store_true", 
                       help="Test the trip router")
    parser.add_argument("--test-tool", choices=["discovery.costs", "city.graph", "opt.greedy", "trip.maker"],
                       help="Test a specific final tool")
    parser.add_argument("--test-all-tools", action="store_true", 
                       help="Test all final tools")
    parser.add_argument("--test-complete-workflow", action="store_true", 
                       help="Test the complete final phase workflow")
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
    
    if args.test_interpreter or not any([args.test_interpreter_node, args.test_router, args.test_tool, args.test_all_tools, args.test_complete_workflow]):
        result = test_individual_trip_interpreter(mock_data, args.user_message)
        if not result.get("tool_plan"):
            success = False
    
    if args.test_interpreter_node or args.test_complete_workflow:
        travel_state = create_final_phase_state(mock_data)
        result_state = test_trip_interpreter_node(travel_state)
        if not result_state.get('trip_plan_queue'):
            success = False
    
    if args.test_router or args.test_complete_workflow:
        travel_state = create_final_phase_state(mock_data)
        # First run interpreter to populate the plan queue
        travel_state = test_trip_interpreter_node(travel_state)
        next_tool = test_trip_router(travel_state)
        if next_tool == "END":
            success = False
    
    if args.test_tool:
        travel_state = create_final_phase_state(mock_data)
        # First run interpreter to populate the plan queue
        travel_state = test_trip_interpreter_node(travel_state)
        # Manually set the tool in the queue
        travel_state['trip_plan_queue'] = [args.test_tool]
        result_state = test_final_tools(travel_state, args.test_tool)
        if not result_state:
            success = False
        else:
            # Print detailed output for the single tool
            print_final_output(result_state)
    
    if args.test_all_tools:
        travel_state = create_final_phase_state(mock_data)
        tools = ["discovery.costs", "city.graph", "opt.greedy", "trip.maker"]
        for tool in tools:
            travel_state['trip_plan_queue'] = [tool]
            result_state = test_final_tools(travel_state, tool)
            if not result_state:
                success = False
        # Print final output after all tools
        print_final_output(travel_state)
    
    if args.test_complete_workflow:
        travel_state = create_final_phase_state(mock_data)
        result_state = test_complete_final_phase(travel_state)
        if not result_state.get('trip_done_tools'):
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
