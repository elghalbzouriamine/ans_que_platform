from db import get_neo4j,get_redis,get_mongo

r=get_redis()

db=get_mongo()["qa_platform"]

driver=get_neo4j()

def add_question(question):
    with driver.session() as s:
        s.run("""
    MERGE (u:User {id: $author_id})
    MERGE (q:Question {id: $question_id})
    SET q.title = $title

    MERGE (u)-[:ASKED]->(q)

    WITH q
    UNWIND $tags AS tag
    MERGE (t:Tag {name: tag})
    MERGE (q)-[:HAS_TAG]->(t)
    """,
    author_id=str(question["author_id"]),
    question_id=str(question["_id"]),
    title=question.get("title", ""),
    tags=question.get("tags", []))
def add_user(user):
    with driver.session() as s:
        s.run("""
            MERGE (u:User {id: $uid})
            SET u.username = $username
        """,
            uid=str(user["_id"]),
            username=user.get("username", "Anonymous"))
def add_answer(answer):
    answer_id=answer["_id"]
    votes=r.get(f"answer:{answer_id}:votes")
    votes=int(votes) if votes is not None else 0
    with driver.session()  as s:
        s.run("""merge (u:User {id:$author_id})
        merge (q:Question{id:$question_id})
        merge (u)-[a:ANSWERED {answer_id:$aid}]->(q)
        set a.votes=$votes

        """,
        author_id=str(answer["author_id"]),
        question_id=str(answer["question_id"]),
        aid=str(answer_id),
        votes=votes
        )

def sync_neo4j():
    # 0. Users (id + username)
    for u in db.users.find():
        add_user(u)
    print("users loaded")

    # 1. Questions (create question + tag nodes)
    total_q = db.questions.count_documents({})
    for i, q in enumerate(db.questions.find(), start=1):
        add_question(q)
        if i % 500 == 0:
            print(f"questions: {i}/{total_q}")

    # 2. Answers (link users to questions, with votes)
    total_a = db.answers.count_documents({})
    for i, a in enumerate(db.answers.find(), start=1):
        add_answer(a)
        if i % 500 == 0:
            print(f"answers: {i}/{total_a}")

    print("sync finished")

def experts_for_tag(tag, limit=5):
    with driver.session() as s:
        result = s.run("""
            MATCH (u:User)-[a:ANSWERED]->(q:Question)-[:HAS_TAG]->(t:Tag {name: $tag})
            RETURN u.id AS user_id,
                   u.username AS username,
                   count(a) AS answers,
                   sum(a.votes) AS total_votes
            ORDER BY total_votes DESC, answers DESC
            LIMIT $limit
        """, tag=tag, limit=limit)
        return [record.data() for record in result]


def get_all_tags():
    with driver.session() as s:
        result = s.run("MATCH (t:Tag) RETURN t.name AS name ORDER BY name")
        return [record["name"] for record in result]

if __name__ == "__main__":
    sync_neo4j()