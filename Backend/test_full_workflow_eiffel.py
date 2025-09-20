#!/usr/bin/env python3
"""
Full LangGraph workflow test for Eiffel Tower info to verify gap agent data passing
"""

import os
import sys
import json
from typing import Dict, Any
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.agents.agent_coordinator import AgentCoordinator

def test_full_workflow_eiffel():
    """Test the complete LangGraph workflow for Eiffel Tower info"""
    
    print("=== FULL LANGGRAPH WORKFLOW TEST - EIFFEL TOWER ===")
    print("=" * 60)
    
    # Create coordinator
    coordinator = AgentCoordinator()
    
    # Create and register agents
    from app.agents.planning_agent import PlanningAgent
    from app.agents.reasearch_agent import ResearchAgent
    from app.agents.budget_agent import BudgetAgent
    from app.agents.output_agent import OutputAgent
    from app.agents.gap_agent import GapAgent
    from app.agents.learning_agent import LearningAgent
    
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
    
    print(f"✅ Created AgentCoordinator")
    print(f"📊 Available agents: {list(coordinator.agents.keys())}")
    
    # Build the workflow
    workflow = coordinator.build_agent_graph()
    print(f"✅ Built agent graph workflow")
    
    # Test request
    user_request = "Tell me about the Eiffel Tower in Paris"
    print(f"\n🎯 User Request: {user_request}")
    
    # Initial state with all required AgentState fields
    initial_state = {
        "session_id": "test_eiffel_session",
        "user_request": user_request,
        "conversation_history": [],
        "agent_statuses": {},
        "agent_memories": {},
        "message_queue": [],
        "message_history": [],
        "planning_data": {},
        "research_data": {},
        "budget_data": {},
        "final_response": None,
        "current_agent": "planning_agent",
        "next_agent": None,
        "coordination_strategy": "sequential",
        "error_handling_mode": "retry",
        "start_time": datetime.now(),
        "processing_steps": [],
        "performance_metrics": {},
        # Additional fields for gap agent
        "gap_filling_completed": False,
        "gap_filling_attempts": 0,
        "sla_seconds": 300
    }
    
    print(f"\n🚀 Starting full workflow...")
    print("-" * 40)
    
    try:
        # Execute the full workflow
        result = workflow.invoke(initial_state)
        
        print(f"\n✅ Workflow completed successfully!")
        print(f"📊 Final state keys: {list(result.keys())}")
        
        # Check if gap agent was called
        if "gap_filling_completed" in result:
            print(f"🔍 Gap filling completed: {result['gap_filling_completed']}")
        
        if "gap_filling_attempts" in result:
            print(f"🔍 Gap filling attempts: {result['gap_filling_attempts']}")
        
        # Check research data for filled POI information
        research_data = result.get("research_data", {})
        print(f"\n📊 Research data keys: {list(research_data.keys())}")
        
        if "poi" in research_data:
            poi_data = research_data["poi"]
            print(f"📊 POI data structure: {type(poi_data)}")
            
            if isinstance(poi_data, dict) and "poi_by_city" in poi_data:
                paris_pois = poi_data["poi_by_city"].get("Paris", {})
                if "pois" in paris_pois:
                    pois = paris_pois["pois"]
                    print(f"📊 Found {len(pois)} POIs in Paris")
                    
                    # Look for Eiffel Tower specifically
                    eiffel_tower = None
                    for poi in pois:
                        if poi.get("name") == "Eiffel Tower":
                            eiffel_tower = poi
                            break
                    
                    if eiffel_tower:
                        print(f"\n🗼 EIFFEL TOWER DATA:")
                        print(f"  - Name: {eiffel_tower.get('name', 'N/A')}")
                        print(f"  - Category: {eiffel_tower.get('category', 'N/A')}")
                        print(f"  - Official URL: {eiffel_tower.get('official_url', 'N/A')}")
                        print(f"  - Hours: {eiffel_tower.get('hours', 'N/A')}")
                        print(f"  - Price: {eiffel_tower.get('price', 'N/A')}")
                        print(f"  - Coordinates: {eiffel_tower.get('coords', 'N/A')}")
                        
                        # Check if gap filling worked
                        has_hours = eiffel_tower.get('hours') is not None
                        has_price = eiffel_tower.get('price') is not None
                        has_coords = eiffel_tower.get('coords') is not None
                        
                        print(f"\n🔍 GAP FILLING VERIFICATION:")
                        print(f"  - Hours filled: {'✅' if has_hours else '❌'}")
                        print(f"  - Price filled: {'✅' if has_price else '❌'}")
                        print(f"  - Coordinates filled: {'✅' if has_coords else '❌'}")
                        
                        if has_hours and has_price and has_coords:
                            print(f"🎉 SUCCESS: All missing data was filled by gap agent!")
                        else:
                            print(f"⚠️ PARTIAL: Some data still missing")
                    else:
                        print(f"❌ Eiffel Tower not found in POI data")
                else:
                    print(f"❌ No 'pois' key in Paris POI data")
            else:
                print(f"❌ POI data structure unexpected: {poi_data}")
        else:
            print(f"❌ No POI data in research results")
        
        # Check final response
        if "final_response" in result:
            final_response = result["final_response"]
            print(f"\n📝 FINAL RESPONSE:")
            print(f"  - Type: {type(final_response)}")
            if isinstance(final_response, dict):
                print(f"  - Keys: {list(final_response.keys())}")
                if "response" in final_response:
                    response_data = final_response["response"]
                    if isinstance(response_data, dict) and "response_text" in response_data:
                        response_text = response_data["response_text"]
                        print(f"  - Response length: {len(response_text)} characters")
                        print(f"  - Response preview: {response_text[:200]}...")
                    else:
                        print(f"  - Response structure: {response_data}")
                else:
                    print(f"  - Response data: {final_response}")
            else:
                print(f"  - Response: {final_response}")
        
        # Check processing steps
        processing_steps = result.get("processing_steps", [])
        print(f"\n📋 PROCESSING STEPS:")
        for i, step in enumerate(processing_steps):
            print(f"  {i+1}. {step}")
        
        print(f"\n" + "=" * 60)
        print("🎉 FULL WORKFLOW TEST COMPLETE!")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_full_workflow_eiffel()
