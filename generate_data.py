# seed_mongo.py
import random
from datetime import timedelta
from faker import Faker
from pymongo import MongoClient

fake = Faker()
Faker.seed(42)
random.seed(42)

N_USERS, N_QUESTIONS = 500, 3000   # answers: ~2 per question => ~6000

TAGS = ["python", "mongodb", "redis", "neo4j", "docker", "sql", "javascript",
        "machine-learning", "linux", "git", "api", "pandas", "kubernetes", "java"]

# Templates make questions realistic and give you near-duplicates
# to test similar-question detection later.
TEMPLATES = [
    "How do I {a} in {t}?",
    "What is the best way to {a} with {t}?",
    "Why does {t} fail when I try to {a}?",
    "Can't {a} in {t}, what am I doing wrong?",
]
ACTIONS = ["connect to a database", "handle errors", "optimize queries", "install dependencies",
           "deploy to production", "run tests", "read a file", "parse JSON", "set up authentication",
           "cache results", "schedule a job", "scale horizontally"]

client = MongoClient("mongodb://localhost:27018")
db = client["qa_platform"]
for c in ("users", "questions", "answers"):
    db[c].drop()

# ---- users ----
users = [{
    "_id": i,
    "username": fake.unique.user_name(),
    "email": fake.unique.email(),
  
    "tags_expertise": random.sample(TAGS, k=random.randint(1, 3)),
} for i in range(1, N_USERS + 1)]
db.users.insert_many(users)

# ---- questions ----
questions = []
for i in range(1, N_QUESTIONS + 1):
    tags = random.sample(TAGS, k=random.randint(1, 3))
    created = fake.date_time_between(start_date="-6m", end_date="now")
    questions.append({
        "_id": i,
        "title": random.choice(TEMPLATES).format(a=random.choice(ACTIONS), t=tags[0]),
        "body": fake.paragraph(nb_sentences=5),
        "tags": tags,
        "author_id": random.randint(1, N_USERS),
        "created_at": created,
        "views": random.randint(0, 5000),
    })
db.questions.insert_many(questions)

# ---- answers ----
answers, aid = [], 1
for q in questions:
    for _ in range(random.randint(0, 4)):
        answers.append({
    "_id": aid,
    "question_id": q["_id"],
    "author_id": random.randint(1, N_USERS),
    "body": fake.paragraph(nb_sentences=random.randint(2, 6)),
    "created_at": q["created_at"] + timedelta(minutes=random.randint(5, 20000)),
    "accepted": False,
    "votes": max(0, int(random.gauss(5, 8))),   # most low, a few high
})
        aid += 1
db.answers.insert_many(answers)

# useful indexes
db.questions.create_index("tags")
db.questions.create_index("author_id")
db.answers.create_index("question_id")

print(db.users.count_documents({}), db.questions.count_documents({}), db.answers.count_documents({}))