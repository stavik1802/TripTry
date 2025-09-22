// MongoDB initialization script
db = db.getSiblingDB('agent_memory');

// Create collections
db.createCollection('memories');
db.createCollection('learning_metrics');
db.createCollection('user_preferences');

// Create indexes for better performance
db.memories.createIndex({ "agent_id": 1 });
db.memories.createIndex({ "memory_type": 1 });
db.memories.createIndex({ "tags": 1 });
db.memories.createIndex({ "timestamp": 1 });
db.memories.createIndex({ "importance": 1 });

db.learning_metrics.createIndex({ "agent_id": 1, "task_type": 1 }, { unique: true });
db.learning_metrics.createIndex({ "agent_id": 1 });

db.user_preferences.createIndex({ "user_id": 1, "preference_type": 1 }, { unique: true });
db.user_preferences.createIndex({ "user_id": 1 });

print('MongoDB initialization completed');


