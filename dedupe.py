"""
dedupe.py - remove questions with the same title (case/space-insensitive).

For each group of duplicates it KEEPS one question (the one with the most answers,
ties broken by oldest created_at) and deletes the others together with:
  * their answers in Mongo
  * their Redis vote keys, and subtracts those votes from the leaderboard
  * their documents in Chroma (qa_questions)

Only EXACT same titles are touched. Near-duplicates ("How do I undo the last commit"
vs "How can I revert my latest commit") are different strings, so they are kept.

Run:  python dedupe.py            -> dry run, only prints what it would delete
      python dedupe.py --apply    -> actually deletes
"""
import sys
import redis
import chromadb
from pymongo import MongoClient

APPLY = "--apply" in sys.argv

db = MongoClient("mongodb://localhost:27018")["qa_platform"]
questions, answers, users = db["questions"], db["answers"], db["users"]
r = redis.Redis(host="localhost", port=6379, decode_responses=True)
col = chromadb.HttpClient(host="localhost", port=8000).get_or_create_collection("qa_questions")

# 1) groups of questions sharing the same normalized title
groups = list(questions.aggregate([
    {"$group": {
        "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$title", ""]}}}},
        "ids": {"$push": "$_id"},
        "n": {"$sum": 1},
    }},
    {"$match": {"n": {"$gt": 1}}},
], allowDiskUse=True))

# 2) number of answers per question
answer_count = {d["_id"]: d["n"] for d in answers.aggregate([
    {"$group": {"_id": "$question_id", "n": {"$sum": 1}}}
])}

to_delete = []
for g in groups:
    docs = list(questions.find({"_id": {"$in": g["ids"]}}, {"created_at": 1}))
    # most answers first, then oldest
    docs.sort(key=lambda d: (-answer_count.get(d["_id"], 0), d.get("created_at") or 0))
    to_delete.extend(d["_id"] for d in docs[1:])

dup_answers = list(answers.find({"question_id": {"$in": to_delete}}, {"author_id": 1}))

print(f"duplicate title groups : {len(groups)}")
print(f"questions to delete    : {len(to_delete)}")
print(f"answers to delete      : {len(dup_answers)}")

if not APPLY:
    print("Dry run only. Re-run with --apply to delete.")
    sys.exit(0)

if not to_delete:
    print("Nothing to do.")
    sys.exit(0)

# 3) Redis: remove vote keys and fix the leaderboard
username_of = {u["_id"]: u["username"] for u in users.find({}, {"username": 1})}
pipe = r.pipeline()
for a in dup_answers:
    key = f"answer:{a['_id']}:votes"
    votes = int(r.get(key) or 0)
    name = username_of.get(a["author_id"])
    if name and votes:
        pipe.zincrby("leaderboard", -votes, name)
    pipe.delete(key, f"answer:{a['_id']}:voters")
pipe.execute()

# 4) Chroma: delete in batches (ids are str(_id))
ids = [str(i) for i in to_delete]
for i in range(0, len(ids), 5000):
    col.delete(ids=ids[i:i + 5000])

# 5) Mongo last
answers.delete_many({"question_id": {"$in": to_delete}})
questions.delete_many({"_id": {"$in": to_delete}})

print(f"Done. Questions left: {questions.count_documents({})}  Chroma count: {col.count()}")
