from pymongo import MongoClient
from neo4j_integration import add_answer, add_question
from neo4j_integration import experts_for_tag,get_all_tags
'''
db = MongoClient("mongodb://localhost:27018")["qa_platform"]
a = db.answers.find_one()
print(a)'''
tags=get_all_tags()
print(tags)
for e in experts_for_tag("java"):
    print(e)
'''
q=db.questions.find_one({"_id":a["question_id"]})
add_question(q)
add_answer(a)
print("done")'''