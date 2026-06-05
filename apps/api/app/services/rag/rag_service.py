from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.services.ai.openai_client import openai_client

SOURCE_REPOSITORIES = {
    "SOP": ("docs/sop-repository", settings.root_dir / "docs" / "sop-repository"),
    "POLICY": ("docs/policy-repository", settings.root_dir / "docs" / "policy-repository"),
}


def list_source_files(source_type: str | None = None) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for repo_source_type, (repo_name, directory) in SOURCE_REPOSITORIES.items():
        if source_type and repo_source_type != source_type:
            continue
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            files.append(file_payload(path, repo_source_type, repo_name, content, include_content=False))
    return files


def read_source_file(file_id: str) -> dict[str, Any] | None:
    for source_type, (repo_name, directory) in SOURCE_REPOSITORIES.items():
        path = directory / f"{file_id}.md"
        if path.exists():
            return file_payload(path, source_type, repo_name, path.read_text(encoding="utf-8"), include_content=True)
    return None


def file_payload(path: Path, source_type: str, repo_name: str, content: str, include_content: bool) -> dict[str, Any]:
    title = extract_title(content) or path.stem
    metadata = {
        "source_file_path": str(path),
        "source_repository": repo_name,
        "sections": [section for section, _ in split_sections(content)],
        "process_area": title.split(": ", 1)[1] if ": " in title else title,
    }
    payload = {
        "id": path.stem,
        "title": title,
        "source_type": source_type,
        "source_file_path": str(path),
        "source_repository": repo_name,
        "metadata": metadata,
        "size_bytes": path.stat().st_size,
        "updated_at": path.stat().st_mtime,
    }
    if include_content:
        payload["content"] = content
    return payload


def extract_title(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line.replace("# ", "", 1).strip()
    return ""


def chunk_text(title: str, source_type: str, content: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    sections = split_sections(content)
    chunks: list[dict[str, Any]] = []
    for section_title, section_body in sections:
        words = section_body.split()
        if not words:
            continue
        for start in range(0, len(words), 700):
            window = words[start : start + 800]
            header = f"Title: {title}\nSource type: {source_type}\nSection: {section_title}\n"
            text = header + " ".join(window)
            chunks.append(
                {
                    "text": text,
                    "metadata": {**metadata, "title": title, "section": section_title, "process_area": metadata.get("process_area", "")},
                }
            )
            if start + 800 >= len(words):
                break
    return chunks


def split_sections(content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current = ("Document", [])
    for line in content.splitlines():
        if line.startswith("## "):
            if current[1]:
                sections.append(current)
            current = (line.replace("## ", "", 1).strip(), [])
        elif line.startswith("# "):
            continue
        else:
            current[1].append(line)
    if current[1]:
        sections.append(current)
    return [(title, "\n".join(lines).strip()) for title, lines in sections]


def reindex(session: Session) -> dict[str, Any]:
    try:
        session.execute(delete(models.DocumentChunk))
        chunk_count = 0
        for source_type, (repo_name, directory) in SOURCE_REPOSITORIES.items():
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                content = path.read_text(encoding="utf-8")
                title = extract_title(content) or path.stem
                metadata = {
                    "source_file_path": str(path),
                    "source_repository": repo_name,
                    "process_area": title.split(": ", 1)[1] if ": " in title else title,
                }
                chunk_count += store_chunks(session, title, source_type, str(path), repo_name, content, metadata)

        latest_process = session.scalars(select(models.IdealProcess).order_by(models.IdealProcess.created_at.desc())).first()
        if latest_process:
            chunk_count += store_chunks(
                session,
                "Canonical process summary",
                "PROCESS",
                "generated://canonical-process/latest",
                "generated/process",
                canonical_process_text(latest_process),
                {"process_area": "canonical_process"},
            )

        latest_run = session.scalars(select(models.MiningRun).order_by(models.MiningRun.created_at.desc())).first()
        if latest_run:
            chunk_count += store_chunks(
                session,
                "Latest mined process summary",
                "MINING_SUMMARY",
                "generated://mining-summary/latest",
                "generated/mining",
                mining_text(latest_run),
                {"process_area": "mined_process"},
            )

        session.commit()
        return status(session) | {"indexed_chunks": chunk_count}
    except Exception:
        session.rollback()
        raise


def store_chunks(
    session: Session,
    title: str,
    source_type: str,
    source_file_path: str,
    source_repository: str,
    content: str,
    metadata: dict[str, Any],
) -> int:
    count = 0
    for index, chunk in enumerate(chunk_text(title, source_type, content, metadata)):
        session.add(
            models.DocumentChunk(
                document_title=title,
                source_type=source_type,
                source_file_path=source_file_path,
                source_repository=source_repository,
                chunk_index=index,
                chunk_text=chunk["text"],
                chunk_metadata=chunk["metadata"] | {"chunk_index": index},
                embedding=openai_client.embed(chunk["text"]),
            )
        )
        count += 1
    return count


def search(session: Session, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query_embedding = openai_client.embed(query)
    chunks = filtered_chunks(session, filters)
    scored = []
    for chunk in chunks:
        similarity = round(cosine(query_embedding, list(chunk.embedding)), 4)
        scored.append(chunk_payload(chunk) | {"similarity": float(similarity)})
    return sorted(scored, key=lambda item: item["similarity"], reverse=True)[:top_k]


def list_chunks(
    session: Session,
    source_file_path: str | None = None,
    source_type: str | None = None,
    include_embedding: bool = False,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if source_file_path:
        filters["source_file_path"] = source_file_path
    if source_type:
        filters["source_type"] = source_type
    chunks = filtered_chunks(session, filters)
    return [chunk_payload(chunk, include_embedding=include_embedding) for chunk in chunks]


def filtered_chunks(session: Session, filters: dict[str, Any] | None = None) -> list[models.DocumentChunk]:
    stmt = select(models.DocumentChunk).order_by(models.DocumentChunk.source_type, models.DocumentChunk.document_title, models.DocumentChunk.chunk_index)
    chunks = list(session.scalars(stmt).all())
    if filters and filters.get("source_type"):
        allowed = filters["source_type"]
        if isinstance(allowed, str):
            allowed = [allowed]
        chunks = [chunk for chunk in chunks if chunk.source_type in allowed]
    if filters and filters.get("source_file_path"):
        chunks = [chunk for chunk in chunks if chunk.source_file_path == filters["source_file_path"]]
    return chunks


def chunk_payload(chunk: models.DocumentChunk, include_embedding: bool = False) -> dict[str, Any]:
    embedding = [float(value) for value in list(chunk.embedding)]
    payload = {
        "chunk_id": chunk.id,
        "document_title": chunk.document_title,
        "title": chunk.document_title,
        "source_type": chunk.source_type,
        "source_file_path": chunk.source_file_path,
        "source_repository": chunk.source_repository,
        "chunk_index": chunk.chunk_index,
        "embedding_dimensions": len(embedding),
        "embedding_preview": embedding[:16],
        "metadata": chunk.chunk_metadata,
        "chunk_text": chunk.chunk_text,
        "created_at": chunk.created_at.isoformat(),
    }
    if include_embedding:
        payload["embedding"] = embedding
    return payload


def status(session: Session) -> dict[str, Any]:
    chunks = list(session.scalars(select(models.DocumentChunk)).all())
    source_files = sorted({chunk.source_file_path for chunk in chunks})
    types = sorted({chunk.source_type for chunk in chunks})
    last_chunk = max((chunk.created_at for chunk in chunks), default=None)
    return {
        "total_documents": len(source_files),
        "total_chunks": len(chunks),
        "document_types": types,
        "last_index_time": last_chunk.isoformat() if last_chunk else None,
    }


def cosine(left: list[float], right: list[float]) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    size = min(len(left_values), len(right_values))
    dot = sum(left_values[index] * right_values[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left_values[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right_values[:size])) or 1.0
    return float(dot / (left_norm * right_norm))


def canonical_process_text(process: models.IdealProcess) -> str:
    nodes = "\n".join(f"- {node.label} ({node.system}, {node.role})" for node in process.nodes)
    edges = "\n".join(f"- {edge.source_node_key} -> {edge.target_node_key} {edge.label}" for edge in process.edges)
    return f"# Canonical process summary\n\n## Nodes\n{nodes}\n\n## Edges\n{edges}"


def mining_text(run: models.MiningRun) -> str:
    return (
        "# Latest mined process summary\n\n"
        f"## Metrics\n{run.metrics}\n\n"
        f"## Top variants\n{run.top_variants}\n\n"
        f"## Top hidden issues\n{run.top_hidden_issues}\n\n"
        f"## Top bottlenecks\n{run.top_bottlenecks}"
    )
