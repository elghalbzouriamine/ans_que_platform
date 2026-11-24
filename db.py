import streamlit as st
import pymongo, redis, chromadb
from pymongo import MongoClient
import redis 
import chromadb
from neo4j import GraphDatabase
@st.cache_resource


def get_mongo():
    client = MongoClient("mongodb://localhost:27018/")
    client.admin.command("ping")
    return client

@st.cache_resource
def get_redis():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)

@st.cache_resource
def get_chroma():
    client = chromadb.HttpClient(host="localhost", port=8000)
    return client.get_or_create_collection("qa_questions", metadata={"hnsw:space": "cosine"},)


uri="neo4j://localhost:7687"
username="neo4j"
password="password123"

driver=GraphDatabase.driver(uri,auth=(username,password))
def get_neo4j():
    driver.verify_connectivity()




