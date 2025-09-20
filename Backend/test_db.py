# test_mongo.py
import os, sys
from pymongo import MongoClient

uri = os.environ.get("MONGODB_URI")
if not uri:
    print("MONGODB_URI is not set"); sys.exit(1)

print("Using URI prefix:", uri.split('@')[0])  # don't print full uri

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
print(client.admin.command("ping"))  # should return {'ok': 1.0}
print("Connected to:", client.topology_description.topology_type_name)
