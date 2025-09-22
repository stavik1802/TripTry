# Core API Keys (REQUIRED)
eb setenv OPENAI_API_KEY=""
eb setenv TAVILY_API_KEY=""
eb setenv MONGODB_URI=""
eb setenv MONGO_URI=""
# Application Configuration
eb setenv ENVIRONMENT="production"
eb setenv DEBUG="false"
eb setenv SLA_SECONDS="300"

# MongoDB Configuration
eb setenv MONGODB_DB="agent_memory"
eb setenv RUNS_COLLECTION="runs"

# OpenAI Model (optional - defaults to gpt-4o-mini)
eb setenv OPENAI_MODEL="gpt-4o-mini"

