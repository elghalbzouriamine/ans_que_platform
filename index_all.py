

import chromadb
from pymongo import MongoClient
from db import get_chroma,get_mongo,get_neo4j,get_redis

dbm=get_mongo()["qa_platform"]
dbc=get_chroma()

def index_chroma(question):
    dbc.upsert(ids=[str(question["_id"])],documents=[question["title"]])


