"""
Graph Integration System for TripPlanner Multi-Agent Tools

This module provides a robust bridge between agents and external tools, implementing
a sophisticated tool execution framework with timeout handling, retry logic, circuit
breakers, and concurrent execution capabilities.

ARCHITECTURE OVERVIEW:
=====================
The system consists of three main components:

1. GRAPH TOOL WRAPPER - Wraps all external tools for consistent interface
2. CIRCUIT BREAKER - Prevents cascading failures with failure threshold tracking
3. AGENT GRAPH BRIDGE - Main execution engine with timeout, retry, and concurrency

FEATURES:
=========
- **Timeout Management**: Configurable timeouts per tool call
- **Retry Logic**: Exponential backoff with jitter for failed calls
- **Circuit Breaker**: Prevents system overload during tool failures
- **Concurrent Execution**: Thread pool for parallel tool execution
- **Tool Registration**: Dynamic registration of available tools
- **Policy Management**: Per-tool configuration of execution policies
- **Error Handling**: Comprehensive error reporting and recovery

TOOL CATEGORIES:
===============
- **Discovery Tools**: city_recommender, poi_discovery, restaurants_discovery
- **Pricing Tools**: city_fare, intercity_fare, currency
- **Planning Tools**: discoveries_costs, city_graph, optimizer, trip_maker
- **Export Tools**: writer_report, exporter
- **Gap Tools**: gap_data
- **Interpreter**: Natural language request interpretation

EXECUTION POLICIES:
==================
Each tool can have customized execution policies:
- timeout_sec: Maximum execution time
- retries: Number of retry attempts
- base_backoff_sec: Initial backoff delay
- backoff_jitter_sec: Random jitter for backoff
- circuit_fail_threshold: Failures before circuit opens
- circuit_open_sec: Duration circuit stays open

USAGE:
======
bridge = AgentGraphBridge()
bridge.register_tool("my_tool", my_tool_function)
result = bridge.execute_tool("my_tool", {"param": "value"})

The result format is always:
- Success: {"status": "success", "result": {...}}
- Error: {"status": "error", "error": "error_message"}
- Skipped: {"status": "skipped", "error": "circuit_open"}
"""

from __future__ import annotations

import time
import random
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

DEFAULT_MAX_WORKERS = 12

# Per-tool default policy
DEFAULT_POLICY = {
    "timeout_sec": 45,           # hard wall for any tool call
    "retries": 2,                # retry count after the first attempt (total tries = retries+1)
    "base_backoff_sec": 1.0,     # first backoff
    "backoff_jitter_sec": 0.3,   # +/- jitter
    "circuit_fail_threshold": 3, # consecutive failures to open circuit
    "circuit_open_sec": 60,      # how long we keep it open
}

class GraphToolWrapper:
    """Wrapper class for all external tools with import handling and fallbacks."""
    
    @staticmethod
    def wrap_interpreter_tool():
        """Wrap interpreter tool for natural language processing."""
        try:
            from app.tools.interpreter.interpreter import interpret
            return interpret
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_city_recommender_tool():
        """Wrap city recommender tool for destination suggestions."""
        try:
            from app.tools.discovery.city_recommender import city_recommender_tool, CityRecommenderArgs
            return city_recommender_tool, CityRecommenderArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_poi_discovery_tool():
        """Wrap POI discovery tool for finding attractions."""
        try:
            from app.tools.discovery.POI_discovery_tool import poi_discovery_tool, POIDiscoveryArgs
            return poi_discovery_tool, POIDiscoveryArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_restaurants_discovery_tool():
        """Wrap restaurants discovery tool for finding dining options."""
        try:
            from app.tools.discovery.restaurants_discovery_tool import restaurants_discovery_tool, RestaurantsDiscoveryArgs
            return restaurants_discovery_tool, RestaurantsDiscoveryArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_city_fare_tool():
        """Wrap city fare tool for local transportation costs."""
        try:
            from app.tools.pricing.city_fare_tool import cityfares_discovery_tool, CityFaresArgs
            return cityfares_discovery_tool, CityFaresArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_intercity_fare_tool():
        """Wrap intercity fare tool for intercity transportation costs."""
        try:
            from app.tools.pricing.intercity_fare_tool import intercity_discovery_tool, IntercityDiscoveryArgs
            return intercity_discovery_tool, IntercityDiscoveryArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_currency_tool():
        """Wrap currency tool for exchange rate information."""
        try:
            from app.tools.pricing.currency_tool import fx_oracle_tool, FxOracleArgs
            return fx_oracle_tool, FxOracleArgs
        except ImportError as e:
            return None, None
    
    @staticmethod
    def wrap_discoveries_costs_tool():
        """Wrap discoveries costs tool for combining discovery and cost data."""
        try:
            from app.tools.planning.discoveries_costs_tool import discovery_and_cost
            return discovery_and_cost
        except ImportError as e:
            return None

    @staticmethod
    def wrap_city_graph_tool():
        """Wrap city graph tool for geographic and cost data assembly."""
        try:
            from app.tools.planning.city_graph_tool import geocost_assembler
            return geocost_assembler
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_optimizer_tool():
        """Wrap optimizer tool for itinerary optimization."""
        try:
            from app.tools.planning.optimizer_helper_tool import itinerary_optimizer_greedy
            return itinerary_optimizer_greedy
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_trip_maker_tool():
        """Wrap trip maker tool for creating detailed trip plans."""
        try:
            from app.tools.planning.trip_maker_tool import trip_orchestrator
            return trip_orchestrator
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_writer_report_tool():
        """Wrap writer report tool for generating trip reports."""
        try:
            from app.tools.export.writer_report_tool import writer_report
            return writer_report
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_exporter_tool():
        """Wrap exporter tool for data export functionality."""
        try:
            from app.tools.export.exporter_tool import exporter
            return exporter
        except ImportError as e:
            return None
    
    @staticmethod
    def wrap_gap_data_tool():
        """Wrap gap data tool for filling missing data gaps."""
        try:
            from app.tools.gap_patch.gap_data_tool import fill_gaps_search_only
            return fill_gaps_search_only
        except ImportError as e:
            return None

class _Breaker:
    """Circuit breaker for preventing cascading failures during tool execution."""
    __slots__ = ("failures", "opened_until")

    def __init__(self):
        """Initialize circuit breaker with no failures and closed state."""
        self.failures = 0
        self.opened_until: float = 0.0

    def is_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        return time.time() < self.opened_until

    def record_success(self) -> None:
        """Record successful execution and reset failure count."""
        self.failures = 0
        self.opened_until = 0.0

    def record_failure(self, threshold: int, open_for: float) -> None:
        """Record failure and open circuit if threshold reached."""
        self.failures += 1
        if self.failures >= threshold:
            self.opened_until = time.time() + float(open_for)

class AgentGraphBridge:
    """
    Shared tool bridge with:
      - register_tool(name, fn)
      - execute_tool(name, args, policy_override=None) -> {'status', 'result'|'error'}
    Features:
      - Timeouts per call
      - Retries with backoff + jitter
      - Simple per-tool circuit breaker (consecutive failures)
    """
    
    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS, default_policy: Optional[Dict[str, Any]] = None):
        """Initialize the graph bridge with thread pool and tool registration."""
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._tool_registry: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._breakers: Dict[str, _Breaker] = {}
        self._default_policy = dict(DEFAULT_POLICY)
        if default_policy:
            self._default_policy.update(default_policy)
        self.tool_wrappers = GraphToolWrapper()
        self.available_tools = self._check_available_tools()
        self._register_all_tools()
    
    def _check_available_tools(self) -> Dict[str, bool]:
        """Check which tools are available and return availability status."""
        return {
            "interpreter": self.tool_wrappers.wrap_interpreter_tool() is not None,
            "city_recommender": self.tool_wrappers.wrap_city_recommender_tool()[0] is not None,
            "poi_discovery": self.tool_wrappers.wrap_poi_discovery_tool()[0] is not None,
            "restaurants_discovery": self.tool_wrappers.wrap_restaurants_discovery_tool()[0] is not None,
            "city_fare": self.tool_wrappers.wrap_city_fare_tool()[0] is not None,
            "intercity_fare": self.tool_wrappers.wrap_intercity_fare_tool()[0] is not None,
            "currency": self.tool_wrappers.wrap_currency_tool()[0] is not None,
            "discoveries_costs": self.tool_wrappers.wrap_discoveries_costs_tool() is not None,
            "city_graph": self.tool_wrappers.wrap_city_graph_tool() is not None,
            "optimizer": self.tool_wrappers.wrap_optimizer_tool() is not None,
            "trip_maker": self.tool_wrappers.wrap_trip_maker_tool() is not None,
            "writer_report": self.tool_wrappers.wrap_writer_report_tool() is not None,
            "exporter": self.tool_wrappers.wrap_exporter_tool() is not None,
            "gap_data": self.tool_wrappers.wrap_gap_data_tool() is not None
        }
    
    def _register_all_tools(self):
        """Register all available tools for execution using proper wrappers."""
        # Register interpreter
        interpreter_tool = self.tool_wrappers.wrap_interpreter_tool()
        if interpreter_tool:
            self.register_tool("interpreter", lambda args: {
                "status": "success", 
                "result": interpreter_tool(args.get("user_request", ""))
            })
        
        # Use the proper tool wrappers from tools_to_agent.py
        try:
            # Import the wrapper functions directly
            from app.tools.bridge.tools_to_agent import (
                city_recommender_wrapper,
                currency_wrapper,
                city_fare_wrapper,
                intercity_fare_wrapper,
                poi_discovery_wrapper,
                restaurants_discovery_wrapper,
                discoveries_costs_wrapper,
                city_graph_wrapper,
                optimizer_wrapper,
                trip_maker_wrapper,
                writer_report_wrapper,
                gap_data_wrapper
            )
            
            # Register the wrappers
            self.register_tool("city_recommender", city_recommender_wrapper)
            self.register_tool("currency", currency_wrapper)
            self.register_tool("city_fare", city_fare_wrapper)
            self.register_tool("intercity_fare", intercity_fare_wrapper)
            self.register_tool("poi_discovery", poi_discovery_wrapper)
            self.register_tool("restaurants_discovery", restaurants_discovery_wrapper)
            self.register_tool("discoveries_costs", discoveries_costs_wrapper)
            self.register_tool("city_graph", city_graph_wrapper)
            self.register_tool("optimizer", optimizer_wrapper)
            self.register_tool("trip_maker", trip_maker_wrapper)
            self.register_tool("writer_report", writer_report_wrapper)
            self.register_tool("gap_data", gap_data_wrapper)
            
        except ImportError as e:
            # Basic registration fallback
            self._register_basic_tools()
    
    def _register_basic_tools(self):
        """Basic tool registration fallback when advanced wrappers are not available."""
        # Register city recommender
        city_tool, city_args = self.tool_wrappers.wrap_city_recommender_tool()
        if city_tool and city_args:
            def city_wrapper(args):
                try:
                    city_args_obj = city_args(**args)
                    result = city_tool(city_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("city_recommender", city_wrapper)
        
        # Register POI discovery
        poi_tool, poi_args = self.tool_wrappers.wrap_poi_discovery_tool()
        if poi_tool and poi_args:
            def poi_wrapper(args):
                try:
                    poi_args_obj = poi_args(**args)
                    result = poi_tool(poi_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("poi_discovery", poi_wrapper)
        
        # Register restaurant discovery
        rest_tool, rest_args = self.tool_wrappers.wrap_restaurants_discovery_tool()
        if rest_tool and rest_args:
            def rest_wrapper(args):
                try:
                    rest_args_obj = rest_args(**args)
                    result = rest_tool(rest_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("restaurants_discovery", rest_wrapper)
        
        # Register city fare
        city_fare_tool, city_fare_args = self.tool_wrappers.wrap_city_fare_tool()
        if city_fare_tool and city_fare_args:
            def city_fare_wrapper(args):
                try:
                    city_fare_args_obj = city_fare_args(**args)
                    result = city_fare_tool(city_fare_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("city_fare", city_fare_wrapper)
        
        # Register intercity fare
        intercity_tool, intercity_args = self.tool_wrappers.wrap_intercity_fare_tool()
        if intercity_tool and intercity_args:
            def intercity_wrapper(args):
                try:
                    intercity_args_obj = intercity_args(**args)
                    result = intercity_tool(intercity_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("intercity_fare", intercity_wrapper)
        
        # Register currency tool
        currency_tool, currency_args = self.tool_wrappers.wrap_currency_tool()
        if currency_tool and currency_args:
            def currency_wrapper(args):
                try:
                    currency_args_obj = currency_args(**args)
                    result = currency_tool(currency_args_obj)
                    return {"status": "success", "result": result.model_dump() if hasattr(result, 'model_dump') else result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("currency", currency_wrapper)
        
        # Register discoveries costs tool
        discoveries_tool = self.tool_wrappers.wrap_discoveries_costs_tool()
        if discoveries_tool:
            def discoveries_wrapper(args):
                try:
                    # Create a mock AppState for the tool
                    class MockAppState:
                        def __init__(self, data):
                            self.request = data  # The tool expects state.request
                            self.itinerary = {}
                            self.caps = {}
                            self.meta = {}
                            self.logs = []
                            self.done = False
                            self.run_id = ""
                            self.mode = "structured"
                            # Add any other attributes from data
                            for key, value in data.items():
                                if not hasattr(self, key):
                                    setattr(self, key, value)
                    mock_state = MockAppState(args)
                    result = discoveries_tool(mock_state)
                    return {"status": "success", "result": result.__dict__ if hasattr(result, '__dict__') else str(result)}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("discoveries_costs", discoveries_wrapper)
        
        # Register optimizer tool
        optimizer_tool = self.tool_wrappers.wrap_optimizer_tool()
        if optimizer_tool:
            def optimizer_wrapper(args):
                try:
                    class MockAppState:
                        def __init__(self, data):
                            self.request = data  # The tool expects state.request
                            self.itinerary = {}
                            self.caps = {}
                            self.meta = {}
                            self.logs = []
                            self.done = False
                            self.run_id = ""
                            self.mode = "structured"
                            # Add any other attributes from data
                            for key, value in data.items():
                                if not hasattr(self, key):
                                    setattr(self, key, value)
                    mock_state = MockAppState(args)
                    result = optimizer_tool(mock_state)
                    return {"status": "success", "result": result.__dict__ if hasattr(result, '__dict__') else str(result)}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("optimizer", optimizer_tool)
        
        # Register gap data tool
        gap_tool = self.tool_wrappers.wrap_gap_data_tool()
        if gap_tool:
            def gap_wrapper(args):
                try:
                    result, patches = gap_tool(args)
                    return {"status": "success", "result": result, "patched": patches}
                except Exception as e:
                    return {"status": "error", "error": str(e)}
            self.register_tool("gap_data", gap_wrapper)
        

    # ------------ registration & policy ------------
    def register_tool(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a tool function with the bridge."""
        self._tool_registry[name] = fn
        if name not in self._breakers:
            self._breakers[name] = _Breaker()

    def set_policy(self, name: str, policy: Dict[str, Any]) -> None:
        """Set execution policy for a specific tool."""
        p = dict(self._default_policy)
        p.update(policy or {})
        self._policies[name] = p

    def _policy_for(self, name: str, override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get execution policy for a tool with overrides applied."""
        base = dict(self._default_policy)
        if name in self._policies:
            base.update(self._policies[name])
        if override:
            base.update(override)
        return base

    # ------------ execution ------------
    def execute_tool(self, name: str, args: Optional[Dict[str, Any]] = None, policy_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a registered tool with retries, timeout, and circuit breaker protection."""
        if name not in self._tool_registry:
            return {"status": "error", "error": f"unknown_tool:{name}"}

        policy = self._policy_for(name, policy_override)
        breaker = self._breakers.get(name) or _Breaker()
        self._breakers[name] = breaker

        if breaker.is_open():
            return {"status": "skipped", "error": "circuit_open"}

        fn = self._tool_registry[name]
        tries = int(policy.get("retries", 0)) + 1
        timeout = float(policy.get("timeout_sec", 45))
        base_backoff = float(policy.get("base_backoff_sec", 1.0))
        jitter = float(policy.get("backoff_jitter_sec", 0.3))
        threshold = int(policy.get("circuit_fail_threshold", 3))
        open_for = float(policy.get("circuit_open_sec", 60))

        last_err: Optional[str] = None

        for attempt in range(1, tries + 1):
            try:
                fut = self._pool.submit(fn, args or {})
                res = fut.result(timeout=timeout)  # may raise FuturesTimeout
                # Expect the wrapper already returns {'status':...}
                if not isinstance(res, dict) or "status" not in res:
                    raise RuntimeError("tool_return_shape_invalid")

                if res.get("status") == "success":
                    breaker.record_success()
                    return res

                # Non-success: treat as failure for breaker, but pass result through on last try
                last_err = res.get("error") or "tool_error"
                if attempt >= tries:
                    breaker.record_failure(threshold, open_for)
                    return {"status": res.get("status", "error"), "error": last_err, "result": res.get("result")}
                # backoff then retry
                self._sleep_backoff(base_backoff, jitter, attempt)
                continue

            except FuturesTimeout:
                last_err = "timeout"
            except Exception as e:
                last_err = f"runtime:{e}"

            if attempt >= tries:
                breaker.record_failure(threshold, open_for)
                return {"status": "error", "error": last_err}
            self._sleep_backoff(base_backoff, jitter, attempt)

        # Should not reach here
        breaker.record_failure(threshold, open_for)
        return {"status": "error", "error": last_err or "unknown_error"}

    @staticmethod
    def _sleep_backoff(base: float, jitter: float, attempt: int) -> None:
        """Implement exponential backoff with jitter for retry delays."""
        # exponential backoff with jitter
        delay = (base * (2 ** (attempt - 1))) + random.uniform(-jitter, jitter)
        if delay < 0.05:
            delay = 0.05
        time.sleep(delay)
