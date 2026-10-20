# seed.py
# ==============================================================================
# FIRESTORE DATABASE SEEDER & VECTOR EMBEDDING GENERATOR
# ------------------------------------------------------------------------------
# This script reads the local `menu.json` file, generates a vector embedding
# for each menu item's name and description using the `text-embedding-005`
# model on Gemini Enterprise Agent Platform, and uploads the enriched documents
# to the Cloud Firestore `coffee-menu` database (under the `menu` collection).
# This enables semantic/vector search over the coffee shop menu.
# ==============================================================================
import json
import os
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

# Initialize Firestore client targeting the 'coffee-menu' database
db = firestore.Client(database="coffee-menu")

# Initialize the Gen AI client on Agent Platform (vertexai=True) for embeddings
client = genai.Client(
    vertexai=True,
    project=os.environ.get("PROJECT_ID"),
    location=os.environ.get("REGION", "us-central1")
)

# Load local menu items from JSON file
with open("menu.json", "r") as f:
    menu_items = json.load(f)

for item in menu_items:
    # Use the name as the document ID
    doc_id = item["name"].lower().replace(" ", "-")

    # Generate text embedding using Gemini Enterprise Agent Platform text-embedding-005 model
    text_to_embed = f"{item['name']}: {item['description']}"
    response = client.models.embed_content(
        model="text-embedding-005",
        contents=text_to_embed,
    )
    embedding = response.embeddings[0].values

    # Add embedding vector to the menu item data
    item["embedding"] = Vector(embedding)

    # Save the enriched menu item document to the 'menu' collection in Firestore
    db.collection("menu").document(doc_id).set(item)

print("Firestore menu collection seeded with vector embeddings successfully!")
