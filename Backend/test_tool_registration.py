#!/usr/bin/env python3
"""
Test tool registration to see what tools are available
"""

import os
import sys

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.graph_integration import AgentGraphBridge

def test_tool_registration():
    """Test what tools are registered in the bridge"""
    
    print("=== TOOL REGISTRATION TEST ===")
    print("=" * 50)
    
    # Create bridge
    bridge = AgentGraphBridge()
    
    print(f"📊 Total tools registered: {len(bridge._tool_registry)}")
    print(f"📊 Available tools:")
    
    for tool_name in sorted(bridge._tool_registry.keys()):
        print(f"  ✅ {tool_name}")
    
    # Test gap_data specifically
    if "gap_data" in bridge._tool_registry:
        print(f"\n✅ gap_data tool is registered")
        
        # Test calling it
        print(f"\n🔍 Testing gap_data tool call...")
        try:
            test_args = {
                "message": "Tell me about the Eiffel Tower",
                "request_snapshot": {"poi": {"poi_by_city": {"Paris": {"pois": []}}}},
                "missing": [{"path": "test", "description": "test"}],
                "max_queries_per_item": 1,
                "max_results_per_query": 1
            }
            
            result = bridge.execute_tool("gap_data", test_args)
            print(f"✅ gap_data tool call succeeded: {result.get('status', 'unknown')}")
            if result.get('status') == 'error':
                print(f"❌ Error: {result.get('error', 'unknown')}")
        except Exception as e:
            print(f"❌ gap_data tool call failed: {e}")
    else:
        print(f"\n❌ gap_data tool is NOT registered")
    
    print(f"\n" + "=" * 50)
    print("🎉 TOOL REGISTRATION TEST COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    test_tool_registration()
