import streamlit as st

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def open_profile(user_id, username):
    st.session_state.viewed_user = {"id": user_id, "username": username}


def expert_card(rank, expert):
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 4, 2])

        with col1:
            st.markdown(f"## #{rank}")

        with col2:
            st.markdown(f"### {expert['username']}")
            st.caption(f"ID: {expert['user_id']}")

        with col3:
            st.metric("Total votes", expert["total_votes"])
            st.caption(f"{expert['answers']} answers")