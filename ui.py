import streamlit as st
import bcrypt
from db import get_mongo, get_redis, get_chroma
from datetime import datetime, timezone
from questionCard import question_card
from answerCard import answer_card
import random
from bson import ObjectId

import redis_integration as rv   # add with the other imports

# after: answers = db["answers"]
     # fills Redis from the seeded votes (runs once)


mongo = get_mongo()
db = mongo["qa_platform"]

users = db["users"]
questions = db["questions"]
answers = db["answers"]



if "browse_questions" not in st.session_state:
    browse_questions = list(
        questions.find().sort("created_at", -1).limit(20)
    )
    random.shuffle(browse_questions)
    st.session_state.browse_questions = browse_questions


# Ensure usernames are unique
users.create_index("username", unique=True)

st.title("QA Platform")

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if not st.session_state.user_id:

    with st.form("auth"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button("Continue")

    if submitted:
        if not username or not password:
            st.error("Fill in both fields.")

        else:
            user = users.find_one({"username": username})

            if user:
                # Existing user: verify password
                if bcrypt.checkpw(
                    password.encode(),
                    user["password"]
                ):
                    st.session_state.user_id = user["_id"]
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Incorrect password.")

            else:
                # New user: register
                hashed_password = bcrypt.hashpw(
                    password.encode(),
                    bcrypt.gensalt()
                )

                result = users.insert_one({
                    "username": username,
                    "password": hashed_password
                })

                st.session_state.user_id = result.inserted_id
                st.session_state.username = username

                st.success("Account created!")
                st.rerun()

else:
    st.sidebar.success(
        f"Welcome, {st.session_state.username}"
    )

    tab_ask, tab_browse, tab_rank ,tab_profile= st.tabs(
        ["Ask", "Browse", "Leaderboard","Profile"]
    )

    with tab_ask:
        st.header("Ask a question")
        title = st.text_input("Question title")
        content = st.text_area("Describe your question")
        tags=st.text_input("enter the tags")
     

        if st.button("Submit"):
            st.write("Question submitted!")
            result = questions.insert_one({
                                "title":title,
                                "body":content,
                                "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
                                "author_id":st.session_state.user_id,
                                "created_at":datetime.now(timezone.utc),
                            })
            st.session_state.browse_questions = list(
                questions.find().sort("created_at", -1).limit(20)
            )

            random.shuffle(st.session_state.browse_questions)
            st.success(f"Question published! ID: {result.inserted_id}")
        
    with tab_browse:
        st.header("Browse questions")
        search = st.text_input("🔍 Search questions by title", placeholder="Search...")
        if st.button("Find"):
            if search.strip():
                c =get_chroma()
                result=c.query(query_texts=[search],n_results=5)
                question_id=result["ids"][0]
                for qid in question_id:
                    _id = int(qid) if qid.isdigit() else ObjectId(qid)
                    question=questions.find_one({"_id":_id})
                    if question:
                        question_card(question, users, answers)
            else:
                st.warning("enter a a question!!!")
               
        for question in st.session_state.browse_questions:
                            question_card(question, users, answers)
        

        
          

    with tab_profile:
        st.header("My Profile")
        st.subheader("My Questions")
        res=questions.find({"author_id":st.session_state.user_id})
        for question in res:
            question_card(question,users,answers,show_answer=False)
        st.divider()
        st.subheader("My Answers")
        res1 = answers.find({
        "author_id": st.session_state.user_id
    })

        for answer in res1:
            q=questions.find_one({"_id":answer.get("question_id")})
            if q:
                au=users.find_one({"_id":q.get("author_id")})
                uname = au["username"] if au else "Anonymous"

                with st.container(border=True):

                    st.markdown(f"**Question:** {q.get('title', 'Untitled')}")

                    st.caption(f"Asked by: {uname}")

                    st.divider()

                    st.markdown("**Your answer:**")

                    st.write(answer.get("body", ""))
                
            

    with tab_rank:
        st.header("Leaderboard")
        s=rv.leaderboard(10)
        for i in range(len(s)):
            username,score=s[i]
            st.write(f"#{i+1}_{username} --- {int(score)} points")

