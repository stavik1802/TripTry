# TripPlanner Multi-Agent System

A sophisticated AI-powered trip planning system that uses multiple specialized agents to create comprehensive, personalized travel itineraries.

## 🌟 Features

### 🤖 Multi-Agent Architecture
- **Planning Agent**: Interprets natural language requests and creates execution plans
- **Research Agent**: Discovers cities, POIs, restaurants, and transportation options
- **Gap Agent**: Identifies and fills missing data using web search
- **Budget Agent**: Optimizes costs and creates detailed financial breakdowns
- **Output Agent**: Generates human-readable responses and reports
- **Learning Agent**: Learns from interactions and improves over time

### 🛠️ Advanced Capabilities
- **Natural Language Processing**: Understands complex travel requests
- **Real-time Data**: Web search integration for current information
- **Cost Optimization**: Intelligent budget planning and cost estimation
- **Gap Detection**: Automatically identifies and fills missing data
- **Memory System**: Persistent learning and conversation history
- **Multi-format Output**: JSON, Markdown, HTML, and text reports
- **Modern Web UI**: React-based multi-session chat interface
- **Responsive Design**: Works on desktop and mobile devices

## 🏗️ Architecture


### Agent Coordination Graph

The following diagram illustrates the end-to-end agent workflow, including retries, SLA shortcuts, gap detection/filling, and error handling.

![Agent Coordination Graph](Backend/assets/agent_workflow.png)


### Core Components

#### 🧠 Core System (`Backend/app/core/`)
- **`advanced_multi_agent_system.py`**: Main orchestrator with LangGraph integration
- **`coordinator_graph.py`**: Agent coordination and workflow management
- **`common_schema.py`**: Standardized data structures and validation

#### 🤖 Agents (`Backend/app/agents/`)
- **`base_agent.py`**: Foundation framework for all agents
- **`planning_agent.py`**: Request interpretation and planning
- **`reasearch_agent.py`**: Data discovery and collection
- **`gap_agent.py`**: Missing data identification and filling
- **`budget_agent.py`**: Cost calculation and optimization
- **`output_agent.py`**: Response generation and formatting
- **`learning_agent.py`**: System improvement and adaptation

#### 🛠️ Tools (`Backend/app/tools/`)
- **Discovery Tools**: City recommendations, POI discovery, restaurant finding
- **Pricing Tools**: City fares, intercity transportation, currency conversion
- **Planning Tools**: Cost calculation, city graphs, optimization, trip creation
- **Export Tools**: Report generation and data export
- **Interpreter**: Natural language request processing

#### 🎨 Frontend (`trip_ui/`)
- **React 18**: Modern React with TypeScript
- **Multi-Session Chat**: Multiple conversation sessions
- **Real-time Updates**: Live trip planning progress
- **Responsive Design**: Tailwind CSS styling
- **API Integration**: Seamless backend communication

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ (3.10+ recommended for type hints)
- Node.js 18+ (for frontend)
- Docker & Docker Compose (for containerized deployment)
- MongoDB (included in Docker setup)

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TripPlanner
   ```

2. **Set up environment variables**
   ```bash
   cp Backend/.env.example Backend/.env
   # Edit Backend/.env with your API keys
   ```

3. **Required API Keys**
   ```env
   OPENAI_API_KEY=your_openai_api_key
   TAVILY_API_KEY=your_tavily_api_key
   MONGO_URI=mongodb://admin:password123@localhost:27017/agent_memory
   ```


### Development Setup

#### Option 1: Docker (Recommended)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Option 2: Local Development
```bash
# Backend setup
cd Backend
pip install -r requirements.txt
python -m uvicorn app.server:app --reload --port 8000

# Frontend setup (in another terminal)
cd trip_ui
npm install
npm run dev
```

### Testing
```bash
# Test all imports
cd Backend
python test_imports.py

# Run the system
python -c "
from app.core.advanced_multi_agent_system import AdvancedMultiAgentSystem
system = AdvancedMultiAgentSystem()
result = system.process_request('Plan a 5-day trip to Paris with $2000 budget')
print(result)
"
```

## 📖 Usage

### API Endpoints

#### Main Trip Planning
```http
POST /trip/plan
Content-Type: application/json

{
  "query": "Plan a 5-day trip to Paris with $2000 budget",
  "user_id": "user123",
  "session_id": "session456"
}
```

#### Health Check
```http
GET /health
```

#### Memory Management
```http
GET /_debug/memory_counts
GET /_debug/system_status
```

### Example Requests

#### Basic Trip Planning
```json
{
  "query": "I want to visit Tokyo for 7 days with a budget of $3000",
  "user_id": "user123"
}
```

#### Multi-City Trip
```json
{
  "query": "Plan a 2-week Europe trip visiting Paris, Rome, and Barcelona with $5000",
  "user_id": "user123"
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI responses | Yes | - |
| `TAVILY_API_KEY` | Tavily API key for web search | Yes | - |
| `MONGO_URI` | MongoDB connection string | Yes | - |
| `SLA_SECONDS` | Service Level Agreement timeout | No | 300 |
| `LOG_LEVEL` | Logging level | No | INFO |
| `DEBUG` | Debug mode | No | false |

## 🏭 Production Deployment

### AWS Elastic Beanstalk (Recommended)
```bash
# Deploy to AWS Elastic Beanstalk (handles everything automatically)
eb init
./set_env.sh (make sure to insert keys in this)
./deploy-eb.sh
```

**What `deploy-eb.sh` does:**
- Builds the React frontend for production
- Deploys both frontend and backend to Elastic Beanstalk
- Provides the live URL after successful deployment
- Handles all configuration automatically

**Elastic Beanstalk Configuration:**
- **Platform**: Python 3.9
- **Instance Type**: t3.medium (recommended)
- **Environment**: Web server environment
- **Health Check**: `/health` endpoint
- **Auto Scaling**: Enabled with min 1, max 10 instances
- **URL**: Automatically provided by EB (e.g., `your-app.region.elasticbeanstalk.com`)

**Setting Environment Variables on EB:**

After initial deployment, you need to set your API keys and configuration:

```bash
# Option 1: Use the provided script (recommended)
./set_env.sh

# Option 2: Set manually
eb setenv OPENAI_API_KEY="sk-your-openai-key"
eb setenv TAVILY_API_KEY="tvly-your-tavily-key"
eb setenv MONGODB_URI="mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
eb setenv MONGODB_DB="agent_memory"
eb setenv ENVIRONMENT="production"
eb setenv DEBUG="false"
eb setenv SLA_SECONDS="300"
```

**Required Environment Variables:**
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `TAVILY_API_KEY` - Your Tavily API key (required for web search)
- `MONGODB_URI` - MongoDB connection string (required)
- `MONGODB_DB` - Database name (default: "agent_memory")

**Optional Environment Variables:**
- `OPENAI_MODEL` - OpenAI model to use (default: "gpt-4o-mini")
- `ENVIRONMENT` - Environment setting (default: "production")
- `DEBUG` - Debug mode (default: "false")
- `SLA_SECONDS` - Request timeout (default: "300")

### Docker Deployment
```bash
# Production build
docker-compose -f docker-compose.prod.yml up -d

# Scale backend
docker-compose up -d --scale backend=3
```

### Frontend Deployment
```bash
# Frontend is automatically built and deployed with the backend via deploy-eb.sh
# The script handles:
# 1. Building React app for production
# 2. Integrating with backend API
# 3. Deploying to Elastic Beanstalk
# 4. Providing the live URL

# For standalone frontend deployment (if needed):
cd trip_ui
npm ci
npm run build
# Deploy dist/ folder to any static hosting (Netlify, Vercel, S3, etc.)
```

### Health Monitoring
- Health checks: `GET /health`
- Memory usage: `GET /_debug/memory_counts`
- System status: `GET /_debug/system_status`

## 🧪 Development

### Project Structure
```
TripPlanner/
├── Backend/                 # Python backend
│   ├── app/
│   │   ├── core/           # Core system components
│   │   ├── agents/         # AI agents
│   │   ├── tools/          # External tools
│   │   ├── database/       # Data persistence
│   │   └── server.py       # FastAPI server
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile         # Backend container
│   └── test_imports.py    # Import verification
├── trip_ui/               # React frontend
│   ├── src/
│   │   ├── App.tsx        # Main app component
│   │   ├── MultiSessionApp.tsx # Multi-session chat interface
│   │   └── main.tsx       # React entry point
│   ├── package.json       # Node dependencies
│   ├── tailwind.config.js # Tailwind CSS config
│   └── Dockerfile         # Frontend container
├── docker-compose.yml     # Development setup
├── docker-compose.prod.yml # Production setup
├── deploy-eb.sh          # Elastic Beanstalk deployment
├── Procfile              # EB process configuration
└── requirements.txt      # Root Python dependencies
```

### Adding New Agents

1. **Create agent class** in `Backend/app/agents/`
2. **Implement required methods** from `BaseAgent`
3. **Register agent** in `coordinator_graph.py`
4. **Add to workflow** in the graph definition

### Adding New Tools

1. **Create tool module** in `Backend/app/tools/`
2. **Implement tool function** with proper error handling
3. **Register tool** in `tools_to_agent.py`
4. **Add to agent capabilities** as needed

### Frontend Development

#### React Components
- **`App.tsx`**: Main application entry point
- **`MultiSessionApp.tsx`**: Multi-session chat interface
- **API Integration**: Automatic backend communication
- **Styling**: Tailwind CSS for responsive design

#### Development Commands
```bash
# Install dependencies
cd trip_ui
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

#### Environment Configuration
```bash
# Frontend automatically detects API URL:
# - Development: http://localhost:8000
# - Production: Uses Elastic Beanstalk URL automatically

# Manual configuration (if needed):
VITE_API_BASE=http://localhost:8000  # Development only
REACT_APP_API_BASE=http://localhost:8000  # Alternative
```

## 🔍 Troubleshooting

### Common Issues
#### Memory Issues
```bash
# Check MongoDB connection
docker-compose logs mongodb

# Reset memory system
curl -X POST http://localhost:8000/_debug/reset_memory
```

#### Frontend Issues
```bash
# Clear node modules and reinstall
cd trip_ui
rm -rf node_modules package-lock.json
npm install

# Check API connection (development)
curl http://localhost:8000/health

# Check API connection (production)
curl https://your-app.region.elasticbeanstalk.com/health

# Build issues
npm run build --verbose
```

#### Elastic Beanstalk Issues
```bash
# Check EB status
eb status

# View logs
eb logs

# Check health
eb health

# Redeploy
eb deploy --verbose
```

### Debug Mode

Enable debug logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
python -m uvicorn app.server:app --reload
```

## 📊 Performance

### Metrics
- **Memory Usage**: ~500MB per agent instance
- **Accuracy**: 95%+ for standard trip planning requests

### Optimization
- **Caching**: Intelligent result caching with TTL
- **Parallel Processing**: Concurrent tool execution
- **Circuit Breakers**: Prevents cascading failures
- **Memory Management**: Automatic cleanup and consolidation


### Code Style
- Follow PEP 8 for Python code
- Use type hints for all functions
- Add comprehensive docstrings
- Include error handling

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LangGraph** for multi-agent coordination
- **OpenAI** for natural language processing
- **Tavily** for web search capabilities
- **FastAPI** for the web framework
- **MongoDB** for data persistence

---

**Built with ❤️ using AI agents and modern web technologies**

