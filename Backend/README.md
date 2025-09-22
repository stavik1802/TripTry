# TripPlanner Backend

A sophisticated multi-agent system for intelligent trip planning, built with Python, FastAPI, and LangGraph.

## 🚀 Features

- **Multi-Agent Architecture** - Specialized agents for planning, research, budgeting, and output
- **LangGraph Integration** - Stateful workflow orchestration
- **MongoDB Storage** - Persistent memory and conversation history
- **FastAPI Framework** - High-performance async API
- **OpenAI Integration** - GPT models for natural language processing
- **Tavily Search** - Real-time web search capabilities
- **Session Management** - Isolated user sessions with shared memory
- **Health Monitoring** - Comprehensive health checks and debugging endpoints

## 🛠️ Tech Stack

- **Python 3.9+** - Core language
- **FastAPI** - Web framework
- **LangGraph** - Multi-agent orchestration
- **MongoDB** - Database and memory storage
- **OpenAI** - AI/LLM integration
- **Tavily** - Web search API
- **Pydantic** - Data validation
- **Uvicorn/Gunicorn** - ASGI server

## 📦 Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 🏃‍♂️ Development

```bash
# Start development server
python -m uvicorn app.server:app --reload --port 8000

# Or use the main entry point
python app/main.py

# Test imports
python test_imports.py
```

## 🌐 Environment Configuration

Create a `.env` file in the `Backend/` directory:

```env
# Required API Keys
OPENAI_API_KEY=sk-your-openai-key
TAVILY_API_KEY=tvly-your-tavily-key

# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/agent_memory
MONGODB_DB=agent_memory

# Optional Configuration
OPENAI_MODEL=gpt-4o-mini
ENVIRONMENT=development
DEBUG=true
SLA_SECONDS=300
LOG_LEVEL=INFO
```

## 📁 Project Structure

```
Backend/
├── app/
│   ├── agents/              # Agent implementations
│   │   ├── base_agent.py           # Base agent class
│   │   ├── planning_agent.py       # Trip planning logic
│   │   ├── reasearch_agent.py      # Research and discovery
│   │   ├── budget_agent.py         # Budget calculations
│   │   ├── gap_agent.py           # Gap analysis
│   │   ├── output_agent.py        # Response formatting
│   │   ├── learning_agent.py      # Learning and adaptation
│   │   └── utils/                 # Agent utilities
│   │       ├── memory_system.py   # Memory management
│   │       ├── multi_agent_system.py
│   │       └── graph_integration.py
│   ├── core/                # Core system components
│   │   ├── advanced_multi_agent_system.py  # Main orchestrator
│   │   ├── coordinator_graph.py           # LangGraph workflow
│   │   └── common_schema.py              # Shared data models
│   ├── database/            # Database layer
│   │   └── mongo_store.py          # MongoDB operations
│   ├── tools/               # Tool implementations
│   │   ├── discovery/              # Discovery tools
│   │   ├── planning/               # Planning tools
│   │   ├── pricing/                # Pricing tools
│   │   ├── export/                 # Export tools
│   │   ├── gap_patch/              # Gap analysis tools
│   │   ├── interpreter/            # NLP interpretation
│   │   └── bridge/                 # Tool-to-agent bridge
│   ├── server.py            # FastAPI application
│   ├── main.py              # Development entry point
│   ├── config.py            # Configuration management
│   └── boot.py              # Bootstrap utilities
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container configuration
└── mongo-init.js           # MongoDB initialization
```

## 🤖 Multi-Agent System

The system uses specialized agents working together:

### Agent Roles

1. **Planning Agent** (`planning_agent.py`)
   - Interprets user requests
   - Creates tool execution plans
   - Manages conversation context

2. **Research Agent** (`reasearch_agent.py`)
   - Discovers cities and destinations
   - Finds points of interest
   - Searches for restaurants and activities

3. **Budget Agent** (`budget_agent.py`)
   - Calculates trip costs
   - Manages currency conversions
   - Optimizes budget allocation

4. **Gap Agent** (`gap_agent.py`)
   - Identifies missing information
   - Suggests improvements
   - Fills data gaps

5. **Output Agent** (`output_agent.py`)
   - Formats final responses
   - Creates trip summaries
   - Generates exportable content

6. **Learning Agent** (`learning_agent.py`)
   - Learns from user preferences
   - Improves recommendations
   - Adapts to user behavior

### Workflow Orchestration

The system uses LangGraph for stateful workflow management:

```python
# Workflow: Planning → Research → Budget → Gap → Output → Learning
graph = StateGraph(AgentState)
graph.add_node("planning", planning_agent_node)
graph.add_node("research", research_agent_node)
graph.add_node("budget", budget_agent_node)
graph.add_node("gap", gap_agent_node)
graph.add_node("output", output_agent_node)
graph.add_node("learning", learning_agent_node)
```

## 🗄️ Database Schema

### MongoDB Collections

1. **`runs`** - Trip planning sessions
   ```json
   {
     "_id": "ObjectId",
     "session_id": "string",
     "user_id": "string",
     "user_query": "string",
     "intent": "string",
     "context": "object",
     "status": "string",
     "started_at": "datetime",
     "finished_at": "datetime",
     "final": "object",
     "error": "string"
   }
   ```

2. **`memories`** - Agent memory storage
   ```json
   {
     "_id": "ObjectId",
     "session_id": "string",
     "user_id": "string",
     "memory_type": "episodic|semantic|procedural|working",
     "content": "object",
     "timestamp": "datetime",
     "metadata": "object"
   }
   ```

3. **`conversation_turns`** - Conversation history
   ```json
   {
     "_id": "ObjectId",
     "session_id": "string",
     "user_id": "string",
     "turn_number": "number",
     "user_input": "string",
     "agent_response": "string",
     "timestamp": "datetime"
   }
   ```

## 🔌 API Endpoints

### Core Endpoints

```http
# Health checks
GET /health                    # Basic health check
GET /health/db                 # Database health check

# Trip planning
POST /process                  # Main trip planning endpoint
POST /trip/export             # Export trip data

# Debug and monitoring
GET /_debug/memory_counts     # Memory usage statistics
GET /runs/latest             # Latest run information
```

### Request/Response Format

```json
// POST /process
{
  "user_request": "Plan a 5-day trip to Paris with $2000 budget",
  "user_id": "user123",
  "session_id": "session456"
}

// Response
{
  "run_id": "ObjectId",
  "status": "completed",
  "result": {
    "trip_summary": "...",
    "itinerary": [...],
    "cost_breakdown": {...}
  }
}
```

## 🧠 Memory System

The system maintains four types of memory:

1. **Episodic Memory** - Specific trip planning experiences
2. **Semantic Memory** - General knowledge about destinations
3. **Procedural Memory** - Learned planning procedures
4. **Working Memory** - Current session context

### Memory Operations

```python
# Store memory
memory_system.store_memory(
    session_id="session123",
    memory_type="episodic",
    content={"destination": "Paris", "duration": 5}
)

# Retrieve memory
memories = memory_system.get_conversation_history(
    session_id="session123"
)
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Yes | - |
| `TAVILY_API_KEY` | Tavily search API key | Yes | - |
| `MONGODB_URI` | MongoDB connection string | Yes | - |
| `MONGODB_DB` | Database name | No | `agent_memory` |
| `OPENAI_MODEL` | OpenAI model to use | No | `gpt-4o-mini` |
| `ENVIRONMENT` | Environment setting | No | `development` |
| `DEBUG` | Debug mode | No | `false` |
| `SLA_SECONDS` | Request timeout | No | `300` |
| `LOG_LEVEL` | Logging level | No | `INFO` |

### Application Settings

```python
# app/config.py
class Settings:
    openai_api_key: str
    tavily_api_key: str
    mongodb_uri: str
    mongodb_db: str = "agent_memory"
    openai_model: str = "gpt-4o-mini"
    environment: str = "development"
    debug: bool = False
    sla_seconds: int = 300
    log_level: str = "INFO"
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build individual container
docker build -t tripplanner-backend .
docker run -p 8000:8000 tripplanner-backend
```

### Production Deployment

```bash
# Using Gunicorn for production
gunicorn app.server:app -w 4 -k uvicorn.workers.UvicornWorker

# Or with Uvicorn
uvicorn app.server:app --host 0.0.0.0 --port 8000 --workers 4
```

### Elastic Beanstalk

The backend is automatically deployed to AWS Elastic Beanstalk via the main `deploy-eb.sh` script.

## 🧪 Testing

```bash
# Test imports and basic functionality
python test_imports.py

# Test the multi-agent system
python -c "
from app.core.advanced_multi_agent_system import AdvancedMultiAgentSystem
system = AdvancedMultiAgentSystem()
result = system.process_request('Plan a 5-day trip to Paris with $2000 budget')
print(result)
"

# Test API endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"user_request": "Plan a trip to Tokyo", "user_id": "test123"}'
```

## 🐛 Troubleshooting

### Common Issues

**MongoDB Connection Failed:**
```bash
# Check MongoDB is running
docker-compose ps
# Check connection string
echo $MONGODB_URI
```

**OpenAI API Errors:**
```bash
# Verify API key
echo $OPENAI_API_KEY
# Check API quota and billing
```

**Agent Workflow Stuck:**
```bash
# Check logs for agent status
tail -f logs/app.log
# Use debug endpoints
curl http://localhost:8000/_debug/memory_counts
```

### Debug Endpoints

```bash
# Memory usage
GET /_debug/memory_counts

# Latest runs
GET /runs/latest

# Database health
GET /health/db
```

## 📊 Monitoring

### Health Checks

- **`/health`** - Basic application health
- **`/health/db`** - Database connectivity and read/write tests
- **`/_debug/memory_counts`** - Memory usage statistics

### Logging

The application uses structured logging with different levels:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 🔒 Security

- **API Key Management** - Environment variables for sensitive data
- **Input Validation** - Pydantic models for request validation
- **Rate Limiting** - Built into FastAPI and can be extended
- **CORS Configuration** - Configurable for frontend integration

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [MongoDB Python Driver](https://pymongo.readthedocs.io/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)

## 🤝 Contributing

1. Follow Python PEP 8 style guidelines
2. Add type hints to all functions
3. Include docstrings for classes and methods
4. Write tests for new functionality
5. Update documentation for API changes

## 📄 License

This project is part of the TripPlanner application. See the main project README for license information.
