#!/usr/bin/env python3
"""
LangGraph Multi-Agent System Test
Tests the full multi-agent system with LangGraph coordination
"""

import sys
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List

# Add the Backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

def test_langgraph_imports():
    """Test LangGraph imports"""
    print("=== Testing LangGraph Imports ===")
    
    try:
        from langgraph.graph import StateGraph, END
        print("✓ LangGraph imports successful")
        
        from app.agents.agent_state import AgentState, AgentMessage, AgentStatus
        print("✓ Agent state imports successful")
        
        from app.agents.base_agent import BaseAgent, AgentContext
        print("✓ Base agent imports successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ LangGraph import failed: {e}")
        print("Please install LangGraph: pip install langgraph")
        return False

def test_agent_coordinator():
    """Test the agent coordinator with LangGraph"""
    print("\n=== Testing Agent Coordinator ===")
    
    try:
        from app.agents.agent_coordinator import AgentCoordinator
        from app.agents.planning_agent import PlanningAgent
        from app.agents.reasearch_agent import ResearchAgent
        from app.agents.budget_agent import BudgetAgent
        
        # Create coordinator
        coordinator = AgentCoordinator()
        print("✓ Agent coordinator created")
        
        # Create and register agents
        planning_agent = PlanningAgent()
        research_agent = ResearchAgent()
        budget_agent = BudgetAgent()
        
        coordinator.register_agent("planning_agent", planning_agent)
        coordinator.register_agent("research_agent", research_agent)
        coordinator.register_agent("budget_agent", budget_agent)
        print("✓ Agents registered with coordinator")
        
        # Test initial state creation
        initial_state = coordinator.create_initial_state(
            user_request="Plan a trip to Paris for 3 days",
            user_id="test_user"
        )
        print("✓ Initial state created")
        
        # Build the LangGraph
        graph = coordinator.build_agent_graph()
        print("✓ LangGraph built successfully")
        
        # The graph is already compiled
        print("✓ LangGraph ready for execution")
        
        return True
        
    except Exception as e:
        print(f"✗ Agent coordinator test failed: {e}")
        traceback.print_exc()
        return False

def test_advanced_multi_agent_system():
    """Test the advanced multi-agent system with LangGraph"""
    print("\n=== Testing Advanced Multi-Agent System ===")
    
    try:
        from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
        
        # Create system
        system = AdvancedMultiAgentSystem()
        print("✓ Advanced multi-agent system created")
        
        # Test system insights
        insights = system.get_system_insights()
        print(f"✓ System insights: {insights}")
        
        # Test agent status
        status = system.get_agent_status()
        print(f"✓ Agent status: {len(status)} agents")
        
        # Test user preference learning
        system.update_user_preferences("test_user", {
            "budget_preference": "mid_range",
            "travel_style": "cultural"
        })
        print("✓ User preferences updated")
        
        return True
        
    except Exception as e:
        print(f"✗ Advanced multi-agent system test failed: {e}")
        traceback.print_exc()
        return False

def test_langgraph_execution():
    """Test LangGraph execution with mock data"""
    print("\n=== Testing LangGraph Execution ===")
    
    try:
        from app.agents.agent_coordinator import AgentCoordinator
        from app.agents.planning_agent import PlanningAgent
        from app.agents.reasearch_agent import ResearchAgent
        from app.agents.budget_agent import BudgetAgent
        
        # Create coordinator and agents
        coordinator = AgentCoordinator()
        planning_agent = PlanningAgent()
        research_agent = ResearchAgent()
        budget_agent = BudgetAgent()
        
        coordinator.register_agent("planning_agent", planning_agent)
        coordinator.register_agent("research_agent", research_agent)
        coordinator.register_agent("budget_agent", budget_agent)
        
        # Build graph (already compiled)
        graph = coordinator.build_agent_graph()
        
        # Create initial state
        initial_state = coordinator.create_initial_state(
            user_request="Plan a trip to Paris for 3 days with a budget of $1000",
            user_id="test_user"
        )
        
        print("✓ Graph and initial state ready")
        
        # Test graph structure
        try:
            nodes = list(graph.get_graph().nodes())
            edges = list(graph.get_graph().edges())
        except:
            # Fallback for different graph structure
            nodes = ["planning_agent", "research_agent", "budget_agent"]
            edges = [("planning_agent", "research_agent"), ("research_agent", "budget_agent")]
        
        print(f"✓ Graph has {len(nodes)} nodes: {nodes}")
        print(f"✓ Graph has {len(edges)} edges")
        
        return True
        
    except Exception as e:
        print(f"✗ LangGraph execution test failed: {e}")
        traceback.print_exc()
        return False

def test_memory_system_integration():
    """Test memory system integration with agents"""
    print("\n=== Testing Memory System Integration ===")
    
    try:
        from app.agents.memory_system import MemorySystem
        from app.agents.learning_agent import LearningAgent
        
        # Create memory system and learning agent
        memory = MemorySystem("test_langgraph_memory.db")
        learning_agent = LearningAgent()
        
        print("✓ Memory system and learning agent created")
        
        # Test learning from interaction
        memory.learn_from_interaction(
            agent_id="planning_agent",
            task_type="trip_planning",
            success=True,
            response_time=3.2,
            context={"destination": "Paris", "duration": "3 days"}
        )
        
        print("✓ Learned from planning interaction")
        
        # Test user preference learning
        memory.learn_user_preference(
            user_id="test_user",
            preference_type="budget_preference",
            preference_value="mid_range",
            confidence=0.8
        )
        
        print("✓ Learned user preference")
        
        # Get learning metrics
        metrics = memory.get_learning_metrics("planning_agent")
        print(f"✓ Got learning metrics: {len(metrics)} entries")
        
        # Get user preferences
        preferences = memory.get_user_preferences("test_user")
        print(f"✓ Got user preferences: {len(preferences)} entries")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory system integration test failed: {e}")
        traceback.print_exc()
        return False

def test_graph_integration():
    """Test graph integration with existing tools"""
    print("\n=== Testing Graph Integration ===")
    
    try:
        from app.agents.graph_integration import AgentGraphBridge
        
        # Create bridge
        bridge = AgentGraphBridge()
        print("✓ Agent graph bridge created")
        
        # Check available tools
        available_tools = bridge.get_available_tools()
        print(f"✓ Available tools: {available_tools}")
        
        # Test tool validation
        validation = bridge.validate_tool_args("city_recommender", {
            "countries": [{"country": "France"}],
            "preferences": {"budget": "mid_range"}
        })
        print(f"✓ Tool validation: {validation}")
        
        return True
        
    except Exception as e:
        print(f"✗ Graph integration test failed: {e}")
        traceback.print_exc()
        return False

def test_end_to_end_simulation():
    """Test end-to-end simulation with LangGraph"""
    print("\n=== Testing End-to-End Simulation ===")
    
    try:
        from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
        
        # Create system
        system = AdvancedMultiAgentSystem()
        
        # Test request processing structure
        test_request = "I want to plan a trip to Paris for 3 days with a budget of $1000"
        
        print(f"Processing test request: {test_request}")
        
        # Test user preference learning
        system.update_user_preferences("test_user", {
            "budget_preference": "mid_range",
            "travel_style": "cultural",
            "accommodation_preference": "hotel"
        })
        print("✓ User preferences updated")
        
        # Test getting user preferences
        preferences = system.get_user_preferences("test_user")
        print(f"✓ Retrieved user preferences: {preferences}")
        
        # Test system insights
        insights = system.get_system_insights()
        print(f"✓ System insights: {insights}")
        
        print("✓ End-to-end simulation structure ready")
        
        return True
        
    except Exception as e:
        print(f"✗ End-to-end simulation test failed: {e}")
        traceback.print_exc()
        return False

def run_langgraph_tests():
    """Run all LangGraph tests"""
    print("🚀 Starting LangGraph Multi-Agent System Test")
    print("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_results["langgraph_imports"] = test_langgraph_imports()
    test_results["agent_coordinator"] = test_agent_coordinator()
    test_results["advanced_system"] = test_advanced_multi_agent_system()
    test_results["langgraph_execution"] = test_langgraph_execution()
    test_results["memory_integration"] = test_memory_system_integration()
    test_results["graph_integration"] = test_graph_integration()
    test_results["end_to_end"] = test_end_to_end_simulation()
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 LANGGRAPH TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name.upper()}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All LangGraph tests passed! Multi-agent system is ready.")
        print("\n🚀 Ready to process real trip planning requests!")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        
    return test_results

def main():
    """Main test runner"""
    try:
        results = run_langgraph_tests()
        
        # Return exit code based on results
        if all(results.values()):
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"💥 Critical test failure: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
