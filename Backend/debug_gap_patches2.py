#!/usr/bin/env python3
"""
Debug gap agent patch application - step by step
"""

import os
import sys

# Add Backend to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.agents.gap_agent import GapAgent

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
    print(f"  Full structure: {research_data}")
    
    # Create gap agent
    gap_agent = GapAgent()
    
    # Test path parsing first
    test_path = "poi.poi_by_city.Paris.pois[name=Eiffel Tower].official_url"
    print(f"\nTesting path parsing for: {test_path}")
    parsed_keys = gap_agent._parse_path(test_path)
    print(f"Parsed keys: {parsed_keys}")
    
    # Test patches that should be applied
    patches = {
        "poi.poi_by_city.Paris.pois[name=Eiffel Tower].official_url": "https://www.toureiffel.paris/en",
    }
    
    print(f"\nApplying single patch:")
    for path, value in patches.items():
        print(f"  {path} = {value}")
    
    # Apply patches
    gap_agent._apply_patches(research_data, patches)
    
    print(f"\nAfter patches:")
    print(f"  Full structure: {research_data}")
    if research_data['poi']['poi_by_city']['Paris']['pois']:
        print(f"  POI data: {research_data['poi']['poi_by_city']['Paris']['pois'][0]}")
    else:
        print(f"  POI data: No POIs found")

if __name__ == "__main__":
    test_patch_application()
