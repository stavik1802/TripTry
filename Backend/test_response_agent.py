#!/usr/bin/env python3
"""
Test the AI-powered response agent with manually generated data
"""
import os
import sys
sys.path.append('/home/stav.karasik/TripPlanner/Backend')

# Set API keys
os.environ['OPENAI_API_KEY'] = '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'

from app.agents.output_agent import OutputAgent
from app.agents.base_agent import AgentContext

def test_response_agent():
    print("=== TESTING AI-POWERED RESPONSE AGENT ===")
    print("=" * 60)
    
    # Create response agent
    response_agent = OutputAgent()
    
    # Create mock data that would come from other agents
    planning_data = {
        "intent": "plan_trip",
        "travelers": {"adults": 2, "children": 1},
        "preferences": {
            "duration_days": 3,
            "themes": ["cultural", "fine dining"],
            "price_tier": "budget",
            "kid_friendly": True
        },
        "budget_caps": {"total": 1500.0},
        "target_currency": "EUR",
        "musts": ["Eiffel Tower", "Louvre Museum"],
        "countries": [{"country": "France", "cities": ["Paris"]}]
    }
    
    research_data = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "name": "Eiffel Tower",
                            "description": "Iconic iron tower and symbol of Paris",
                            "price": {"adult": 35.70, "child": 17.85, "currency": "EUR"},
                            "coords": {"lat": 48.8583, "lon": 2.2944},
                            "official_url": "https://www.toureiffel.paris/en"
                        },
                        {
                            "name": "Louvre Museum",
                            "description": "World's largest art museum and historic monument",
                            "price": {"adult": 17.00, "child": 0.00, "currency": "EUR"},
                            "coords": {"lat": 48.8606, "lon": 2.3376},
                            "official_url": "https://www.louvre.fr/en"
                        },
                        {
                            "name": "Notre-Dame Cathedral",
                            "description": "Medieval Catholic cathedral",
                            "price": {"adult": 0.00, "child": 0.00, "currency": "EUR"},
                            "coords": {"lat": 48.8530, "lon": 2.3499}
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
                            "url": "https://www.restaurants-toureiffel.com/fr/restaurant-jules-verne"
                        },
                        {
                            "name": "L'Astrance",
                            "cuisine": "French",
                            "url": "https://www.astrance.com"
                        }
                    ],
                    "casual": [
                        {
                            "name": "Café de Flore",
                            "cuisine": "French",
                            "url": "https://www.cafedeflore.fr"
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
                        "weekly_pass": {"amount": 31.60, "currency": "EUR"}
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
                }
            }
        }
    }
    
    budget_data = {
        "cost_breakdown": {
            "accommodation": 300.00,
            "transportation": 150.00,
            "attractions": 100.00,
            "meals": 400.00,
            "miscellaneous": 50.00
        },
        "total_cost": 1000.00
    }
    
    trip_data = {
        "request": {
            "trip": {
                "days": [
                    {
                        "date": "2024-03-15",
                        "city": "Paris",
                        "items": [
                            {
                                "name": "Eiffel Tower",
                                "type": "attraction",
                                "start_min": 540,  # 9:00 AM
                                "duration_min": 120
                            },
                            {
                                "name": "Lunch at Café de Flore",
                                "type": "meal",
                                "start_min": 720,  # 12:00 PM
                                "duration_min": 90
                            },
                            {
                                "name": "Louvre Museum",
                                "type": "attraction",
                                "start_min": 900,  # 3:00 PM
                                "duration_min": 180
                            }
                        ]
                    },
                    {
                        "date": "2024-03-16",
                        "city": "Paris",
                        "items": [
                            {
                                "name": "Notre-Dame Cathedral",
                                "type": "attraction",
                                "start_min": 600,  # 10:00 AM
                                "duration_min": 90
                            },
                            {
                                "name": "Dinner at Le Jules Verne",
                                "type": "meal",
                                "start_min": 1200,  # 8:00 PM
                                "duration_min": 150
                            }
                        ]
                    },
                    {
                        "date": "2024-03-17",
                        "city": "Paris",
                        "items": [
                            {
                                "name": "Seine River Cruise",
                                "type": "activity",
                                "start_min": 660,  # 11:00 AM
                                "duration_min": 60
                            },
                            {
                                "name": "Shopping in Champs-Élysées",
                                "type": "shopping",
                                "start_min": 780,  # 1:00 PM
                                "duration_min": 120
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    geocost_data = {}
    optimized_data = {}
    
    # Create context with all the data
    context = AgentContext()
    context.user_request = "I want to visit Paris for 3 days with my family (2 adults, 1 child). We want to see the Eiffel Tower, Louvre Museum, and eat at good French restaurants. Budget around 1500 EUR. We prefer cultural attractions and fine dining."
    context.shared_data = {
        "planning_data": planning_data,
        "research_data": research_data,
        "budget_data": budget_data,
        "trip_data": trip_data,
        "geocost_data": geocost_data,
        "optimized_data": optimized_data
    }
    
    print(f"📋 Test Data Summary:")
    print(f"   Cities: {research_data['cities']}")
    print(f"   POIs: {len(research_data['poi']['poi_by_city']['Paris']['pois'])}")
    print(f"   Restaurants: {sum(len(cat) for cat in research_data['restaurants']['names_by_city']['Paris'].values())}")
    print(f"   Trip Days: {len(trip_data['request']['trip']['days'])}")
    print(f"   Budget: {budget_data['total_cost']} EUR")
    
    print(f"\n🤖 Testing AI Response Generation...")
    
    # Test the response agent
    result = response_agent.execute_task(context)
    
    print(f"\n📊 Response Agent Result:")
    print(f"   Status: {result.get('status')}")
    print(f"   Agent ID: {result.get('agent_id')}")
    
    if result.get('status') == 'success':
        response = result.get('response', {})
        print(f"\n✅ AI Response Generated Successfully!")
        print(f"   Tier: {response.get('tier', 'unknown')}")
        
        # Show the AI-generated response
        if response.get('response_text'):
            print(f"\n🤖 AI-GENERATED RESPONSE:")
            print("=" * 80)
            print(response['response_text'])
            print("=" * 80)
        
        # Show summary
        if response.get('summary'):
            summary = response['summary']
            print(f"\n📊 RESPONSE SUMMARY:")
            print(f"   Cities: {summary.get('cities', [])}")
            print(f"   Duration: {summary.get('duration', 0)} days")
            print(f"   Budget: {summary.get('budget', 0)} {summary.get('currency', 'EUR')}")
            print(f"   Has Itinerary: {summary.get('has_itinerary', False)}")
            print(f"   Has POIs: {summary.get('has_pois', False)}")
            print(f"   Has Restaurants: {summary.get('has_restaurants', False)}")
            print(f"   Has Transportation: {summary.get('has_transportation', False)}")
        
        # Show trip data
        if response.get('trip_data'):
            trip_days = response['trip_data']
            print(f"\n🗓️ TRIP ITINERARY:")
            for i, day in enumerate(trip_days):
                print(f"   Day {i+1}: {day.get('date')} in {day.get('city')}")
                items = day.get('items', [])
                for item in items:
                    name = item.get('name', 'Unknown')
                    start_time = item.get('start_min', 0)
                    if start_time:
                        hours = start_time // 60
                        minutes = start_time % 60
                        time_str = f"{hours:02d}:{minutes:02d}"
                        print(f"      {time_str}: {name}")
                    else:
                        print(f"      • {name}")
    else:
        print(f"\n❌ Response Agent Failed:")
        print(f"   Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_response_agent()
