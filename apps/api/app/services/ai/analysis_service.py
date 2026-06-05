from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.ai.openai_client import OpenAIResponseError, openai_client
from app.services.rag import rag_service


def analyze(session: Session, question: str, mining_run_id: str | None = None) -> dict:
    chunks = rag_service.search(session, question, top_k=5, filters=None)
    relevant = [chunk for chunk in chunks if chunk["similarity"] > 0.05]
    run = session.get(models.MiningRun, mining_run_id) if mining_run_id else session.scalars(select(models.MiningRun).order_by(models.MiningRun.created_at.desc())).first()
    if not relevant:
        answer = {
            "answer": "Context is insufficient to answer safely. Rebuild the RAG index with SOPs, policies, and mined summaries first.",
            "evidence_used": [],
            "retrieved_sources": [],
            "visible_trace": ["No relevant retrieved chunks passed the minimum similarity threshold."],
            "assumptions": ["No answer was generated without evidence."],
            "missing_information": ["Relevant SOP, policy, or mined process context."],
            "confidence": "low",
        }
    else:
        metrics = run.metrics if run else {}
        answer = normalize_analysis_answer(openai_client.structured_json(build_analysis_prompt(question, relevant, metrics)))
    query = models.RagQuery(
        mining_run_id=mining_run_id,
        question=question,
        answer=answer,
        retrieved_chunks=relevant,
        visible_trace=answer.get("visible_trace", []),
    )
    session.add(query)
    session.commit()
    answer["query_id"] = query.id
    return answer


def build_analysis_prompt(question: str, chunks: list[dict], metrics: dict) -> str:
    return (
        "Analyze the invoice process question using only the retrieved context and mined metrics.\n"
        "Return JSON with keys: answer, evidence_used, retrieved_sources, visible_trace, assumptions, missing_information, confidence.\n"
        "Write for a non expert operations user. Keep the answer short, concrete, and useful.\n"
        "Use natural human language. Avoid consultant phrasing, filler, and generic AI wording.\n"
        "Explain the reason in simple terms so the user understands what to do and why it matters.\n"
        "Name the exact process step, control, policy, system, or metric when the context provides one.\n"
        "Do not use vague nouns like systems, changes, things, or configurations unless the context names them that way.\n"
        "Do not repeat the same point across answer, visible_trace, assumptions, and missing_information.\n"
        "Do not use dash punctuation or dash list markers in any prose value.\n"
        "Use arrays for evidence_used, retrieved_sources, visible_trace, assumptions, and missing_information.\n"
        "Each array entry must be one short sentence.\n"
        "answer must be 2 to 4 short sentences with the recommendation and the plain reason.\n"
        "evidence_used must contain concrete facts from retrieved context or mined metrics.\n"
        "visible_trace must show the source, the fact taken from it, and the conclusion in plain language.\n"
        "assumptions must contain only specific assumptions needed to answer. Use an empty array when none are needed.\n"
        "missing_information must contain only facts that would change the answer. Use an empty array when nothing important is missing.\n"
        "Do not recommend automation that skips duplicate checks, vendor risk controls, approval thresholds, or final human approval.\n\n"
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{json.dumps(chunks, default=str)}\n\n"
        f"Mined metrics:\n{json.dumps(metrics, default=str)}"
    )


def normalize_analysis_answer(answer: dict) -> dict:
    if not isinstance(answer.get("answer"), str) or not answer["answer"].strip():
        raise OpenAIResponseError("OpenAI analysis response must include a non-empty answer.")
    normalized = dict(answer)
    for field in ["evidence_used", "retrieved_sources", "visible_trace", "assumptions", "missing_information"]:
        normalized[field] = list_value(normalized.get(field))
    normalized["confidence"] = str(normalized.get("confidence") or "medium")
    return normalized


def list_value(value: object) -> list:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]
