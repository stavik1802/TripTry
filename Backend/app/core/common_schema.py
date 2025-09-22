"""
Common Data Schema for TripPlanner Multi-Agent System

This module provides standardized data structures, validation schemas, and normalization
utilities used across all agents in the TripPlanner system. It ensures consistency
in data flow, prevents value update issues, and maintains data integrity throughout
the multi-agent workflow.

PURPOSE:
========
The TripPlanner system uses multiple agents that need to share and process data
in consistent formats. This module provides:

1. Standardized data structures for all trip planning entities
2. Data validation utilities for ensuring data integrity
3. Data normalization functions for handling different data formats
4. Standard tool and state key definitions for consistency

DATA STRUCTURES:
===============
- POI: Points of Interest (attractions, landmarks, activities)
- Restaurant: Dining establishments with location and cuisine info
- CityFare: Local transportation costs and options
- IntercityFare: Transportation between cities
- TripDay: Daily itinerary structure
- CostBreakdown: Comprehensive cost analysis

VALIDATION SYSTEM:
=================
The AgentDataSchema class provides comprehensive validation including:
- Data structure validation (required keys, data types)
- Tool availability checking
- Data normalization across different formats
- Type safety enforcement

USAGE:
======
from app.core.common_schema import POI, AgentDataSchema, STANDARD_TOOL_NAMES

# Create standardized POI
poi = POI(name="Eiffel Tower", city="Paris", category="landmark")

# Validate data structure
is_valid = AgentDataSchema.validate_data_structure(data, ["cities", "dates"])

# Use standard tool names
tool_name = STANDARD_TOOL_NAMES["city_recommender"]
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class POI:
    """Standardized POI structure"""
    name: str
    city: str
    category: str = ""
    description: str = ""
    official_url: str = ""
    hours: Dict[str, str] = field(default_factory=dict)
    price: Dict[str, Any] = field(default_factory=dict)
    coords: Dict[str, float] = field(default_factory=dict)
    source_urls: List[str] = field(default_factory=list)

@dataclass
class Restaurant:
    """Standardized restaurant structure"""
    name: str
    city: str
    cuisine: str = ""
    category: str = ""
    url: str = ""
    near_poi: str = ""
    snippet: str = ""
    source: str = ""

@dataclass
class CityFare:
    """Standardized city fare structure"""
    city: str
    transit: Dict[str, Any] = field(default_factory=dict)
    taxi: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IntercityFare:
    """Standardized intercity fare structure"""
    from_city: str
    to_city: str
    mode: str = ""
    duration: Optional[int] = None
    price: Optional[float] = None
    currency: str = ""

@dataclass
class TripDay:
    """Standardized trip day structure"""
    date: str
    city: str
    items: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class CostBreakdown:
    """Standardized cost breakdown structure"""
    lodging: Dict[str, Any] = field(default_factory=dict)
    transit: Dict[str, Any] = field(default_factory=dict)
    intercity: Dict[str, Any] = field(default_factory=dict)
    travel: Dict[str, Any] = field(default_factory=dict)
    poi_entry: Dict[str, Any] = field(default_factory=dict)
    meals: Dict[str, Any] = field(default_factory=dict)
    grand_total: Dict[str, Any] = field(default_factory=dict)

class AgentDataSchema:
    """Standardized data schema for agent communication"""
    
    @staticmethod
    def validate_data_structure(data: Dict[str, Any], required_keys: List[str], data_name: str = "data") -> bool:
        """Validate that data structure contains required keys"""
        if not isinstance(data, dict):
            print(f"[VALIDATION] ❌ {data_name} is not a dictionary")
            return False
        
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            print(f"[VALIDATION] ❌ {data_name} missing required keys: {missing_keys}")
            return False
        
        # Check for empty values that might cause processing issues
        empty_keys = [key for key in required_keys if not data.get(key)]
        if empty_keys:
            print(f"[VALIDATION] ⚠️ {data_name} has empty values for keys: {empty_keys}")
        
        print(f"[VALIDATION] ✅ {data_name} structure is valid")
        return True
    
    @staticmethod
    def validate_data_types(data: Dict[str, Any], type_schema: Dict[str, type], data_name: str = "data") -> bool:
        """Validate that data values match expected types"""
        if not isinstance(data, dict):
            print(f"[VALIDATION] ❌ {data_name} is not a dictionary")
            return False
        
        for key, expected_type in type_schema.items():
            if key in data:
                if not isinstance(data[key], expected_type):
                    print(f"[VALIDATION] ❌ {data_name}.{key} is {type(data[key])}, expected {expected_type}")
                    return False
        
        print(f"[VALIDATION] ✅ {data_name} types are valid")
        return True
    
    @staticmethod
    def validate_tool_availability(tool_name: str, available_tools: Dict[str, bool]) -> bool:
        """Validate that a tool is available before execution"""
        if tool_name not in available_tools:
            print(f"[VALIDATION] ❌ Tool {tool_name} not found in available tools")
            return False
        
        if not available_tools[tool_name]:
            print(f"[VALIDATION] ❌ Tool {tool_name} is not available")
            return False
        
        print(f"[VALIDATION] ✅ Tool {tool_name} is available")
        return True
    
    @staticmethod
    def normalize_poi_data(poi_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize POI data to standard structure"""
        if not poi_data:
            return {"poi_by_city": {}}
        
        normalized = {"poi_by_city": {}}
        
        if "poi_by_city" in poi_data:
            # Already in correct format
            normalized["poi_by_city"] = poi_data["poi_by_city"]
        else:
            # Convert from other formats (city -> data mapping)
            for city, data in poi_data.items():
                if isinstance(data, dict) and "pois" in data:
                    normalized["poi_by_city"][city] = data
                elif isinstance(data, list):
                    normalized["poi_by_city"][city] = {"pois": data}
        
        return normalized
    
    @staticmethod
    def normalize_restaurant_data(restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize restaurant data to standard structure"""
        if not restaurant_data:
            return {"names_by_city": {}, "links_by_city": {}, "details_by_city": {}}
        
        normalized = {
            "names_by_city": restaurant_data.get("names_by_city", {}),
            "links_by_city": restaurant_data.get("links_by_city", {}),
            "details_by_city": restaurant_data.get("details_by_city", {})
        }
        
        return normalized
    
    @staticmethod
    def normalize_city_fares_data(fares_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize city fares data to standard structure"""
        if not fares_data:
            return {"city_fares": {}}
        
        if "city_fares" in fares_data:
            return fares_data
        else:
            return {"city_fares": fares_data}
    
    @staticmethod
    def normalize_intercity_data(intercity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize intercity data to standard structure"""
        if not intercity_data:
            return {"hops": []}
        
        if "hops" in intercity_data:
            return intercity_data
        else:
            return {"hops": intercity_data}
    
    @staticmethod
    def normalize_trip_data(trip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize trip data to standard structure"""
        if not trip_data:
            return {"trip": {"days": []}}
        
        # Check different possible locations for trip data
        if "trip" in trip_data:
            return trip_data
        elif "request" in trip_data and "trip" in trip_data["request"]:
            return trip_data
        else:
            return {"trip": trip_data}
    
    @staticmethod
    def extract_trip_days(trip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract trip days from normalized trip data"""
        if not trip_data:
            return []
        
        trip = trip_data.get("trip", {})
        if not trip:
            return []
        
        return trip.get("days", [])
    
    @staticmethod
    def extract_cost_breakdown(trip_data: Dict[str, Any]) -> CostBreakdown:
        """Extract cost breakdown from trip data"""
        if not trip_data:
            return CostBreakdown()
        
        trip = trip_data.get("trip", {})
        if not trip:
            return CostBreakdown()
        
        totals = trip.get("totals", {})
        if not totals:
            return CostBreakdown()
        
        return CostBreakdown(
            lodging=totals.get("lodging", {}),
            transit=totals.get("transit", {}),
            intercity=totals.get("intercity", {}),
            travel=totals.get("travel", {}),
            poi_entry=totals.get("poi_entry", {}),
            meals=totals.get("meals", {}),
            grand_total=totals.get("grand_total", {})
        )

# =============================================================================
# STANDARD CONSTANTS FOR CONSISTENCY ACROSS AGENTS
# =============================================================================

# Standard tool names used across all agents
# These ensure consistent tool identification throughout the multi-agent system
STANDARD_TOOL_NAMES = {
    "city_recommender": "city_recommender",
    "poi_discovery": "poi_discovery", 
    "restaurants_discovery": "restaurants_discovery",
    "city_fare": "city_fare",
    "intercity_fare": "intercity_fare",
    "currency": "currency",
    "discoveries_costs": "discoveries_costs",
    "city_graph": "city_graph",
    "optimizer": "optimizer",
    "trip_maker": "trip_maker",
    "writer_report": "writer_report",
    "gap_data": "gap_data"
}

# Standard state keys used across all agents
# These ensure consistent state management throughout the workflow
STANDARD_STATE_KEYS = {
    "planning_data": "planning_data",
    "research_data": "research_data", 
    "budget_data": "budget_data",
    "trip_data": "trip_data",
    "geocost_data": "geocost_data",
    "optimized_data": "optimized_data",
    "final_response": "final_response"
}
