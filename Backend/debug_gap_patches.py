#!/usr/bin/env python3
"""
Debug gap agent patch application
"""

import os
import sys

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent
from app.agents.base_agent import AgentContext

def test_patch_application():
    """Test how patches are applied to research data"""
    print("🔧 Testing Gap Agent Patch Application...")
    print("=" * 50)
    
    # Create test research data
    research_data = {
        "cities": ["Paris"],
        "city_country_map": {"Paris": "France"},
        "poi": {
            "poi_by_city": {
                "Paris": {
                    "pois": [
                        {
                            "name": "Eiffel Tower",
                            # Missing fields
                        }
                    ]
                }
            }
        }
    }
    
    print("Before patches:")
    print(f"  POI data: {research_data['poi']['poi_by_city']['Paris']['pois'][0]}")
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Test patches that should be applied
    patches = {
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].official_url": "https://www.toureiffel.paris/en",
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].hours": "9:30am to 12am",
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].price": "€40.95",
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].coords": "48.8583701,2.2944813"
    }
    
    print(f"\nApplying patches:")
    for path, value in patches.items():
        print(f"  {path} = {value}")
    
    # Apply patches
    gap_agent._apply_patches(research_data, patches)
    
    print(f"\nAfter patches:")
    print(f"  POI data: {research_data['poi']['poi_by_city']['Paris']['pois'][0]}")
    
    # Check if patches were applied correctly
    poi = research_data['poi']['poi_by_city']['Paris']['pois'][0]
    print(f"\nVerification:")
    print(f"  official_url: {poi.get('official_url')}")
    print(f"  hours: {poi.get('hours')}")
    print(f"  price: {poi.get('price')}")
    print(f"  coords: {poi.get('coords')}")

if __name__ == "__main__":
    test_patch_application()
