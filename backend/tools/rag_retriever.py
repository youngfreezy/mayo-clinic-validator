"""
PGVector retriever factory using langchain-postgres (psycopg3).

IMPORTANT: Use langchain_postgres.PGVector, NOT langchain_community.
The new package requires a psycopg3 URI: postgresql+psycopg://...
"""

from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from config.settings import settings

COLLECTION_NAME = "mayo_medical_knowledge"


def get_retriever(k: int = 5):
    """
    Returns a configured MMR retriever over the Mayo medical knowledge base.

    MMR (Maximal Marginal Relevance) balances relevance with diversity in results,
    reducing repetition when multiple chunks from the same document are retrieved.
    """
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY,
    )
    store = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=settings.PGVECTOR_CONNECTION_STRING,
        use_jsonb=True,
    )
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": 20,
            "lambda_mult": 0.5,  # 0=max diversity, 1=max relevance
        },
    )
