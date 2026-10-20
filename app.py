# app.py
# ==============================================================================
# WEB FRONTEND & USER INTERFACE (Streamlit)
# ------------------------------------------------------------------------------
# This file builds the interactive web UI for the Coffee Shop Barista Bot.
# Responsibilities:
#   1. Renders the visual layout, coffee-themed header, and sidebar menu cards.
#   2. Manages per-user session state (session_id, chat message history).
#   3. Connects user chat inputs to the ADK `app` imported from `agent.py`
#      using `InMemoryRunner` and displays the AI's responses.
# ==============================================================================
import asyncio
import logging
import uuid
from contextlib import aclosing

import streamlit as st
from google.genai import types

logger = logging.getLogger(__name__)

# Set page config for a premium look
st.set_page_config(
    page_title="☕ Coffee Shop - Barista Bot",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to make the header sticky (adapts to light/dark themes)
st.markdown("""
<style>
    div[data-testid="element-container"]:has(.header-container),
    div.element-container:has(.header-container) {
        position: sticky;
        top: 2.875rem;
        z-index: 999;
        background-color: transparent;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# App Header (using inline styles for the permanent coffee theme look)
st.markdown("""
<div class="header-container" style="text-align: center; padding: 20px; background: linear-gradient(135deg, #8B5E3C, #6F4E37); color: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
    <h1 style="margin: 0; font-size: 2.5rem; font-weight: 700; color: white;">☕ Coffee Shop</h1>
    <p style="margin: 5px 0 0 0; font-size: 1.1rem; opacity: 0.9; color: white;">Your friendly AI Barista is ready to help you find the perfect drink or pastry!</p>
</div>
""", unsafe_allow_html=True)

# Load Menu for the sidebar
# [START load_menu]
from google.cloud import firestore

try:
    db = firestore.Client(database="coffee-menu")
    docs = db.collection("menu").stream()
    menu_items = []
    for doc in docs:
        item = doc.to_dict()
        item.pop("embedding", None)
        menu_items.append(item)
except Exception:
    # Log the details, and show users a generic message. Error messages can
    # include project and resource names.
    logger.exception("Couldn't load the menu from Firestore")
    st.error("Sorry, the menu isn't available right now.")
    menu_items = []
# [END load_menu]

# Sidebar Menu & Configuration
with st.sidebar:
    st.markdown("## ☕ Coffee Shop Menu")
    st.markdown("Explore our offerings and ask the barista for recommendations.")
    st.markdown("---")

    for item in menu_items:
        with st.container(border=True):
            st.markdown(f"**{item['name']}**  •  **${item['price']:.2f}**")
            st.caption(item['description'])

            # Tags & Allergens as native badges
            tags = " ".join([f"`{t}`" for t in item.get("tags", [])])
            if tags:
                st.markdown(tags)

            allergens = ", ".join(item.get("allergens", []))
            if allergens:
                st.markdown(f"⚠️ *Allergens: {allergens}*")

# Chat Interface
# Each browser session gets its own runner and ADK session, so one fixed ADK
# user ID is enough.
USER_ID = "streamlit_user"

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "runner" not in st.session_state:
    from google.adk.runners import InMemoryRunner
    from agent import app
    runner = InMemoryRunner(app=app)
    # run_async() needs an existing session, so create it up front.
    asyncio.run(runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=USER_ID,
        session_id=st.session_state.session_id,
    ))
    st.session_state.runner = runner

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome to ☕ Coffee Shop! What can I get started for you today?"}
    ]

# Display existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Ask for recommendations (e.g., 'What dairy-free pastries do you have?')"):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate response
    with st.chat_message("assistant"):
        try:
            # Send the message to the agent and collect the events that ADK
            # yields. aclosing() closes the event stream even if an error
            # stops it early.
            async def fetch_response():
                message = types.Content(role="user", parts=[types.Part(text=prompt)])
                async with aclosing(st.session_state.runner.run_async(
                    user_id=USER_ID,
                    session_id=st.session_state.session_id,
                    new_message=message,
                )) as events:
                    return [event async for event in events]

            res_events = asyncio.run(fetch_response())

            # Show each text part as its own paragraph (Claude often sends a short
            # preamble before calling a tool), and skip "thought" parts so the
            # model's internal reasoning is never displayed.
            response_text = "\n\n".join([
                part.text
                for event in res_events
                if event.content and event.content.parts
                for part in event.content.parts
                if part.text and not part.thought
            ])

            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
        except Exception:
            # Log the details, and show users a generic message. Error messages
            # can include project and resource names.
            logger.exception("The agent couldn't respond")
            st.error("Sorry, I ran into a problem. Please try again.")
