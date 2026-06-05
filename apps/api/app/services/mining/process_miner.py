from __future__ import annotations

from collections import Counter, defaultdict
import math
from statistics import mean
from typing import Any

import pandas as pd
import pm4py
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def run_process_mining(session: Session, event_log_id: str, ideal_process_id: str) -> models.MiningRun:
    process = session.get(models.IdealProcess, ideal_process_id)
    event_log = session.get(models.UploadedEventLog, event_log_id)
    if process is None or event_log is None:
        raise ValueError("Selected ideal process or event log does not exist")

    events = list(
        session.scalars(
            select(models.ProcessEvent)
            .where(models.ProcessEvent.event_log_id == event_log_id)
            .order_by(models.ProcessEvent.case_id, models.ProcessEvent.timestamp)
        ).all()
    )
    if not events:
        raise ValueError("Event log has no process events")

    canonical_labels = {node.label for node in process.nodes}
    node_key_by_label = {node.label: node.node_key for node in process.nodes}
    canonical_aliases = canonical_activity_aliases(process)
    canonical_edges = observable_canonical_edges(process)
    pm4py_log = pm4py_event_frame(events)
    frequency_dfg, start_activities, end_activities = pm4py.discover_dfg(pm4py_log)
    performance_dfg, _, _ = pm4py.discover_performance_dfg(pm4py_log)
    variant_counts = pm4py_variant_counts(pm4py.get_variants_as_tuples(pm4py_log))

    case_count = len({event.case_id for event in events})
    node_counts: Counter[str] = Counter(pm4py.get_event_attribute_values(pm4py_log, "concept:name"))
    edge_counts = pm4py_edge_counts(frequency_dfg)
    avg_wait_by_edge = {
        edge: pm4py_wait_hours(performance_dfg.get(edge, 0.0))
        for edge in edge_counts
    }
    hidden_node_flags: dict[str, bool] = defaultdict(bool)
    issue_counts: Counter[str] = Counter()
    hidden_cases: set[str] = set()

    for event in events:
        hidden = event.is_hidden_step or canonical_aliases.get(event.activity, event.activity) not in canonical_labels
        hidden_node_flags[event.activity] = hidden_node_flags[event.activity] or hidden
        if hidden:
            hidden_cases.add(event.case_id)
            if event.hidden_issue_type:
                issue_counts[event.hidden_issue_type] += 1

    waits = sorted(avg_wait_by_edge.values())
    percentile_index = min(len(waits) - 1, max(0, int(len(waits) * 0.8))) if waits else 0
    bottleneck_threshold = max(24.0, waits[percentile_index] if waits else 24.0)
    cycle_hours = [duration / 3600 for duration in pm4py.get_all_case_durations(pm4py_log)]

    top_bottlenecks = [
        {"source": source, "target": target, "avg_wait_hours": round(wait, 2), "frequency": edge_counts[(source, target)]}
        for (source, target), wait in sorted(avg_wait_by_edge.items(), key=lambda item: item[1], reverse=True)
        if wait >= bottleneck_threshold
    ][:10]
    top_hidden_issues = [{"issue": issue, "count": count} for issue, count in issue_counts.most_common(10)]
    top_variants = [
        {"variant": list(variant), "count": count, "share": round(count / max(1, case_count), 4)}
        for variant, count in sorted(variant_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    metrics = {
        "case_count": case_count,
        "event_count": len(events),
        "avg_cycle_time_hours": round(mean(cycle_hours), 2),
        "hidden_case_rate": round(len(hidden_cases) / max(1, case_count), 4),
        "top_hidden_issue": top_hidden_issues[0]["issue"] if top_hidden_issues else "",
        "top_bottleneck": f"{top_bottlenecks[0]['source']} -> {top_bottlenecks[0]['target']}" if top_bottlenecks else "",
        "sla_breach_estimate": round(sum(1 for value in cycle_hours if value > 120) / max(1, len(cycle_hours)), 4),
        "bottleneck_threshold_hours": round(bottleneck_threshold, 2),
        "mining_engine": "pm4py",
        "discovery_algorithm": "pm4py.discover_dfg",
        "performance_algorithm": "pm4py.discover_performance_dfg",
        "variant_algorithm": "pm4py.get_variants_as_tuples",
        "start_activities": activity_counts_label(start_activities),
        "end_activities": activity_counts_label(end_activities),
    }

    run = models.MiningRun(
        ideal_process_id=ideal_process_id,
        event_log_id=event_log_id,
        metrics=metrics,
        top_variants=top_variants,
        top_hidden_issues=top_hidden_issues,
        top_bottlenecks=top_bottlenecks,
    )
    session.add(run)
    session.flush()

    bottleneck_node_names = {item["source"] for item in top_bottlenecks} | {item["target"] for item in top_bottlenecks}
    for activity, frequency in node_counts.items():
        canonical_label = canonical_aliases.get(activity, activity)
        hidden = hidden_node_flags[activity]
        bottleneck = activity in bottleneck_node_names and not hidden
        session.add(
            models.MinedNode(
                mining_run_id=run.id,
                activity=activity,
                frequency=frequency,
                is_hidden=hidden,
                is_bottleneck=bottleneck,
                severity="hidden" if hidden else "bottleneck" if bottleneck else "normal",
                node_metadata={"canonical_node_key": node_key_by_label.get(canonical_label)},
            )
        )

    for (source, target), frequency in edge_counts.items():
        wait = avg_wait_by_edge[(source, target)]
        canonical_source = canonical_aliases.get(source, source)
        canonical_target = canonical_aliases.get(target, target)
        includes_hidden_node = hidden_node_flags[source] or hidden_node_flags[target]
        hidden = includes_hidden_node or (canonical_source, canonical_target) not in canonical_edges
        bottleneck = (wait >= bottleneck_threshold) and not hidden
        session.add(
            models.MinedEdge(
                mining_run_id=run.id,
                source_activity=source,
                target_activity=target,
                frequency=frequency,
                avg_wait_hours=round(wait, 2),
                is_hidden=hidden,
                is_bottleneck=bottleneck,
                severity="hidden" if hidden else "bottleneck" if bottleneck else "normal",
                edge_metadata={"canonical": (canonical_source, canonical_target) in canonical_edges},
            )
        )

    session.commit()
    session.refresh(run)
    return run


def pm4py_event_frame(events: list[models.ProcessEvent]) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "case_id": event.case_id,
                "activity": event.activity,
                "timestamp": event.timestamp,
            }
            for event in events
        ]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return pm4py.format_dataframe(frame, case_id="case_id", activity_key="activity", timestamp_key="timestamp")


def pm4py_edge_counts(frequency_dfg: dict[tuple[str, str], int]) -> Counter[tuple[str, str]]:
    return Counter({(str(source), str(target)): int(count) for (source, target), count in frequency_dfg.items()})


def pm4py_variant_counts(variants: dict[tuple[str, ...], Any]) -> dict[tuple[str, ...], int]:
    counts: dict[tuple[str, ...], int] = {}
    for variant, cases in variants.items():
        key = tuple(str(activity) for activity in variant)
        counts[key] = int(cases) if isinstance(cases, int) else len(cases)
    return counts


def pm4py_wait_hours(performance_value: Any) -> float:
    seconds = performance_value.get("mean", 0.0) if isinstance(performance_value, dict) else performance_value
    seconds_float = float(seconds or 0.0)
    return seconds_float / 3600 if math.isfinite(seconds_float) else 0.0


def activity_counts_label(counts: dict[str, int]) -> str:
    return ", ".join(f"{activity}: {int(count)}" for activity, count in counts.items())


def process_node_label(process: models.IdealProcess, node_key: str) -> str:
    for node in process.nodes:
        if node.node_key == node_key:
            return node.label
    return node_key


def canonical_activity_aliases(process: models.IdealProcess) -> dict[str, str]:
    aliases = {node.label: node.label for node in process.nodes}
    aliases.update(
        {
            "Invoice received": "Invoice received in Coupa",
            "Check PO exists": "Check purchase order exists in SAP",
            "Run three-way match": "Run three-way match in SAP",
            "Create missing PO exception": "Create missing PO exception in ServiceNow",
            "Schedule payment": "Schedule payment in SAP",
        }
    )
    return aliases


def observable_canonical_edges(process: models.IdealProcess) -> set[tuple[str, str]]:
    nodes_by_key = {node.node_key: node for node in process.nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in process.edges:
        adjacency[edge.source_node_key].append(edge.target_node_key)

    observable_edges: set[tuple[str, str]] = set()
    for source_key, source_node in nodes_by_key.items():
        if source_node.node_type == "gateway":
            continue
        stack = list(adjacency[source_key])
        visited: set[str] = set()
        while stack:
            target_key = stack.pop()
            if target_key in visited:
                continue
            visited.add(target_key)
            target_node = nodes_by_key[target_key]
            if target_node.node_type == "gateway":
                stack.extend(adjacency[target_key])
            else:
                observable_edges.add((source_node.label, target_node.label))
    return observable_edges


def mining_run_payload(session: Session, run: models.MiningRun) -> dict[str, Any]:
    nodes = list(session.scalars(select(models.MinedNode).where(models.MinedNode.mining_run_id == run.id)).all())
    edges = list(session.scalars(select(models.MinedEdge).where(models.MinedEdge.mining_run_id == run.id)).all())
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat(),
        "metrics": run.metrics,
        "top_variants": run.top_variants,
        "top_hidden_issues": run.top_hidden_issues,
        "top_bottlenecks": run.top_bottlenecks,
        "nodes": [
            {
                "id": node.id,
                "activity": node.activity,
                "frequency": node.frequency,
                "is_hidden": node.is_hidden,
                "is_bottleneck": node.is_bottleneck,
                "severity": node.severity,
                "metadata": node.node_metadata,
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "source_activity": edge.source_activity,
                "target_activity": edge.target_activity,
                "frequency": edge.frequency,
                "avg_wait_hours": edge.avg_wait_hours,
                "is_hidden": edge.is_hidden,
                "is_bottleneck": edge.is_bottleneck,
                "severity": edge.severity,
                "metadata": edge.edge_metadata,
            }
            for edge in edges
        ],
    }
