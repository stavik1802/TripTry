# Mock Data Generator for Trip Planner Testing

This directory contains tools for generating comprehensive mock data to test the trip planner's build graph and trip interpreter functionality without running the full discovery pipeline.

## Files

- `mock_data_generator.py` - Main script for generating mock data
- `test_trip_interpreter.py` - Test script for validating the trip interpreter
- `example_usage.py` - Examples of how to use the mock data tools
- `MOCK_DATA_README.md` - This documentation file

## Quick Start

### 1. Generate Mock Data

```bash
# Generate data for a predefined scenario
python mock_data_generator.py --scenario europe_trip

# Generate data for a custom trip
python mock_data_generator.py --scenario custom --cities "Tokyo" "Kyoto" "Osaka" --countries "Japan" --currency USD

# Generate data with specific parameters
python mock_data_generator.py --scenario asia_trip --adults 2 --children 1 --budget 4000
```

### 2. Test the Trip Interpreter

```bash
# Test with generated mock data
python test_trip_interpreter.py --scenario europe_trip --test-interpreter

# Test with a specific mock file
python test_trip_interpreter.py --mock-file mock_state_snapshot.json --test-interpreter

# Run all tests
python test_trip_interpreter.py --scenario asia_trip --test-interpreter --test-appstate --test-integration
```

### 3. Run Examples

```bash
# Run all usage examples
python example_usage.py
```

## Available Scenarios

The mock data generator includes several predefined scenarios:

- **europe_trip**: Rome, Florence, Venice (Italy) - Cultural tour
- **asia_trip**: Tokyo, Kyoto, Osaka (Japan) - Family trip with child
- **budget_trip**: Prague, Budapest, Krakow (Eastern Europe) - Backpacking
- **luxury_trip**: Paris, Nice, Monaco (France/Monaco) - High-end travel
- **multi_country**: Amsterdam, Brussels, Paris, London - Multi-country tour

## Mock Data Structure

The generated mock data includes all the components that the trip interpreter expects:

### Core Data
- `interp`: Interpretation data (intent, countries, dates, travelers, preferences, budget)
- `cities`: List of cities to visit
- `city_country_map`: Mapping of cities to countries
- `fx_meta`: Foreign exchange metadata and conversion rates

### Discovery Data
- `poi`: Points of interest by city (museums, landmarks, attractions, cultural sites)
- `restaurants`: Restaurant data by city (names, links, details, cuisine types)
- `city_fares`: Transportation costs within cities (transit, taxi, ride-share)
- `intercity`: Transportation between cities (flights, trains, buses, car rental)

### Metadata
- `logs`: Sample log entries from the discovery phase
- `errors`: Error log (empty in mock data)
- `done_tools`: List of completed discovery tools
- `last_tool`: Last tool that was executed

## Usage in Code

### Basic Usage

```python
from mock_data_generator import MockDataGenerator, MockConfig

# Create configuration
config = MockConfig(
    cities=["Rome", "Florence"],
    countries=["Italy"],
    target_currency="EUR",
    travelers={"adults": 2, "children": 0}
)

# Generate mock data
generator = MockDataGenerator(config)
state_snapshot = generator.generate_complete_state_snapshot()

# Use with trip interpreter
from app.graph.nodes_new.trip_interpreter import interpret_trip_plan
result = interpret_trip_plan("Plan my Italian vacation", state_snapshot)
```

### Using Predefined Scenarios

```python
from mock_data_generator import create_scenario_configs

# Get a scenario
scenarios = create_scenario_configs()
config = scenarios["asia_trip"]

# Generate data
generator = MockDataGenerator(config)
state_snapshot = generator.generate_complete_state_snapshot()
```

### Testing the Build Graph

```python
from app.graph.build_graph import build_graph, TravelState

# Convert mock data to TravelState
travel_state: TravelState = {
    "user_message": state_snapshot.get("user_message", "Plan my trip"),
    "interp": state_snapshot.get("interp", {}),
    "cities": state_snapshot.get("cities", []),
    # ... other fields
}

# Build and test the graph
graph = build_graph()
result = graph.invoke(travel_state)
```

## Command Line Options

### Mock Data Generator

```bash
python mock_data_generator.py [options]

Options:
  --scenario {europe_trip,asia_trip,budget_trip,luxury_trip,multi_country,custom}
                        Predefined scenario to generate
  --cities CITIES [CITIES ...]
                        Custom cities (for custom scenario)
  --countries COUNTRIES [COUNTRIES ...]
                        Custom countries (for custom scenario)
  --currency CURRENCY   Target currency (default: EUR)
  --adults ADULTS       Number of adult travelers (default: 2)
  --children CHILDREN   Number of child travelers (default: 0)
  --budget BUDGET       Total budget
  --output OUTPUT       Output file (default: mock_state_snapshot.json)
  --pretty              Pretty print JSON
```

### Test Script

```bash
python test_trip_interpreter.py [options]

Options:
  --mock-file MOCK_FILE
                        Path to mock data JSON file
  --scenario SCENARIO   Generate and test a specific scenario
  --test-interpreter    Test the trip interpreter function
  --test-appstate       Test the AppState builder
  --test-integration    Test build graph integration
  --validate-only       Only validate the mock data structure
  --user-message MESSAGE
                        Custom user message for testing
```

## Data Validation

The mock data generator creates realistic data structures that match what the real discovery tools would produce:

- **POI Data**: Includes categories (museums, landmarks, attractions, cultural), ratings, price ranges
- **Restaurant Data**: Organized by cuisine type with ratings and price levels
- **Transportation**: Multiple options (transit, taxi, ride-share) with realistic pricing
- **Intercity Travel**: Various modes (flight, train, bus, car rental) with duration and cost estimates
- **Foreign Exchange**: Realistic currency mappings and conversion rates

## Integration with Build Graph

The mock data is designed to work seamlessly with the existing build graph:

1. **Phase 1**: Discovery tools populate the state with cities, POIs, restaurants, fares, etc.
2. **Phase 2**: Trip interpreter analyzes the collected data and determines which final tools to run
3. **Final Phase**: Final tools (discovery.costs, city.graph, opt.greedy, trip.maker) process the data

The mock data simulates the state after Phase 1, allowing you to test Phase 2 and the final phase without running the full discovery pipeline.

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're running from the Backend directory or have it in your Python path
2. **Missing Dependencies**: Ensure all required packages are installed (see requirements.txt)
3. **Data Structure Mismatches**: The mock data should match the expected TravelState structure

### Debug Mode

Enable debug output by setting environment variables:

```bash
export TP_MOCK_TOOLS=1
export TP_MOCK_FINAL=1
export PD_TRACE=1
```

This will enable mock mode for all tools and add detailed tracing information.

## Contributing

To add new scenarios or improve the mock data:

1. Add new scenarios to `create_scenario_configs()` in `mock_data_generator.py`
2. Extend the data generation methods to include more realistic data
3. Update the test scripts to cover new functionality
4. Update this documentation

## Examples

See `example_usage.py` for comprehensive examples of how to use the mock data tools in your own code.
