# agent.py
# ==============================================================================
# AI BACKEND & AGENT LOGIC (Google ADK)
# ------------------------------------------------------------------------------
# This file defines the core AI Barista Agent, its system instructions/persona,
# and the tools it can use (like searching the menu in Firestore). It exports
# an ADK `App` object that can be invoked by a frontend UI (such as app.py) or
# deployed.
# ==============================================================================
import json
import logging
import os

import google.auth
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models.anthropic_llm import Claude

# [START get_menu]
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

logger = logging.getLogger(__name__)


def get_menu(query: str) -> str:
    """Retrieves coffee shop menu items matching the user's query.

    Args:
        query: The search query or preference to find matching menu items.

    Returns:
        str: A JSON string representing the list of top matching menu items.
    """
    try:
        # Initialize clients
        db = firestore.Client(database="coffee-menu")
        client = genai.Client()

        # Generate embedding for the search query
        response = client.models.embed_content(
            model="text-embedding-005",
            contents=query,
        )
        query_vector = response.embeddings[0].values

        # Search the Firestore database using Vector Search
        results = db.collection("menu").find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=3,
        ).stream()

        menu_data = []
        for doc in results:
            item = doc.to_dict()
            # Remove embedding field to save tokens
            item.pop("embedding", None)
            menu_data.append(item)

        return json.dumps(menu_data)
    except Exception:
        # Log the details for debugging, but return a generic error. Error
        # messages can include project and resource names, and Claude might
        # repeat the tool's response to the user.
        logger.exception("get_menu couldn't retrieve the menu")
        return json.dumps({"error": "The menu isn't available right now."})
# [END get_menu]

# Claude on Gemini Enterprise Agent Platform
# ------------------------------------------------------------------------------
# The agent runs on Anthropic's Claude (Opus 5 by default) through Gemini
# Enterprise Agent Platform, authenticated with Application Default Credentials.
# Newer Claude models are served from the `global` endpoint, so the location is
# set on the model's resource name. This keeps it independent of
# GOOGLE_CLOUD_LOCATION, which the embedding client in get_menu() uses.
# The model must be enabled for your project in Model Garden.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
CLAUDE_LOCATION = os.environ.get("CLAUDE_LOCATION", "global")


def _get_project_id() -> str:
    """Returns GOOGLE_CLOUD_PROJECT, falling back to the ADC default project."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        _, project_id = google.auth.default()
    if not project_id:
        raise ValueError(
            "Set GOOGLE_CLOUD_PROJECT to the project where Claude is enabled."
        )
    return project_id


# Creating this Claude object doesn't call Claude. It records which model to
# use, and ADK makes the calls through Anthropic's SDK when the agent runs.
#
# Use a Claude instance, not a model-name string. ADK only recognizes
# claude-3-* and claude-*-4* strings on its own, so model="claude-opus-5"
# fails with "Model claude-opus-5 not found."
claude_model = Claude(
    model=(
        f"projects/{_get_project_id()}/locations/{CLAUDE_LOCATION}"
        f"/publishers/anthropic/models/{CLAUDE_MODEL}"
    )
)

# Create the barista agent
barista_agent = LlmAgent(
    name="barista_agent",
    # Pass the Claude instance from above. On each turn, ADK sends the
    # conversation to Claude and runs any tools that Claude asks for.
    model=claude_model,
    instruction="""You are a friendly barista at ☕ Coffee Shop.
Your job is to recommend drinks and pastries to customers based on their preferences.

Rules you MUST follow:
1.  You must recommend items ONLY from the menu returned by get_menu().
2.  Do NOT recommend or suggest any item that is not present in the menu.
3.  If a user's preference is vague or unclear, ask exactly ONE friendly clarifying question to narrow down what they want (e.g., cold or hot, sweet or strong, coffee or pastry).
4.  Be warm and welcoming, but remain professional.
5.  Ground your recommendations in the actual tags, descriptions, and allergens listed in the menu (e.g., if a user is dairy-free, recommend ONLY items tagged 'dairy-free' or with no dairy allergens).
""",
    tools=[get_menu]
)

# Define the App object
app = App(
    name="coffee_barista_app",
    root_agent=barista_agent
)
