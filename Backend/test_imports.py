#!/usr/bin/env python3
"""
Comprehensive Import Test for TripPlanner Multi-Agent System

This test verifies that all imports across the entire codebase are working correctly.
It tests imports from:
- Core modules (agents, tools, core)
- Agent classes and utilities
- Tool modules and utilities
- Configuration and storage
- Bridge and integration modules

Run with: python test_imports.py
"""

import sys
import traceback
from pathlib import Path

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_import(module_name, description=""):
    """Test importing a module and report success/failure"""
    try:
        __import__(module_name)
        print(f"✅ {module_name:<50} {description}")
        return True
    except Exception as e:
        print(f"❌ {module_name:<50} {description}")
        print(f"   Error: {str(e)}")
        if "ModuleNotFoundError" in str(e) or "ImportError" in str(e):
            print(f"   Traceback: {traceback.format_exc().split('ImportError')[0]}ImportError: {str(e)}")
        return False

def test_class_import(module_name, class_name, description=""):
    """Test importing a class from a module"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        getattr(module, class_name)
        print(f"✅ {module_name}.{class_name:<30} {description}")
        return True
    except Exception as e:
        print(f"❌ {module_name}.{class_name:<30} {description}")
        print(f"   Error: {str(e)}")
        return False

def main():
    """Run comprehensive import tests"""
    print("🔍 Testing all imports in TripPlanner Multi-Agent System")
    print("=" * 80)
    
    failed_imports = []
    total_tests = 0
    
    # Test core modules
    print("\n📁 CORE MODULES")
    print("-" * 40)
    
    core_tests = [
        ("app.core.advanced_multi_agent_system", "Main orchestrator"),
        ("app.core.common_schema", "Data schemas and validation"),
        ("app.core.coordinator_graph", "Agent coordination system"),
        ("app.config", "Configuration settings"),
        ("app.main", "FastAPI entry point"),
        ("app.server", "FastAPI server setup"),
    ]
    
    for module, desc in core_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test agent modules
    print("\n🤖 AGENT MODULES")
    print("-" * 40)
    
    agent_tests = [
        ("app.agents.base_agent", "Base agent framework"),
        ("app.agents.agent_state", "Agent state management"),
        ("app.agents.memory_enhanced_base_agent", "Memory-enhanced base agent"),
        ("app.agents.planning_agent", "Planning agent"),
        ("app.agents.reasearch_agent", "Research agent"),
        ("app.agents.budget_agent", "Budget agent"),
        ("app.agents.gap_agent", "Gap filling agent"),
        ("app.agents.output_agent", "Output generation agent"),
        ("app.agents.learning_agent", "Learning agent"),
    ]
    
    for module, desc in agent_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test agent utilities
    print("\n🔧 AGENT UTILITIES")
    print("-" * 40)
    
    agent_utils_tests = [
        ("app.agents.utils.graph_integration", "Graph integration utilities"),
        ("app.agents.utils.memory_system", "Memory system"),
        ("app.agents.utils.multi_agent_system", "Multi-agent system utilities"),
    ]
    
    for module, desc in agent_utils_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test tool modules
    print("\n🛠️  TOOL MODULES")
    print("-" * 40)
    
    tool_tests = [
        ("app.tools.gap_patch.gap_data_tool", "Gap data tool"),
        ("app.tools.interpreter.interpreter", "Request interpreter"),
        ("app.tools.planning.city_graph_tool", "City graph tool"),
        ("app.tools.planning.discoveries_costs_tool", "Discoveries costs tool"),
        ("app.tools.planning.optimizer_helper_tool", "Optimizer helper"),
        ("app.tools.planning.trip_maker_tool", "Trip maker tool"),
        ("app.tools.pricing.city_fare_tool", "City fare tool"),
        ("app.tools.pricing.intercity_fare_tool", "Intercity fare tool"),
        ("app.tools.pricing.currency_tool", "Currency tool"),
        ("app.tools.discovery.city_recommender_tool", "City recommender"),
        ("app.tools.discovery.POI_discovery_tool", "POI discovery"),
        ("app.tools.discovery.restaurants_discovery_tool", "Restaurants discovery"),
        ("app.tools.export.exporter_tool", "Exporter tool"),
        ("app.tools.export.writer_report_tool", "Writer report tool"),
    ]
    
    for module, desc in tool_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test tool utilities
    print("\n🔨 TOOL UTILITIES")
    print("-" * 40)
    
    tool_utils_tests = [
        ("app.tools.tools_utils.state", "AppState utilities"),
        ("app.tools.tools_utils.specs", "Gap detection specs"),
        ("app.tools.tools_utils.patch", "Patch utilities"),
        ("app.tools.bridge.tools_to_agent", "Tools bridge"),
    ]
    
    for module, desc in tool_utils_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test storage modules
    print("\n💾 STORAGE MODULES")
    print("-" * 40)
    
    storage_tests = [
        ("app.database.mongo_store", "MongoDB storage"),
    ]
    
    for module, desc in storage_tests:
        total_tests += 1
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test specific class imports
    print("\n🏗️  CLASS IMPORTS")
    print("-" * 40)
    
    class_tests = [
        ("app.core.advanced_multi_agent_system", "AdvancedMultiAgentSystem", "Main system class"),
        ("app.agents.planning_agent", "PlanningAgent", "Planning agent class"),
        ("app.agents.budget_agent", "BudgetAgent", "Budget agent class"),
        ("app.tools.interpreter.interpreter", "interpret", "Interpreter function"),
        ("app.tools.tools_utils.state", "AppState", "AppState class"),
    ]
    
    for module, class_name, desc in class_tests:
        total_tests += 1
        if not test_class_import(module, class_name, desc):
            failed_imports.append(f"{module}.{class_name}")
    
    # Summary
    print("\n" + "=" * 80)
    print(f"📊 IMPORT TEST SUMMARY")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {total_tests - len(failed_imports)}")
    print(f"Failed: {len(failed_imports)}")
    
    if failed_imports:
        print(f"\n❌ FAILED IMPORTS:")
        for failed in failed_imports:
            print(f"   - {failed}")
        print(f"\n🔧 Please check the import paths and dependencies for the failed modules.")
        return False
    else:
        print(f"\n🎉 ALL IMPORTS SUCCESSFUL!")
        print(f"✅ The entire TripPlanner Multi-Agent System can be imported correctly.")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
