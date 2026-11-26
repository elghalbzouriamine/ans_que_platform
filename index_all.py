import chromadb
from pymongo import MongoClient

mongo = MongoClient("mongodb://localhost:27018")

questions = list(mongo["qa_platform"]["questions"].find())

batch_size = 5000

client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.get_or_create_collection("qa_questions")

for i in range(0, len(questions), batch_size):

    batch = questions[i:i + batch_size]

    collection.upsert(
        ids=[str(q["_id"]) for q in batch],
        documents=[q.get("title", "") for q in batch],
    )

    print(f"Indexed {min(i + batch_size, len(questions))}/{len(questions)}")

print("Total indexed:", collection.count())