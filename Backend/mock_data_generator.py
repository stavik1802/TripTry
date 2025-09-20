#!/usr/bin/env python3
"""
Mock Data Generator for Trip Planner Build Graph Testing

This script generates comprehensive mock data that simulates the state_snapshot
that would be collected before the trip interpreter phase. This allows you to
test the build graph and trip interpreter without running the full discovery pipeline.

Usage:
    python mock_data_generator.py --scenario europe_trip
    python mock_data_generator.py --scenario asia_trip --output mock_state.json
    python mock_data_generator.py --scenario budget_trip --cities 3
"""

import json
import argparse
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MockConfig:
    """Configuration for generating mock data"""
    cities: List[str]
    countries: List[str]
    target_currency: str = "EUR"
    travelers: Dict[str, int] = None
    preferences: Dict[str, Any] = None
    budget_caps: Dict[str, Optional[float]] = None
    musts: List[str] = None
    dates: Dict[str, str] = None
    
    def __post_init__(self):
        if self.travelers is None:
            self.travelers = {"adults": 2, "children": 0}
        if self.preferences is None:
            self.preferences = {
                "pace": "normal",
                "mobility": ["walk", "transit", "taxi"],
                "time_vs_money": 0.5,
                "safety_buffer_min": 15,
                "day_pass_allowed": True,
                "overnight_ok": False,
                "one_way_rental_ok": False,
                "rail_pass_consider": False
            }
        if self.budget_caps is None:
            self.budget_caps = {"total": None, "per_day": None}
        if self.musts is None:
            self.musts = []
        if self.dates is None:
            start_date = date.today() + timedelta(days=14)
            end_date = start_date + timedelta(days=7)
            self.dates = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }


class MockDataGenerator:
    """Generates comprehensive mock data for trip planner testing"""
    
    # Sample data pools
    POI_TEMPLATES = {
        "museums": ["National Museum", "Art Gallery", "History Museum", "Science Center", "Cultural Center"],
        "landmarks": ["Central Square", "Historic District", "City Park", "Observation Deck", "Cathedral"],
        "attractions": ["Zoo", "Aquarium", "Botanical Garden", "Theme Park", "Beach"],
        "cultural": ["Temple", "Palace", "Castle", "Monument", "Market"]
    }
    
    RESTAURANT_TEMPLATES = {
        "fine_dining": ["Le Bistro", "The Garden", "Chef's Table", "Fine Dining Room"],
        "casual": ["Local Cafe", "Street Food Corner", "Family Restaurant", "Bistro"],
        "ethnic": ["Noodle House", "Pizza Corner", "Sushi Bar", "Taco Stand"],
        "fast_food": ["Burger Joint", "Sandwich Shop", "Coffee House", "Deli"]
    }
    
    CURRENCY_BY_COUNTRY = {
        "Italy": "EUR", "France": "EUR", "Germany": "EUR", "Spain": "EUR",
        "Japan": "JPY", "China": "CNY", "Thailand": "THB", "Singapore": "SGD",
        "United States": "USD", "United Kingdom": "GBP", "Canada": "CAD",
        "Australia": "AUD", "Brazil": "BRL", "India": "INR"
    }
    
    def __init__(self, config: MockConfig):
        self.config = config
        self.city_country_map = self._build_city_country_map()
    
    def _build_city_country_map(self) -> Dict[str, str]:
        """Build city to country mapping"""
        mapping = {}
        for i, city in enumerate(self.config.cities):
            country_idx = i % len(self.config.countries)
            mapping[city] = self.config.countries[country_idx]
        return mapping
    
    def generate_interpretation_data(self) -> Dict[str, Any]:
        """Generate the 'interp' section of state_snapshot"""
        countries_data = []
        for i, country in enumerate(self.config.countries):
            country_cities = [city for j, city in enumerate(self.config.cities) 
                            if j % len(self.config.countries) == i]
            countries_data.append({
                "name": country,
                "preferred_cities": country_cities
            })
        
        return {
            "intent": "plan_trip",
            "countries": countries_data,
            "dates": self.config.dates,
            "travelers": self.config.travelers,
            "musts": self.config.musts,
            "preferences": self.config.preferences,
            "budget_caps": self.config.budget_caps,
            "target_currency": self.config.target_currency,
            "passport_country": "US",
            "visa_notes": "Standard tourist visa requirements"
        }
    
    def generate_fx_meta(self) -> Dict[str, Any]:
        """Generate foreign exchange metadata"""
        target_currency = self.config.target_currency
        currency_by_country = {}
        to_target = {}
        
        for country in self.config.countries:
            country_currency = self.CURRENCY_BY_COUNTRY.get(country, "USD")
            currency_by_country[country] = country_currency
            
            if country_currency != target_currency:
                # Mock exchange rates (these would be real in production)
                if target_currency == "USD":
                    to_target[country_currency] = 0.85 if country_currency == "EUR" else 0.007 if country_currency == "JPY" else 1.0
                elif target_currency == "EUR":
                    to_target[country_currency] = 1.18 if country_currency == "USD" else 0.008 if country_currency == "JPY" else 1.0
                else:
                    to_target[country_currency] = 1.0
        
        return {
            "target": target_currency,
            "to_target": to_target,
            "currency_by_country": currency_by_country
        }
    
    def generate_poi_data(self) -> Dict[str, Any]:
        """Generate POI discovery data"""
        poi_by_city = {}
        
        for city in self.config.cities:
            # Generate 3-6 POIs per city
            import random
            num_pois = random.randint(3, 6)
            pois = []
            
            for _ in range(num_pois):
                category = random.choice(list(self.POI_TEMPLATES.keys()))
                template = random.choice(self.POI_TEMPLATES[category])
                pois.append({
                    "name": f"{city} {template}",
                    "category": category,
                    "rating": round(random.uniform(3.5, 5.0), 1),
                    "price_range": random.choice(["$", "$$", "$$$"]),
                    "description": f"Popular {category} in {city}"
                })
            
            poi_by_city[city] = {
                "pois": pois,
                "total_count": len(pois)
            }
        
        return {"poi_by_city": poi_by_city}
    
    def generate_restaurants_data(self) -> Dict[str, Any]:
        """Generate restaurant discovery data"""
        names_by_city = {}
        links_by_city = {}
        details_by_city = {}
        
        for city in self.config.cities:
            # Generate 4-8 restaurants per city
            import random
            num_restaurants = random.randint(4, 8)
            
            # Names by city (bucketed by type)
            names_by_city[city] = {
                "fine_dining": [],
                "casual": [],
                "ethnic": [],
                "fast_food": []
            }
            
            for _ in range(num_restaurants):
                category = random.choice(list(self.RESTAURANT_TEMPLATES.keys()))
                template = random.choice(self.RESTAURANT_TEMPLATES[category])
                restaurant_name = f"{city} {template}"
                
                names_by_city[city][category].append({
                    "name": restaurant_name,
                    "rating": round(random.uniform(3.0, 5.0), 1),
                    "price_range": random.choice(["$", "$$", "$$$", "$$$$"])
                })
            
            # Mock links and details
            links_by_city[city] = {
                "tripadvisor": [f"https://tripadvisor.com/{city.lower().replace(' ', '-')}-restaurant-{i}" 
                               for i in range(2)],
                "google": [f"https://google.com/maps/place/{city.lower().replace(' ', '-')}-restaurant-{i}" 
                          for i in range(2)]
            }
            
            details_by_city[city] = {
                "cuisine_types": random.sample(["Italian", "Asian", "Mediterranean", "Local", "International"], 3),
                "price_levels": random.sample(["$", "$$", "$$$"], 2)
            }
        
        return {
            "names_by_city": names_by_city,
            "links_by_city": links_by_city,
            "details_by_city": details_by_city
        }
    
    def generate_city_fares_data(self) -> Dict[str, Any]:
        """Generate city transportation fare data"""
        city_fares = {}
        
        for city in self.config.cities:
            country = self.city_country_map.get(city, "Unknown")
            currency = self.CURRENCY_BY_COUNTRY.get(country, "USD")
            
            # Mock fare data
            import random
            city_fares[city] = {
                "transit": {
                    "single": {
                        "amount": round(random.uniform(1.5, 4.0), 2),
                        "currency": currency
                    },
                    "day_pass": {
                        "amount": round(random.uniform(8.0, 15.0), 2),
                        "currency": currency
                    },
                    "weekly_pass": {
                        "amount": round(random.uniform(25.0, 45.0), 2),
                        "currency": currency
                    }
                },
                "taxi": {
                    "base": round(random.uniform(2.0, 5.0), 2),
                    "per_km": round(random.uniform(1.2, 2.5), 2),
                    "per_min": round(random.uniform(0.3, 0.8), 2),
                    "currency": currency
                },
                "ride_share": {
                    "base": round(random.uniform(1.5, 3.0), 2),
                    "per_km": round(random.uniform(0.8, 1.8), 2),
                    "per_min": round(random.uniform(0.2, 0.5), 2),
                    "currency": currency
                }
            }
        
        return {"city_fares": city_fares}
    
    def generate_intercity_data(self) -> Dict[str, Any]:
        """Generate intercity transportation data"""
        hops = []
        
        for i in range(len(self.config.cities) - 1):
            from_city = self.config.cities[i]
            to_city = self.config.cities[i + 1]
            from_country = self.city_country_map.get(from_city, "Unknown")
            to_country = self.city_country_map.get(to_city, "Unknown")
            
            # Determine if it's domestic or international
            is_domestic = from_country == to_country
            currency = self.CURRENCY_BY_COUNTRY.get(from_country, "USD")
            
            import random
            # Generate multiple transport options
            transport_options = []
            
            # Flight (always available)
            transport_options.append({
                "mode": "flight",
                "duration": random.randint(60, 300),  # minutes
                "price": round(random.uniform(80, 400), 2),
                "currency": currency,
                "airline": random.choice(["Airline A", "Airline B", "Budget Airline"]),
                "stops": random.choice([0, 1])
            })
            
            # Train (if domestic or nearby countries)
            if is_domestic or random.random() > 0.3:
                transport_options.append({
                    "mode": "train",
                    "duration": random.randint(120, 480),  # minutes
                    "price": round(random.uniform(25, 120), 2),
                    "currency": currency,
                    "class": random.choice(["economy", "business", "first"])
                })
            
            # Bus (budget option)
            transport_options.append({
                "mode": "bus",
                "duration": random.randint(180, 600),  # minutes
                "price": round(random.uniform(15, 60), 2),
                "currency": currency,
                "company": random.choice(["Bus Company A", "Bus Company B"])
            })
            
            # Car rental (if domestic)
            if is_domestic:
                transport_options.append({
                    "mode": "car_rental",
                    "duration": random.randint(90, 360),  # minutes
                    "price": round(random.uniform(40, 150), 2),
                    "currency": currency,
                    "car_type": random.choice(["economy", "compact", "mid-size"])
                })
            
            hops.append({
                "from": from_city,
                "to": to_city,
                "from_country": from_country,
                "to_country": to_country,
                "is_domestic": is_domestic,
                "options": transport_options,
                "recommended": transport_options[0]  # First option as recommended
            })
        
        return {"hops": hops}
    
    def generate_logs(self) -> List[str]:
        """Generate sample log entries"""
        return [
            "[interpret] intent=plan_trip plan=['cities.recommender', 'poi.discovery', 'restaurants.discovery', 'fares.city', 'fares.intercity']",
            "[cities.recommender] picked=['Rome', 'Florence', 'Venice']",
            "[poi.discovery] ok (3 cities)",
            "[restaurants.discovery] ok (3 cities)",
            "[fares.city] ok (3 cities)",
            "[fares.intercity] ok (2 hops)",
            "[gap.search_fill] All required data collected, proceeding to final phase"
        ]
    
    def generate_complete_state_snapshot(self) -> Dict[str, Any]:
        """Generate the complete state_snapshot for trip interpreter testing"""
        return {
            "user_message": f"Plan a trip to {', '.join(self.config.cities)}",
            "interp": self.generate_interpretation_data(),
            "cities": self.config.cities,
            "city_country_map": self.city_country_map,
            "fx_meta": self.generate_fx_meta(),
            "poi": self.generate_poi_data(),
            "restaurants": self.generate_restaurants_data(),
            "city_fares": self.generate_city_fares_data(),
            "intercity": self.generate_intercity_data(),
            "logs": self.generate_logs(),
            "errors": [],
            "plan_queue": [],
            "done_tools": ["cities.recommender", "poi.discovery", "restaurants.discovery", "fares.city", "fares.intercity"],
            "last_tool": "fares.intercity"
        }


def create_scenario_configs() -> Dict[str, MockConfig]:
    """Predefined scenario configurations"""
    scenarios = {}
    
    # European trip scenario
    scenarios["europe_trip"] = MockConfig(
        cities=["Rome", "Florence", "Venice"],
        countries=["Italy"],
        target_currency="EUR",
        travelers={"adults": 2, "children": 0},
        musts=["Colosseum", "Uffizi Gallery", "St. Mark's Basilica"],
        preferences={
            "pace": "normal",
            "mobility": ["walk", "transit", "train"],
            "time_vs_money": 0.6,
            "safety_buffer_min": 20,
            "day_pass_allowed": True,
            "overnight_ok": False,
            "one_way_rental_ok": False,
            "rail_pass_consider": True
        },
        budget_caps={"total": 2500, "per_day": 300}
    )
    
    # Asian trip scenario
    scenarios["asia_trip"] = MockConfig(
        cities=["Tokyo", "Kyoto", "Osaka"],
        countries=["Japan"],
        target_currency="USD",
        travelers={"adults": 2, "children": 1},
        musts=["Tokyo Skytree", "Fushimi Inari Shrine", "Osaka Castle"],
        preferences={
            "pace": "fast",
            "mobility": ["walk", "transit", "taxi"],
            "time_vs_money": 0.7,
            "safety_buffer_min": 10,
            "day_pass_allowed": True,
            "overnight_ok": True,
            "one_way_rental_ok": False,
            "rail_pass_consider": True
        },
        budget_caps={"total": 4000, "per_day": 500}
    )
    
    # Budget backpacking scenario
    scenarios["budget_trip"] = MockConfig(
        cities=["Prague", "Budapest", "Krakow"],
        countries=["Czech Republic", "Hungary", "Poland"],
        target_currency="EUR",
        travelers={"adults": 1, "children": 0},
        musts=["Prague Castle", "Buda Castle", "Wawel Castle"],
        preferences={
            "pace": "slow",
            "mobility": ["walk", "transit", "bus"],
            "time_vs_money": 0.2,
            "safety_buffer_min": 30,
            "day_pass_allowed": True,
            "overnight_ok": True,
            "one_way_rental_ok": False,
            "rail_pass_consider": False
        },
        budget_caps={"total": 800, "per_day": 80}
    )
    
    # Luxury trip scenario
    scenarios["luxury_trip"] = MockConfig(
        cities=["Paris", "Nice", "Monaco"],
        countries=["France", "Monaco"],
        target_currency="EUR",
        travelers={"adults": 2, "children": 0},
        musts=["Louvre", "Eiffel Tower", "Monte Carlo Casino"],
        preferences={
            "pace": "slow",
            "mobility": ["taxi", "rental", "private_transfer"],
            "time_vs_money": 0.9,
            "safety_buffer_min": 45,
            "day_pass_allowed": False,
            "overnight_ok": False,
            "one_way_rental_ok": True,
            "rail_pass_consider": False
        },
        budget_caps={"total": 8000, "per_day": 1000}
    )
    
    # Multi-country scenario
    scenarios["multi_country"] = MockConfig(
        cities=["Amsterdam", "Brussels", "Paris", "London"],
        countries=["Netherlands", "Belgium", "France", "United Kingdom"],
        target_currency="EUR",
        travelers={"adults": 2, "children": 0},
        musts=["Van Gogh Museum", "Grand Place", "Louvre", "Big Ben"],
        preferences={
            "pace": "normal",
            "mobility": ["walk", "transit", "train", "flight"],
            "time_vs_money": 0.5,
            "safety_buffer_min": 20,
            "day_pass_allowed": True,
            "overnight_ok": False,
            "one_way_rental_ok": False,
            "rail_pass_consider": True
        },
        budget_caps={"total": 3500, "per_day": 400}
    )
    
    return scenarios


def main():
    parser = argparse.ArgumentParser(description="Generate mock data for trip planner testing")
    parser.add_argument("--scenario", choices=list(create_scenario_configs().keys()) + ["custom"], 
                       default="europe_trip", help="Predefined scenario to generate")
    parser.add_argument("--cities", nargs="+", help="Custom cities (for custom scenario)")
    parser.add_argument("--countries", nargs="+", help="Custom countries (for custom scenario)")
    parser.add_argument("--currency", default="EUR", help="Target currency")
    parser.add_argument("--adults", type=int, default=2, help="Number of adult travelers")
    parser.add_argument("--children", type=int, default=0, help="Number of child travelers")
    parser.add_argument("--budget", type=float, help="Total budget")
    parser.add_argument("--output", default="mock_state_snapshot.json", help="Output file")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    
    args = parser.parse_args()
    
    # Get configuration
    if args.scenario == "custom":
        if not args.cities or not args.countries:
            print("Error: Custom scenario requires --cities and --countries")
            return 1
        
        config = MockConfig(
            cities=args.cities,
            countries=args.countries,
            target_currency=args.currency,
            travelers={"adults": args.adults, "children": args.children},
            budget_caps={"total": args.budget, "per_day": None}
        )
    else:
        config = create_scenario_configs()[args.scenario]
        # Override with command line args if provided
        if args.currency:
            config.target_currency = args.currency
        if args.adults or args.children:
            config.travelers = {"adults": args.adults, "children": args.children}
        if args.budget:
            config.budget_caps = {"total": args.budget, "per_day": None}
    
    # Generate mock data
    generator = MockDataGenerator(config)
    state_snapshot = generator.generate_complete_state_snapshot()
    
    # Write to file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(state_snapshot, f, indent=2 if args.pretty else None, ensure_ascii=False)
    
    print(f"Mock data generated successfully!")
    print(f"Scenario: {args.scenario}")
    print(f"Cities: {', '.join(config.cities)}")
    print(f"Countries: {', '.join(config.countries)}")
    print(f"Travelers: {config.travelers['adults']} adults, {config.travelers['children']} children")
    print(f"Target currency: {config.target_currency}")
    print(f"Output file: {args.output}")
    
    # Print summary
    print(f"\nData summary:")
    print(f"- Cities: {len(state_snapshot['cities'])}")
    print(f"- POI data: {sum(len(city_data['pois']) for city_data in state_snapshot['poi']['poi_by_city'].values())} POIs")
    print(f"- Restaurants: {sum(len(restaurants) for city_restaurants in state_snapshot['restaurants']['names_by_city'].values() for restaurants in city_restaurants.values())} restaurants")
    print(f"- City fares: {len(state_snapshot['city_fares']['city_fares'])} cities")
    print(f"- Intercity hops: {len(state_snapshot['intercity']['hops'])} connections")
    
    return 0


if __name__ == "__main__":
    exit(main())
