#!/usr/bin/env python3
"""
Example Usage of Mock Data Generator for Trip Planner Testing

This script demonstrates how to use the mock data generator to test
the trip interpreter and build graph functionality.
"""

import json
import sys
from pathlib import Path

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from mock_data_generator import MockDataGenerator, create_scenario_configs
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan, build_appstate_from_travel_state


def example_basic_usage():
    """Basic example of generating and using mock data"""
    print("=" * 60)
    print("BASIC USAGE EXAMPLE")
    print("=" * 60)
    
    # Create a simple configuration
    config = MockDataGenerator.MockConfig(
        cities=["Rome", "Florence"],
        countries=["Italy"],
        target_currency="EUR",
        travelers={"adults": 2, "children": 0},
        musts=["Colosseum", "Uffizi Gallery"]
    )
    
    # Generate mock data
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    print(f"Generated mock data for: {', '.join(config.cities)}")
    print(f"Cities: {state_snapshot['cities']}")
    print(f"POI count: {sum(len(city_data['pois']) for city_data in state_snapshot['poi']['poi_by_city'].values())}")
    
    # Test the trip interpreter
    result = interpret_trip_plan("Plan my Italian vacation", state_snapshot)
    print(f"Trip interpreter result: {result}")
    
    return state_snapshot


def example_scenario_usage():
    """Example using predefined scenarios"""
    print("\n" + "=" * 60)
    print("SCENARIO USAGE EXAMPLE")
    print("=" * 60)
    
    # Get available scenarios
    scenarios = create_scenario_configs()
    print(f"Available scenarios: {list(scenarios.keys())}")
    
    # Use the Asia trip scenario
    config = scenarios["asia_trip"]
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    print(f"Asia trip scenario:")
    print(f"  Cities: {config.cities}")
    print(f"  Countries: {config.countries}")
    print(f"  Travelers: {config.travelers}")
    print(f"  Budget: {config.budget_caps}")
    
    # Test with different user messages
    user_messages = [
        "Plan my Japan trip with family",
        "I want to see temples and eat great food",
        "Budget-conscious travel through Japan"
    ]
    
    for msg in user_messages:
        result = interpret_trip_plan(msg, state_snapshot)
        print(f"  '{msg}' -> {result['tool_plan']}")


def example_appstate_usage():
    """Example of building AppState from mock data"""
    print("\n" + "=" * 60)
    print("APPSTATE USAGE EXAMPLE")
    print("=" * 60)
    
    # Use luxury trip scenario
    config = create_scenario_configs()["luxury_trip"]
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    # Build AppState
    appstate = build_appstate_from_travel_state(state_snapshot)
    
    print(f"AppState created for luxury trip:")
    print(f"  Request keys: {list(appstate.request.keys())}")
    
    # Show discovery data structure
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


def example_custom_scenario():
    """Example of creating a custom scenario"""
    print("\n" + "=" * 60)
    print("CUSTOM SCENARIO EXAMPLE")
    print("=" * 60)
    
    # Create a custom configuration
    config = MockDataGenerator.MockConfig(
        cities=["Barcelona", "Madrid", "Seville"],
        countries=["Spain"],
        target_currency="EUR",
        travelers={"adults": 1, "children": 0},
        musts=["Sagrada Familia", "Prado Museum", "Alcazar"],
        preferences={
            "pace": "slow",
            "mobility": ["walk", "transit"],
            "time_vs_money": 0.3,
            "safety_buffer_min": 30,
            "day_pass_allowed": True,
            "overnight_ok": True,
            "one_way_rental_ok": False,
            "rail_pass_consider": True
        },
        budget_caps={"total": 1200, "per_day": 150}
    )
    
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    print(f"Custom Spain trip:")
    print(f"  Cities: {config.cities}")
    print(f"  Budget: €{config.budget_caps['total']} total, €{config.budget_caps['per_day']}/day")
    print(f"  Pace: {config.preferences['pace']}")
    
    # Test the interpreter
    result = interpret_trip_plan("Solo backpacking through Spain", state_snapshot)
    print(f"  Interpreter result: {result['tool_plan']}")


def example_save_and_load():
    """Example of saving and loading mock data"""
    print("\n" + "=" * 60)
    print("SAVE AND LOAD EXAMPLE")
    print("=" * 60)
    
    # Generate mock data
    config = create_scenario_configs()["multi_country"]
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    # Save to file
    output_file = "example_mock_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(state_snapshot, f, indent=2, ensure_ascii=False)
    
    print(f"Mock data saved to: {output_file}")
    
    # Load from file
    with open(output_file, 'w', encoding='utf-8') as f:
        loaded_data = json.load(f)
    
    print(f"Mock data loaded from: {output_file}")
    print(f"Loaded cities: {loaded_data['cities']}")
    
    # Test with loaded data
    result = interpret_trip_plan("Multi-country European tour", loaded_data)
    print(f"Interpreter result with loaded data: {result['tool_plan']}")


def main():
    """Run all examples"""
    print("Trip Planner Mock Data Generator - Usage Examples")
    print("=" * 60)
    
    try:
        # Run examples
        example_basic_usage()
        example_scenario_usage()
        example_appstate_usage()
        example_custom_scenario()
        example_save_and_load()
        
        print("\n" + "=" * 60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY! ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
