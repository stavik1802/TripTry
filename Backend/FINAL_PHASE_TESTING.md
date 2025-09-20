# Final Phase Testing Guide

This guide explains how to test the final phase of the trip planner (trip interpreter + final tools) without running the full discovery pipeline.

## Quick Start

### 1. Generate Mock Data
```bash
# Generate mock data for a scenario
python mock_data_generator.py --scenario europe_trip --output mock_data.json

# Or use a custom scenario
python mock_data_generator.py --scenario custom --cities "Tokyo" "Kyoto" --countries "Japan" --currency USD
```

### 2. Test Final Phase Directly (Recommended)
```bash
# Test the complete final workflow
python test_final_tools_direct.py --scenario europe_trip --test-workflow

# Test individual components
python test_final_tools_direct.py --scenario asia_trip --test-interpreter
python test_final_tools_direct.py --scenario budget_trip --test-tool discovery.costs
python test_final_tools_direct.py --scenario luxury_trip --test-all
```

### 3. Test Final Phase with Build Graph
```bash
# Test the complete final phase workflow
python test_final_phase.py --scenario europe_trip --test-complete-workflow

# Test individual components
python test_final_phase.py --scenario asia_trip --test-interpreter-node
python test_final_phase.py --scenario budget_trip --test-router
python test_final_phase.py --scenario luxury_trip --test-tool opt.greedy
```

## What Each Script Does

### `test_final_tools_direct.py` (Recommended)
- **Purpose**: Direct testing of final tools without build graph overhead
- **Use when**: You want to test the core functionality quickly
- **Tests**: Trip interpreter function, AppState builder, individual final tools, complete workflow

### `test_final_phase.py`
- **Purpose**: Testing final phase through the build graph structure
- **Use when**: You want to test the actual graph nodes and routing
- **Tests**: Trip interpreter node, trip router, final tool nodes, complete workflow

### `mock_data_generator.py`
- **Purpose**: Generate realistic mock data for testing
- **Scenarios**: europe_trip, asia_trip, budget_trip, luxury_trip, multi_country
- **Output**: Complete state snapshot with all discovery data

## Testing Scenarios

### Available Scenarios
- **europe_trip**: Rome, Florence, Venice (Italy) - Cultural tour
- **asia_trip**: Tokyo, Kyoto, Osaka (Japan) - Family trip
- **budget_trip**: Prague, Budapest, Krakow - Backpacking
- **luxury_trip**: Paris, Nice, Monaco - High-end travel
- **multi_country**: Amsterdam, Brussels, Paris, London - Multi-country

### Custom Scenarios
```bash
python mock_data_generator.py --scenario custom \
  --cities "Barcelona" "Madrid" "Seville" \
  --countries "Spain" \
  --currency EUR \
  --adults 2 \
  --budget 2000
```

## What Gets Tested

### Trip Interpreter
- Analyzes mock data and user message
- Determines which final tools to run
- Returns tool plan and notes

### AppState Builder
- Converts TravelState to AppState format
- Structures discovery data for final tools
- Sets up preferences and metadata

### Final Tools
1. **discovery.costs**: Aggregates POIs/restaurants with cost estimates
2. **city.graph**: Builds activity graphs per city
3. **opt.greedy**: Optimizes itinerary with day assignments
4. **trip.maker**: Creates final day-by-day itinerary cards

## Example Output

### Trip Interpreter Result
```json
{
  "tool_plan": ["discovery.costs", "city.graph", "opt.greedy", "trip.maker"],
  "notes": "Full planning workflow for multi-city trip"
}
```

### Final Itinerary
```json
{
  "days": [
    {
      "day": 1,
      "city": "Rome",
      "plan": ["Museum AM", "Lunch", "Park PM", "Dinner"]
    }
  ],
  "cards": [
    {
      "title": "Day 1 in Rome",
      "items": ["Museum AM", "Lunch", "Park PM", "Dinner"]
    }
  ]
}
```

## Troubleshooting

### Common Issues
1. **Import Errors**: Make sure you're in the Backend directory
2. **Missing Dependencies**: Install required packages
3. **Mock Data Issues**: Regenerate mock data if structure seems wrong

### Debug Mode
```bash
# Enable mock mode for all tools
export TP_MOCK_TOOLS=1
export TP_MOCK_FINAL=1

# Run tests
python test_final_tools_direct.py --scenario europe_trip --test-workflow
```

### Verbose Output
The test scripts provide detailed output showing:
- What each tool does
- What data gets added/modified
- Success/failure status
- Log entries

## Integration with Your Code

### Using Mock Data in Your Tests
```python
from mock_data_generator import MockDataGenerator, create_scenario_configs
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan

# Generate mock data
config = create_scenario_configs()["europe_trip"]
generator = MockDataGenerator(config)
mock_data = generator.generate_complete_state_snapshot()

# Test trip interpreter
result = interpret_trip_plan("Plan my Italian vacation", mock_data)
print(f"Tool plan: {result['tool_plan']}")
```

### Testing Individual Tools
```python
from app.graph.nodes_new.trip_interpreter import build_appstate_from_travel_state
from app.graph.build_graph import _mock_discovery_costs

# Build AppState
appstate = build_appstate_from_travel_state(mock_data)

# Test a tool
result = _mock_discovery_costs(appstate)
print(f"Discovery data: {result.request.get('discovery', {})}")
```

## Next Steps

1. **Run the tests** to verify everything works
2. **Modify scenarios** to match your specific use cases
3. **Add custom tools** if you have additional final phase tools
4. **Integrate** the mock data into your existing test suite

The mock data generator creates realistic data that closely matches what the real discovery tools would produce, allowing you to thoroughly test the final phase without the overhead of running the full discovery pipeline.
