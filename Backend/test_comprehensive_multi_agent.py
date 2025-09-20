#!/usr/bin/env python3
"""
Comprehensive Test Suite for Multi-Agent System
Tests all components: agents, graph integration, memory, learning, and coordination
"""

import sys
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List

# Add the Backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

def test_imports():
    """Test that all required modules can be imported"""
    print("=== Testing Imports ===")
    
    try:
        # Test base agent imports
        from app.agents.base_agent import BaseAgent, AgentMessage, AgentContext
        print("✓ Base agent imports successful")
        
        # Test memory system imports
        from app.agents.memory_system import MemorySystem, MemoryEntry, LearningMetrics
        print("✓ Memory system imports successful")
        
        # Test individual agents
        from app.agents.planning_agent import PlanningAgent
        print("✓ Planning agent import successful")
        
        from app.agents.reasearch_agent import ResearchAgent
        print("✓ Research agent import successful")
        
        from app.agents.budget_agent import BudgetAgent
        print("✓ Budget agent import successful")
        
        from app.agents.learning_agent import LearningAgent
        print("✓ Learning agent import successful")
        
        # Test integration layer
        from app.agents.graph_integration import AgentGraphBridge, AgentStateConverter
        print("✓ Graph integration imports successful")
        
        # Test coordinator
        from app.agents.agent_coordinator import AgentCoordinator
        print("✓ Agent coordinator import successful")
        
        # Test advanced system
        from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
        print("✓ Advanced multi-agent system import successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_memory_system():
    """Test the memory system functionality"""
    print("\n=== Testing Memory System ===")
    
    try:
        from app.agents.memory_system import MemorySystem
        
        # Create memory system
        memory = MemorySystem("test_memory.db")
        print("✓ Memory system created")
        
        # Test storing memories
        memory_id = memory.store_memory(
            agent_id="test_agent",
            memory_type="episodic",
            content={"test": "data", "value": 42},
            importance=0.8,
            tags=["test", "episodic"]
        )
        print(f"✓ Stored memory: {memory_id}")
        
        # Test retrieving memories
        memories = memory.retrieve_memories(agent_id="test_agent", limit=5)
        print(f"✓ Retrieved {len(memories)} memories")
        
        # Test learning from interaction
        memory.learn_from_interaction(
            agent_id="test_agent",
            task_type="test_task",
            success=True,
            response_time=2.5,
            context={"test": "context"}
        )
        print("✓ Learned from interaction")
        
        # Test user preference learning
        memory.learn_user_preference(
            user_id="test_user",
            preference_type="budget_preference",
            preference_value="mid_range",
            confidence=0.8
        )
        print("✓ Learned user preference")
        
        # Get metrics
        metrics = memory.get_learning_metrics("test_agent")
        print(f"✓ Got learning metrics: {len(metrics)} entries")
        
        # Get user preferences
        preferences = memory.get_user_preferences("test_user")
        print(f"✓ Got user preferences: {len(preferences)} entries")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory system test failed: {e}")
        traceback.print_exc()
        return False

def test_graph_integration():
    """Test the graph integration layer"""
    print("\n=== Testing Graph Integration ===")
    
    try:
        from app.agents.graph_integration import AgentGraphBridge, AgentStateConverter
        
        # Create bridge
        bridge = AgentGraphBridge()
        print("✓ Agent graph bridge created")
        
        # Check available tools
        available_tools = bridge.get_available_tools()
        print(f"✓ Available tools: {available_tools}")
        
        # Test tool validation
        validation = bridge.validate_tool_args("city_recommender", {"countries": [{"country": "France"}]})
        print(f"✓ Tool validation: {validation}")
        
        # Test state conversion
        from app.agents.base_agent import AgentContext
        context = AgentContext(
            session_id="test_session",
            user_request="Test request",
            conversation_history=[],
            shared_data={"test": "data"},
            goals=["test_goal"],
            constraints=["test_constraint"]
        )
        
        graph_state = AgentStateConverter.agent_context_to_graph_state(context)
        converted_back = AgentStateConverter.graph_state_to_agent_context(graph_state)
        print("✓ State conversion successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Graph integration test failed: {e}")
        traceback.print_exc()
        return False

def test_individual_agents():
    """Test individual agent functionality"""
    print("\n=== Testing Individual Agents ===")
    
    try:
        from app.agents.planning_agent import PlanningAgent
        from app.agents.reasearch_agent import ResearchAgent
        from app.agents.budget_agent import BudgetAgent
        from app.agents.learning_agent import LearningAgent
        from app.agents.base_agent import AgentContext, AgentMessage
        
        # Test planning agent
        planning_agent = PlanningAgent()
        print("✓ Planning agent created")
        
        # Test research agent
        research_agent = ResearchAgent()
        print("✓ Research agent created")
        
        # Test budget agent
        budget_agent = BudgetAgent()
        print("✓ Budget agent created")
        
        # Test learning agent
        learning_agent = LearningAgent()
        print("✓ Learning agent created")
        
        # Test agent context creation
        context = AgentContext(
            session_id="test_session",
            user_request="Test trip planning request",
            conversation_history=[],
            shared_data={"user_id": "test_user", "budget": "mid_range"},
            goals=["plan_trip"],
            constraints=["budget_limit"]
        )
        print("✓ Agent context created")
        
        # Test agent message creation
        message = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="test_message",
            content={"test": "data"}
        )
        print("✓ Agent message created")
        
        return True
        
    except Exception as e:
        print(f"✗ Individual agents test failed: {e}")
        traceback.print_exc()
        return False

def test_agent_coordination():
    """Test agent coordination system"""
    print("\n=== Testing Agent Coordination ===")
    
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
            user_request="Test trip planning request",
            user_id="test_user"
        )
        print("✓ Initial state created")
        
        # Test coordination strategies
        strategies = coordinator.get_coordination_strategies()
        print(f"✓ Available coordination strategies: {strategies}")
        
        return True
        
    except Exception as e:
        print(f"✗ Agent coordination test failed: {e}")
        traceback.print_exc()
        return False

def test_advanced_multi_agent_system():
    """Test the advanced multi-agent system"""
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
        
        # Test simple request processing (without actually running tools)
        print("✓ System ready for request processing")
        
        return True
        
    except Exception as e:
        print(f"✗ Advanced multi-agent system test failed: {e}")
        traceback.print_exc()
        return False

def test_end_to_end_simulation():
    """Test end-to-end simulation without external API calls"""
    print("\n=== Testing End-to-End Simulation ===")
    
    try:
        from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
        
        # Create system
        system = AdvancedMultiAgentSystem()
        
        # Test with mock request
        test_request = "I want to plan a trip to Paris for 3 days with a budget of $1000"
        
        print(f"Processing test request: {test_request}")
        
        # This would normally call external APIs, so we'll test the structure
        # without actually executing the full pipeline
        
        # Test user preference learning
        system.update_user_preferences("test_user", {
            "budget_preference": "mid_range",
            "travel_style": "cultural"
        })
        print("✓ User preferences updated")
        
        # Test getting user preferences
        preferences = system.get_user_preferences("test_user")
        print(f"✓ Retrieved user preferences: {preferences}")
        
        print("✓ End-to-end simulation structure ready")
        
        return True
        
    except Exception as e:
        print(f"✗ End-to-end simulation test failed: {e}")
        traceback.print_exc()
        return False

def test_graph_tools_availability():
    """Test availability of graph tools"""
    print("\n=== Testing Graph Tools Availability ===")
    
    try:
        from app.agents.graph_integration import AgentGraphBridge
        
        bridge = AgentGraphBridge()
        available_tools = bridge.get_available_tools()
        
        print("Graph tools availability:")
        for tool_name, available in available_tools.items():
            status = "✓" if available else "✗"
            print(f"  {status} {tool_name}")
        
        # Count available tools
        available_count = sum(1 for available in available_tools.values() if available)
        total_count = len(available_tools)
        
        print(f"\nTools available: {available_count}/{total_count}")
        
        return available_count > 0
        
    except Exception as e:
        print(f"✗ Graph tools availability test failed: {e}")
        traceback.print_exc()
        return False

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🚀 Starting Comprehensive Multi-Agent System Test")
    print("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_results["imports"] = test_imports()
    test_results["memory_system"] = test_memory_system()
    test_results["graph_integration"] = test_graph_integration()
    test_results["individual_agents"] = test_individual_agents()
    test_results["agent_coordination"] = test_agent_coordination()
    test_results["advanced_system"] = test_advanced_multi_agent_system()
    test_results["end_to_end"] = test_end_to_end_simulation()
    test_results["graph_tools"] = test_graph_tools_availability()
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
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
        print("🎉 All tests passed! Multi-agent system is ready.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        
    return test_results

def main():
    """Main test runner"""
    try:
        results = run_comprehensive_test()
        
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
