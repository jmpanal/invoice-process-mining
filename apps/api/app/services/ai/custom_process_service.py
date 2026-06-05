from __future__ import annotations

from typing import Any

from app.services.ai.openai_client import OpenAIResponseError, openai_client

ALLOWED_NODE_KINDS = {"trigger", "action", "decision", "wait", "approval", "system", "error", "manual", "data", "terminal"}
ALLOWED_EDGE_TYPES = {"normal", "condition", "error", "retry", "wait", "approval", "rejected", "hidden", "inferred"}


def generate_process_graph(description: str) -> dict[str, Any]:
    prompt = f"""
You are a senior process analyst and workflow architect.

The user wants to generate a process graph from this description:
{description}

If the description is high level, infer the most likely real-world process steps from standard operating practice.
Think through likely triggers, handoffs, decisions, approvals, data/system steps, exception paths, failure paths, retries, and terminal outcomes.
Do not invent exact metrics. Do not include implementation code.

Return only JSON with this shape:
{{
  "title": "short process name",
  "summary": "one sentence explaining the process",
  "assumptions": ["assumption made because the request was high level"],
  "nodes": [
    {{
      "id": "stable_snake_case_id",
      "title": "one-line label under 28 characters",
      "kind": "trigger|action|decision|wait|approval|system|error|manual|data|terminal",
      "lane": "main|exception|approval|system",
      "description": "short operational detail"
    }}
  ],
  "edges": [
    {{
      "id": "stable_snake_case_id",
      "source": "source_node_id",
      "target": "target_node_id",
      "label": "short condition or empty string",
      "type": "normal|condition|error|retry|wait|approval|rejected|hidden|inferred"
    }}
  ]
}}

Rules:
- Include 6 to 16 nodes.
- Every node must be reachable from the first trigger node.
- Include at least one terminal node.
- Use a clean main path left-to-right.
- Put exceptions, rejections, retries, and approvals as side branches.
- Edges must only reference existing node IDs.
"""
    payload = openai_client.structured_json(prompt)
    return normalize_graph(payload)


def normalize_graph(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise OpenAIResponseError("Generated process graph must include nodes.")
    if not isinstance(edges, list) or not edges:
        raise OpenAIResponseError("Generated process graph must include edges.")

    normalized_nodes = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(nodes[:16]):
        if not isinstance(raw, dict):
            raise OpenAIResponseError("Generated process graph node must be an object.")
        node_id = safe_id(string_value(raw.get("id"), f"step_{index + 1}"))
        if node_id in seen_ids:
            node_id = f"{node_id}_{index + 1}"
        seen_ids.add(node_id)
        kind = string_value(raw.get("kind"), "action").lower()
        lane = string_value(raw.get("lane"), "main").lower()
        normalized_nodes.append(
            {
                "id": node_id,
                "title": string_value(raw.get("title"), node_id.replace("_", " "))[:48],
                "kind": kind if kind in ALLOWED_NODE_KINDS else "action",
                "lane": lane if lane in {"main", "exception", "approval", "system"} else "main",
                "description": string_value(raw.get("description"), ""),
            }
        )

    id_map = {safe_id(string_value(raw.get("id"), f"step_{index + 1}")): node["id"] for index, (raw, node) in enumerate(zip(nodes, normalized_nodes, strict=False)) if isinstance(raw, dict)}
    valid_ids = {node["id"] for node in normalized_nodes}
    normalized_edges = []
    for index, raw in enumerate(edges):
        if not isinstance(raw, dict):
            raise OpenAIResponseError("Generated process graph edge must be an object.")
        source = id_map.get(safe_id(string_value(raw.get("source"), "")), safe_id(string_value(raw.get("source"), "")))
        target = id_map.get(safe_id(string_value(raw.get("target"), "")), safe_id(string_value(raw.get("target"), "")))
        if source not in valid_ids or target not in valid_ids or source == target:
            continue
        edge_type = string_value(raw.get("type"), "normal").lower()
        normalized_edges.append(
            {
                "id": safe_id(string_value(raw.get("id"), f"{source}_to_{target}_{index + 1}")),
                "source": source,
                "target": target,
                "label": string_value(raw.get("label"), "")[:32],
                "type": edge_type if edge_type in ALLOWED_EDGE_TYPES else "normal",
            }
        )

    if not normalized_edges:
        raise OpenAIResponseError("Generated process graph did not include valid edges.")
    reachable = reachable_node_ids(normalized_nodes[0]["id"], normalized_edges)
    unreachable = valid_ids - reachable
    if unreachable:
        normalized_nodes = [node for node in normalized_nodes if node["id"] in reachable]
        normalized_edges = [edge for edge in normalized_edges if edge["source"] in reachable and edge["target"] in reachable]

    return {
        "title": string_value(payload.get("title"), "Generated process")[:80],
        "summary": string_value(payload.get("summary"), ""),
        "assumptions": [string_value(item, "") for item in payload.get("assumptions", []) if string_value(item, "")][:8],
        "nodes": normalized_nodes,
        "edges": normalized_edges,
    }


def reachable_node_ids(start_id: str, edges: list[dict[str, str]]) -> set[str]:
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(edge["source"], []).append(edge["target"])
    seen: set[str] = set()
    queue = [start_id]
    while queue:
        node_id = queue.pop(0)
        if node_id in seen:
            continue
        seen.add(node_id)
        queue.extend(outgoing.get(node_id, []))
    return seen


def string_value(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def safe_id(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "node"
