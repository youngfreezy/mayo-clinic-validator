"""
Seeds the PGVector knowledge base with Mayo Clinic medical reference content.

Run once after starting Docker:
    python scripts/seed_knowledge.py

This populates the "mayo_medical_knowledge" collection used by the accuracy agent.
Knowledge entries are loaded from ../data/knowledge_base.json — edit that file to
add, remove, or update topics.
"""

import sys
import os
import json

# Allow running from scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config.settings import settings

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    KNOWLEDGE_BASE = json.load(f)


def seed_knowledge_base() -> None:
    print("Seeding Mayo Clinic medical knowledge base...")
    print(f"Connection: {settings.PGVECTOR_CONNECTION_STRING}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " "],
    )

    docs = []
    for entry in KNOWLEDGE_BASE:
        chunks = splitter.create_documents(
            texts=[entry["content"].strip()],
            metadatas=[entry["metadata"]],
        )
        docs.extend(chunks)

    print(f"Created {len(docs)} chunks from {len(KNOWLEDGE_BASE)} knowledge base entries")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY,
    )

    print("Uploading to PGVector (this may take ~30 seconds)...")
    PGVector.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="mayo_medical_knowledge",
        connection=settings.PGVECTOR_CONNECTION_STRING,
        use_jsonb=True,
        pre_delete_collection=True,  # Wipe and re-seed on each run
    )

    print(f"Done! Seeded {len(docs)} chunks into 'mayo_medical_knowledge' collection.")


if __name__ == "__main__":
    seed_knowledge_base()
