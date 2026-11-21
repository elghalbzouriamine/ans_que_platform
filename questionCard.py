import streamlit as st
from answerCard import answer_section, answer_card
import redis_integration as rv


def question_card(question, users, answers=None, show_answer=True):

    with st.container(border=True):

        st.subheader(question.get("title", "Untitled"))
        st.write(question.get("body", ""))

        tags = question.get("tags", [])
        if tags:
            st.markdown(" ".join([f"`{tag}`" for tag in tags]))

        st.divider()

        author = users.find_one({
            "_id": question["author_id"]
        })

        username = author["username"] if author else "Anonymous"

        answer_count = answers.count_documents({
            "question_id": question["_id"]
        }) if answers is not None else 0

        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption(f"👤 {username}")



        with col3:
            st.caption(f"💬 {answer_count} answers")

        if show_answer and answers is not None:
            answer_section(question, answers)

            if answer_count:
                with st.expander(f"View answers ({answer_count})"):
                    docs = list(answers.find({"question_id": question["_id"]}))
                    # best answers first, ranked by Redis score
                    docs.sort(
                    key=lambda a: rv.get_votes(a["_id"]),
                    reverse=True
                            )
                    
                    for a in docs:
                        answer_card(a, users)
