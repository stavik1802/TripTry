from app.graph.state import AppState
def exporter(state: AppState) -> AppState:
    state.done = True
    return state
