# Core API Keys (REQUIRED)
eb setenv OPENAI_API_KEY="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"
eb setenv TAVILY_API_KEY="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"
eb setenv MONGODB_URI="mongodb+srv://stavos114_db_user:dgtOtRZs3MimkTcK@cluster0.bzqyrad.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
eb setenv MONGO_URI="mongodb+srv://stavos114_db_user:dgtOtRZs3MimkTcK@cluster0.bzqyrad.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# Application Configuration
eb setenv ENVIRONMENT="production"
eb setenv DEBUG="false"
eb setenv SLA_SECONDS="300"

# MongoDB Configuration
eb setenv MONGODB_DB="agent_memory"
eb setenv RUNS_COLLECTION="runs"

# OpenAI Model (optional - defaults to gpt-4o-mini)
eb setenv OPENAI_MODEL="gpt-4o-mini"

