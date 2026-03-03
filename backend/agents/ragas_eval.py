"""
RAGAS Evaluation — standardized RAG quality metrics for the Accuracy Agent.

Runs four metrics after each accuracy agent evaluation:
  - Faithfulness:       Are LLM claims supported by retrieved references?
  - Answer Relevancy:   Is the output focused and on-topic?
  - Context Precision:  Are relevant chunks ranked higher in retrieval?
  - Context Recall:     Did retrieval find all needed reference material?

These metrics decompose the accuracy agent's single composite score into
separate retrieval-quality and generation-quality measurements.
"""

import asyncio
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def run_ragas_eval(
    question: str,
    answer: str,
    contexts: List[str],
    reference: Optional[str] = None,
) -> Optional[Dict[str, float]]:
    """
    Run RAGAS evaluation on a single accuracy agent output.

    Args:
        question:  The query constructed from page title + body (what we asked).
        answer:    The LLM's fact-check response (what GPT-5.1 produced).
        contexts:  The retrieved PGVector reference chunks (what retrieval found).
        reference: Optional ground-truth answer for context_recall.

    Returns:
        Dict with metric scores, or None if evaluation fails.
    """
    if not contexts or not answer:
        logger.warning("RAGAS eval skipped: missing contexts or answer")
        return None

    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
        from ragas.metrics.collections import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from config.settings import settings

        # Build the sample — RAGAS needs question, answer, and retrieved contexts
        sample_kwargs = {
            "user_input": question,
            "response": answer,
            "retrieved_contexts": contexts,
        }
        # context_recall needs a reference (ground truth) to compare against
        if reference:
            sample_kwargs["reference"] = reference

        sample = SingleTurnSample(**sample_kwargs)
        dataset = EvaluationDataset(samples=[sample])

        # Use a lightweight model for RAGAS eval (not the main GPT-5.1)
        eval_llm = LangchainLLMWrapper(ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            request_timeout=60,
        ))
        eval_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
        ))

        # Select metrics — skip context_recall if no reference provided
        metrics = [faithfulness, answer_relevancy, context_precision]
        if reference:
            metrics.append(context_recall)

        result = await asyncio.to_thread(
            evaluate,
            dataset=dataset,
            metrics=metrics,
            llm=eval_llm,
            embeddings=eval_embeddings,
            show_progress=False,
            raise_exceptions=False,
        )

        # Extract scores from the result
        scores = {}
        df = result.to_pandas()
        if not df.empty:
            row = df.iloc[0]
            for metric_name in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                if metric_name in row and row[metric_name] is not None:
                    val = float(row[metric_name])
                    if not (val != val):  # check for NaN
                        scores[metric_name] = round(val, 4)

        logger.info(f"RAGAS eval complete: {scores}")
        return scores if scores else None

    except Exception as e:
        logger.warning(f"RAGAS eval failed (non-fatal): {e}")
        return None
