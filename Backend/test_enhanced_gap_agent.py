#!/usr/bin/env python3
"""
Test script to verify enhanced gap agent with comprehensive gap detection
"""

import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.append('/home/stav.karasik/TripPlanner/Backend')

# Set API keys
os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"

from app.agents.agent_coordinator import AgentCoordinator
from app.agents.planning_agent import PlanningAgent
from app.agents.reasearch_agent import ResearchAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.output_agent import OutputAgent
from app.agents.gap_agent import GapAgent
from app.agents.learning_agent import LearningAgent

def test_enhanced_gap_agent():
    """Test enhanced gap agent with comprehensive gap detection"""
    
    print('=== TESTING ENHANCED GAP AGENT ===')
    print('=' * 60)
    
    # Create coordinator
    coordinator = AgentCoordinator()
    
    # Create and register agents
    planning_agent = PlanningAgent()
    research_agent = ResearchAgent()
    budget_agent = BudgetAgent()
    output_agent = OutputAgent()
    gap_agent = GapAgent()
    learning_agent = LearningAgent()
    
    coordinator.register_agent("planning_agent", planning_agent)
    coordinator.register_agent("research_agent", research_agent)
    coordinator.register_agent("budget_agent", budget_agent)
    coordinator.register_agent("output_agent", output_agent)
    coordinator.register_agent("gap_agent", gap_agent)
    coordinator.register_agent("learning_agent", learning_agent)
    
    print("✅ All agents registered")
    
    # Create workflow
    workflow = coordinator.build_agent_graph()
    print("✅ Workflow created")
    
    # Test with a request that should trigger gap detection
    print(f"\n{'='*60}")
    print("TEST: Enhanced Gap Agent with POI Discovery")
    print(f"{'='*60}")
    print("Request: Tell me about the Eiffel Tower in Paris")
    
    try:
        # Execute workflow
        result = workflow.invoke({
            "session_id": "test_enhanced_gap",
            "user_request": "Tell me about the Eiffel Tower in Paris. I want to know the opening hours, ticket prices, and official website.",
            "user_id": "test_user",
            "conversation_history": [],
            "agent_statuses": {},
            "agent_memories": {},
            "message_queue": [],
            "message_history": [],
            "shared_data": {},
            "next_agent": "coordinator"
        })
        
        print(f"\n✅ Workflow executed successfully!")
        
        # Check the response
        if "final_response" in result:
            response = result["final_response"]
            
            # Get the actual response text
            response_text = ""
            if response.get('response') and response['response'].get('response_text'):
                response_text = response['response']['response_text']
            elif response.get('response_text'):
                response_text = response['response_text']
            
            if response_text:
                print(f"\n📝 RESPONSE TEXT:")
                print("=" * 60)
                print(response_text)
                print("=" * 60)
                
                # Analyze response for gap-filled data
                print(f"\n🔍 GAP DETECTION ANALYSIS:")
                if "official website" in response_text.lower() or "toureiffel.paris" in response_text.lower():
                    print("   ✅ Official website information found")
                else:
                    print("   ❌ Official website information missing")
                
                if "hours" in response_text.lower() or "opening" in response_text.lower():
                    print("   ✅ Opening hours information found")
                else:
                    print("   ❌ Opening hours information missing")
                
                if "price" in response_text.lower() or "ticket" in response_text.lower() or "€" in response_text or "euro" in response_text.lower():
                    print("   ✅ Price information found")
                else:
                    print("   ❌ Price information missing")
                
                if "coordinates" in response_text.lower() or "latitude" in response_text.lower() or "longitude" in response_text.lower():
                    print("   ✅ Coordinate information found")
                else:
                    print("   ❌ Coordinate information missing")
            else:
                print(f"   ❌ No response text generated")
        else:
            print(f"   ❌ No final_response found in result")
        
        # Check research data for detailed information
        if "research_data" in result:
            research_data = result["research_data"]
            print(f"\n🔍 RESEARCH DATA ANALYSIS:")
            
            if research_data.get('poi'):
                poi_data = research_data['poi']
                print(f"   POI Data Available: {bool(poi_data)}")
                
                if poi_data.get('Paris', {}).get('pois'):
                    paris_pois = poi_data['Paris']['pois']
                    eiffel_tower = None
                    for poi in paris_pois:
                        if poi.get('name', '').lower() == 'eiffel tower':
                            eiffel_tower = poi
                            break
                    
                    if eiffel_tower:
                        print(f"   Eiffel Tower Data Found:")
                        print(f"     - Official URL: {eiffel_tower.get('official_url', 'Missing')}")
                        print(f"     - Hours: {eiffel_tower.get('hours', 'Missing')}")
                        print(f"     - Price: {eiffel_tower.get('price', 'Missing')}")
                        print(f"     - Coordinates: {eiffel_tower.get('coords', 'Missing')}")
                    else:
                        print(f"   ❌ Eiffel Tower not found in POI data")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 ENHANCED GAP AGENT TEST COMPLETE!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_enhanced_gap_agent()
