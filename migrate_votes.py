from pymongo import MongoClient
import redis
import random

mongo = MongoClient("mongodb://localhost:27018")
db = mongo["qa_platform"]
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

answers = db["answers"]
users = db["users"]

user_scores = {}

for answer in answers.find():
    key = f"answer:{answer['_id']}:votes"
    current = r.get(key)

    if current is None or int(current) == 0:
        votes = random.randint(0, 30)      # fill only the empty ones
        r.set(key, votes)
    else:
        votes = int(current)               # keep the votes you already have

    author = answer["author_id"]           # keep original type (int or ObjectId)
    user_scores[author] = user_scores.get(author, 0) + votes

for author_id, score in user_scores.items():
    user = users.find_one({"_id": author_id})
    if user:
        r.zadd("leaderboard", {user["username"]: score})

print("Migration completed!")