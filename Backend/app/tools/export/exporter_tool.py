"""
Exporter Tool for TripPlanner Multi-Agent System

This tool provides a simple export completion marker for the trip planning workflow.
It serves as a final step to mark the export process as complete.

Key features:
- Simple completion marker for export workflow
- State management for export process
- Integration with the overall trip planning pipeline

The tool marks the export process as complete, signaling that all trip data
has been processed and is ready for final output.
"""

from app.tools.tools_utils.state import AppState

def exporter(state: AppState) -> AppState:
    """Mark export process as complete"""
    state.done = True
    return state
