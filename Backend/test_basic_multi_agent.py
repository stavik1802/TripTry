#!/usr/bin/env python3
"""
Basic Test Suite for Multi-Agent System
Tests core functionality without external dependencies
"""

import sys
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List

# Add the Backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

def test_core_imports():
    """Test core imports"""
    print("=== Testing Core Imports ===")
    
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
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_agent_creation():
    """Test agent creation and basic functionality"""
    print("\n=== Testing Agent Creation ===")
    
    try:
        from app.agents.planning_agent import PlanningAgent
        from app.agents.reasearch_agent import ResearchAgent
        from app.agents.budget_agent import BudgetAgent
        from app.agents.learning_agent import LearningAgent
        from app.agents.base_agent import AgentContext, AgentMessage
        
        # Create agents
        planning_agent = PlanningAgent()
        research_agent = ResearchAgent()
        budget_agent = BudgetAgent()
        learning_agent = LearningAgent()
        
        print("✓ All agents created successfully")
        
        # Test agent properties
        print(f"✓ Planning agent ID: {planning_agent.agent_id}")
        print(f"✓ Research agent capabilities: {research_agent.capabilities}")
        print(f"✓ Budget agent dependencies: {budget_agent.dependencies}")
        print(f"✓ Learning agent type: {learning_agent.agent_type}")
        
        # Test agent context
        context = AgentContext(
            session_id="test_session",
            user_request="Test request",
            conversation_history=[],
            shared_data={"test": "data"},
            goals=["test_goal"],
            constraints=["test_constraint"]
        )
        print("✓ Agent context created")
        
        # Test agent message
        message = AgentMessage(
            sender="test_sender",
            recipient="test_recipient",
            message_type="test_message",
            content={"test": "data"}
        )
        print("✓ Agent message created")
        
        return True
        
    except Exception as e:
        print(f"✗ Agent creation test failed: {e}")
        traceback.print_exc()
        return False

def test_memory_system():
    """Test memory system without external dependencies"""
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
        
        return True
        
    except Exception as e:
        print(f"✗ Memory system test failed: {e}")
        traceback.print_exc()
        return False

def test_graph_integration():
    """Test graph integration layer"""
    print("\n=== Testing Graph Integration ===")
    
    try:
        from app.agents.graph_integration import AgentGraphBridge, AgentStateConverter
        
        # Create bridge
        bridge = AgentGraphBridge()
        print("✓ Agent graph bridge created")
        
        # Check available tools
        available_tools = bridge.get_available_tools()
        print(f"✓ Available tools: {available_tools}")
        
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

def test_agent_communication():
    """Test agent communication"""
    print("\n=== Testing Agent Communication ===")
    
    try:
        from app.agents.planning_agent import PlanningAgent
        from app.agents.reasearch_agent import ResearchAgent
        from app.agents.base_agent import AgentMessage
        
        # Create agents
        planning_agent = PlanningAgent()
        research_agent = ResearchAgent()
        
        # Create test message
        message = AgentMessage(
            sender="planning_agent",
            recipient="research_agent",
            message_type="research_request",
            content={
                "plan": {"countries": [{"country": "France"}]},
                "tool_plan": ["city_recommender"],
                "user_request": "Plan trip to France"
            },
            priority=2
        )
        
        print("✓ Test message created")
        
        # Test message processing (without actually executing tools)
        response = research_agent.process_message(message)
        print("✓ Message processing attempted")
        
        return True
        
    except Exception as e:
        print(f"✗ Agent communication test failed: {e}")
        traceback.print_exc()
        return False

def run_basic_tests():
    """Run all basic tests"""
    print("🚀 Starting Basic Multi-Agent System Test")
    print("=" * 50)
    
    test_results = {}
    
    # Run all tests
    test_results["core_imports"] = test_core_imports()
    test_results["agent_creation"] = test_agent_creation()
    test_results["memory_system"] = test_memory_system()
    test_results["graph_integration"] = test_graph_integration()
    test_results["agent_communication"] = test_agent_communication()
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
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
        print("🎉 All basic tests passed! Core system is working.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        
    return test_results

def main():
    """Main test runner"""
    try:
        results = run_basic_tests()
        
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
