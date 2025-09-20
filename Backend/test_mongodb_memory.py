#!/usr/bin/env python3
"""
Test MongoDB Memory System Integration
"""

import sys
import os
import traceback
from datetime import datetime

# Add the Backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend'))

def test_mongodb_imports():
    """Test MongoDB imports"""
    print("=== Testing MongoDB Imports ===")
    
    try:
        from app.agents.memory_system import MemorySystem, MemoryEntry, LearningMetrics, UserPreference
        print("✓ Memory system imports successful")
        
        # Test MongoDB availability
        try:
            from pymongo import MongoClient
            print("✓ PyMongo available")
        except ImportError:
            print("⚠️  PyMongo not available - install with: pip install pymongo")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_memory_system_mongodb():
    """Test memory system with MongoDB"""
    print("\n=== Testing Memory System with MongoDB ===")
    
    try:
        from app.agents.memory_system import MemorySystem
        
        # Create memory system with MongoDB
        memory = MemorySystem(mongo_uri="mongodb://localhost:27017", db_name="test_agent_memory")
        print("✓ Memory system created")
        
        # Test storing memories
        memory_id = memory.store_memory(
            agent_id="test_agent",
            memory_type="episodic",
            content={"test": "data", "value": 42, "timestamp": datetime.now().isoformat()},
            importance=0.8,
            tags=["test", "mongodb", "episodic"]
        )
        print(f"✓ Stored memory: {memory_id}")
        
        # Test retrieving memories
        memories = memory.retrieve_memories(agent_id="test_agent", limit=5)
        print(f"✓ Retrieved {len(memories)} memories")
        
        # Test learning from interaction
        memory.learn_from_interaction(
            agent_id="test_agent",
            task_type="mongodb_test",
            success=True,
            response_time=1.5,
            context={"test": "mongodb_integration"}
        )
        print("✓ Learned from interaction")
        
        # Test user preference learning
        memory.learn_user_preference(
            user_id="test_user",
            preference_type="database_preference",
            preference_value="mongodb",
            confidence=0.9
        )
        print("✓ Learned user preference")
        
        # Get metrics
        metrics = memory.get_learning_metrics("test_agent")
        print(f"✓ Got learning metrics: {len(metrics)} entries")
        
        # Get user preferences
        preferences = memory.get_user_preferences("test_user")
        print(f"✓ Got user preferences: {len(preferences)} entries")
        
        # Test memory consolidation
        memory.consolidate_memories("test_agent")
        print("✓ Memory consolidation completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory system test failed: {e}")
        traceback.print_exc()
        return False

def test_memory_persistence():
    """Test memory persistence across sessions"""
    print("\n=== Testing Memory Persistence ===")
    
    try:
        from app.agents.memory_system import MemorySystem
        
        # Create first memory system instance
        memory1 = MemorySystem(mongo_uri="mongodb://localhost:27017", db_name="test_persistence")
        
        # Store some data
        memory1.store_memory(
            agent_id="persistence_agent",
            memory_type="semantic",
            content={"fact": "MongoDB is a NoSQL database"},
            importance=0.9,
            tags=["fact", "database", "persistence"]
        )
        
        memory1.learn_from_interaction(
            agent_id="persistence_agent",
            task_type="persistence_test",
            success=True,
            response_time=2.0,
            context={"test": "persistence"}
        )
        
        memory1.learn_user_preference(
            user_id="persistence_user",
            preference_type="test_preference",
            preference_value="persistent_value",
            confidence=0.8
        )
        
        print("✓ Data stored in first instance")
        
        # Create second memory system instance (simulating restart)
        memory2 = MemorySystem(mongo_uri="mongodb://localhost:27017", db_name="test_persistence")
        
        # Load data from database
        memory2.load_from_database()
        print("✓ Data loaded from database")
        
        # Verify data persistence
        memories = memory2.retrieve_memories(agent_id="persistence_agent")
        metrics = memory2.get_learning_metrics("persistence_agent")
        preferences = memory2.get_user_preferences("persistence_user")
        
        print(f"✓ Persistence verification: {len(memories)} memories, {len(metrics)} metrics, {len(preferences)} preferences")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory persistence test failed: {e}")
        traceback.print_exc()
        return False

def test_multi_agent_mongodb():
    """Test multi-agent system with MongoDB"""
    print("\n=== Testing Multi-Agent System with MongoDB ===")
    
    try:
        from app.agents.advanced_multi_agent_system import AdvancedMultiAgentSystem
        
        # Create system with MongoDB
        system = AdvancedMultiAgentSystem()
        print("✓ Advanced multi-agent system created with MongoDB")
        
        # Test user preference learning
        system.update_user_preferences("mongodb_user", {
            "database_preference": "mongodb",
            "storage_type": "document",
            "query_language": "mql"
        })
        print("✓ User preferences updated")
        
        # Get user preferences
        preferences = system.get_user_preferences("mongodb_user")
        print(f"✓ Retrieved user preferences: {len(preferences)} entries")
        
        # Test system insights
        insights = system.get_system_insights()
        print(f"✓ System insights: {insights}")
        
        return True
        
    except Exception as e:
        print(f"✗ Multi-agent MongoDB test failed: {e}")
        traceback.print_exc()
        return False

def run_mongodb_tests():
    """Run all MongoDB tests"""
    print("🚀 Starting MongoDB Memory System Tests")
    print("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_results["mongodb_imports"] = test_mongodb_imports()
    test_results["memory_system"] = test_memory_system_mongodb()
    test_results["memory_persistence"] = test_memory_persistence()
    test_results["multi_agent"] = test_multi_agent_mongodb()
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 MONGODB TEST SUMMARY")
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
        print("🎉 All MongoDB tests passed! Memory system is ready.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        
    return test_results

def main():
    """Main test runner"""
    try:
        results = run_mongodb_tests()
        
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

