
from pymongo import MongoClient
import redis

# Connections
mongo = MongoClient("mongodb://localhost:27018")
db = mongo["qa_platform"]

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

answers = db["answers"]
users = db["users"]

# Store total votes received by each user
user_scores = {}

for answer in answers.find():

    answer_id = str(answer["_id"])
    author_id = str(answer["author_id"])
    votes = int(answer.get("votes", 0))

    # Restore answer vote count
    r.set(f"answer:{answer_id}:votes", votes)

    # Accumulate votes for answer author
    user_scores[author_id] = (
        user_scores.get(author_id, 0) + votes
    )

# Populate leaderboard
for author_id, score in user_scores.items():

    user = users.find_one({"_id": author_id})

    if user is None:
        from bson import ObjectId
        try:
            user = users.find_one({"_id": ObjectId(author_id)})
        except Exception:
            pass

    if user:
        username = user["username"]

        r.zadd("leaderboard", {username: score})

print("Migration completed!")
