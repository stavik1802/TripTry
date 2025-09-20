#!/usr/bin/env python3
"""
Test all patch types to ensure the gap agent works with different path patterns
"""

import os
import sys
from typing import Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.gap_agent import GapAgent

def test_all_patch_types():
    """Test the gap agent with different patch path patterns"""
    
    print("=== ALL PATCH TYPES TEST ===")
    print("=" * 50)
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Test data with different structures
    test_data = {
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {"name": "Eiffel Tower", "hours": None, "price": None, "coords": None}
                    ]
                }
            }
        },
        "restaurants": {
            "names_by_city": {
                "Paris": {
                    "fine_dining": [
                        {"name": "Le Jules Verne", "url": None}
                    ]
                }
            }
        },
        "fares": {
            "city": {
                "Paris": {
                    "single": None,
                    "day_pass": None
                }
            },
            "intercity": {
                "Paris->London": {
                    "rail": {
                        "price": None,
                        "duration_min": None
                    }
                }
            }
        }
    }
    
    # Test different patch patterns
    test_patches = {
        # POI array patches (should use array logic)
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].hours": "9:00 AM - 11:00 PM",
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].price": {"adult": 25, "currency": "EUR"},
        
        # Restaurant array patches (should use array logic)
        "restaurants.names_by_city.Paris.fine_dining[name=Le Jules Verne].url": "https://lejulesverne-paris.com",
        
        # City fare patches (should use regular logic)
        "fares.city.Paris.single": {"amount": 2.10, "currency": "EUR"},
        "fares.city.Paris.day_pass": {"amount": 7.50, "currency": "EUR"},
        
        # Intercity patches (should use regular logic)
        "fares.intercity.Paris->London.rail.price": {"amount": 120, "currency": "EUR"},
        "fares.intercity.Paris->London.rail.duration_min": 150,
    }
    
    print("🧪 Testing patch application...")
    print(f"📊 Test data structure:")
    print(f"  - POI array: {len(test_data['poi']['poi_by_city']['Paris']['pois'])} items")
    print(f"  - Restaurant array: {len(test_data['restaurants']['names_by_city']['Paris']['fine_dining'])} items")
    print(f"  - City fares: {list(test_data['fares']['city']['Paris'].keys())}")
    print(f"  - Intercity fares: {list(test_data['fares']['intercity'].keys())}")
    
    print(f"\n🔧 Applying {len(test_patches)} patches...")
    
    # Apply patches
    gap_agent._apply_patches(test_data, test_patches)
    
    print(f"\n📊 Results after patching:")
    
    # Check POI patches
    eiffel_tower = test_data['poi']['poi_by_city']['Paris']['pois'][0]
    print(f"  ✅ POI array patches:")
    print(f"    - Eiffel Tower hours: {eiffel_tower.get('hours', 'NOT FOUND')}")
    print(f"    - Eiffel Tower price: {eiffel_tower.get('price', 'NOT FOUND')}")
    
    # Check restaurant patches
    le_jules_verne = test_data['restaurants']['names_by_city']['Paris']['fine_dining'][0]
    print(f"  ✅ Restaurant array patches:")
    print(f"    - Le Jules Verne URL: {le_jules_verne.get('url', 'NOT FOUND')}")
    
    # Check city fare patches
    print(f"  ✅ City fare patches:")
    print(f"    - Paris single: {test_data['fares']['city']['Paris'].get('single', 'NOT FOUND')}")
    print(f"    - Paris day_pass: {test_data['fares']['city']['Paris'].get('day_pass', 'NOT FOUND')}")
    
    # Check intercity patches
    print(f"  ✅ Intercity patches:")
    print(f"    - Paris->London rail price: {test_data['fares']['intercity']['Paris->London']['rail'].get('price', 'NOT FOUND')}")
    print(f"    - Paris->London rail duration: {test_data['fares']['intercity']['Paris->London']['rail'].get('duration_min', 'NOT FOUND')}")
    
    # Verify no unexpected keys were created
    print(f"\n🔍 Checking for unexpected keys:")
    paris_pois = test_data['poi']['poi_by_city']['Paris']
    if 'pois[name=Eiffel Tower]' in paris_pois:
        print(f"  ❌ Found unexpected key 'pois[name=Eiffel Tower]' - array patch failed!")
    else:
        print(f"  ✅ No unexpected keys found - array patches worked correctly!")
    
    print(f"\n" + "=" * 50)
    print("🎉 ALL PATCH TYPES TEST COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    test_all_patch_types()
