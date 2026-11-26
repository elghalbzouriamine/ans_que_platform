import streamlit as st
from datetime import datetime, timezone
import redis_integration as rv
from neo4j_integration import add_answer,add_user



def answer_section(question, answers):

    question_id = str(question["_id"])

    show_answer = st.toggle(
        "💭 Write an answer", #triggeres unique toggle for each question
        key=f"answer_toggle_{question_id}"
    )

    if show_answer:

        with st.container(border=True):

            answer_text = st.text_area(
                "Your answer",
                key=f"answer_text_{question_id}",
                placeholder="Share your knowledge..."
            )

            if st.button(
                "Post answer",
                key=f"post_answer_{question_id}"#gives the button a unique identity inside Streamlit
            ):

                if not answer_text.strip():
                    st.warning("Your answer cannot be empty.")

                else:
                    a={
                        "question_id": question["_id"],
                        "author_id": st.session_state.user_id,
                        "body": answer_text.strip(),
                        "created_at": datetime.now(timezone.utc),
                        "accepted": False,
                        "votes": 0,
                    }
                    
                    answers.insert_one(a)
                    add_user({"_id":st.session_state.user_id,"username":st.session_state.username})
                    add_answer(a)



                    st.success("Answer published!")
                    st.rerun()


def answer_card(answer, users):

    with st.container(border=True):

        st.write(answer.get("body", ""))

        author = users.find_one({"_id": answer.get("author_id")})
        username = author["username"] if author else "Anonymous"

        st.divider()

        col1, col2 = st.columns([3, 1])

        with col1:
            st.caption(f"👤 {username}")

        with col2:
            votes = rv.get_votes(answer["_id"])
            if st.button(f"⬆️ {votes}", key=f"vote_{answer['_id']}"):
                if rv.upvote(answer["_id"], st.session_state.user_id, username):
                    st.rerun()
                else:
                    st.warning("You already voted.")
