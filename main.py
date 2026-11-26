
import chromadb

# 1. Create a persistent client
client = chromadb.HttpClient(
    host="localhost",
    port=8000
)

# 2. Create or retrieve a collection
collection = client.get_or_create_collection(
    name="questions"
)

# 3. Insert documents
collection.add(
    ids=["q4", "q3", "q2"],
    documents=[
        "how to inverse a python list",
        "how to invert an array in python",
        "how to create a database in mongodb"
    ],
    metadatas=[
        {"category": "python"},
        {"category": "python"},
        {"category": "mongodb"}
    ]
)

print("# 4. Retrieve everything")
results1 = collection.get()
print(results1)

print('# 5. Retrieve a specific document')
result2 = collection.get(ids=["q2"])
print(result2)

print('# 6. Semantic search')
result3 = collection.query(
    query_texts=["how can i put a python list in the reversed order?"],
    n_results=2
)
print('dsadas')
print(result3["documents"])
print(result3["distances"])

# 7. Insert or update
collection.upsert(
    ids=["q1"],
    documents=["How to reverse a Python array?"]
)
