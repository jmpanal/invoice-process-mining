from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import repositories

REQUIRED_COLUMNS = [
    "case_id",
    "invoice_id",
    "activity",
    "timestamp",
    "system",
    "role",
    "user_id",
    "invoice_amount",
    "currency",
    "country",
    "vendor_id",
    "vendor_risk",
    "po_number",
    "exception_type",
    "status",
    "is_hidden_step",
    "hidden_issue_type",
]


def generate_event_log(session: Session, case_count: int = 2000, seed: int = 42):
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    start = datetime(2026, 1, 5, 8, 0, 0)
    for case_index in range(case_count):
        rows.extend(generate_case(case_index, rng, start + timedelta(minutes=case_index * 7)))
    filename = f"invoice_events_seed_{seed}_cases_{case_count}.csv"
    path = settings.root_dir / "data" / "generated" / filename
    write_csv(path, rows)
    return repositories.create_event_log(
        session,
        filename=filename,
        source_type="generated",
        rows=rows,
        csv_path=str(path),
        metadata=summarize_rows(rows, seed),
    )


def generate_case(case_index: int, rng: random.Random, timestamp: datetime) -> list[dict[str, Any]]:
    amount = round(rng.uniform(250, 25000), 2)
    vendor_risk = rng.choices(["low", "medium", "high"], weights=[70, 22, 8])[0]
    country = rng.choice(["DE", "NL", "ES", "FR", "IT"])
    case_id = f"CASE-{case_index + 1:05d}"
    invoice_id = f"INV-{case_index + 1:06d}"
    vendor_id = f"V{rng.randint(1000, 9999)}"
    po_number = f"PO{rng.randint(100000, 999999)}"
    user = f"ap{rng.randint(1, 25):02d}"
    exception = pick_exception(rng)
    flags = {
        "manual_email": rng.random() < 0.11,
        "excel": rng.random() < 0.09,
        "reopened": rng.random() < 0.06,
        "queue_delay": rng.random() < 0.20,
        "bypass": rng.random() < 0.015,
    }
    rows: list[dict[str, Any]] = []

    def add(
        activity: str,
        system: str,
        role: str,
        hours: float,
        status: str = "completed",
        hidden: bool = False,
        hidden_issue: str = "",
        exception_type: str = "",
    ) -> None:
        nonlocal timestamp
        timestamp += timedelta(hours=hours)
        rows.append(
            {
                "case_id": case_id,
                "invoice_id": invoice_id,
                "activity": activity,
                "timestamp": timestamp,
                "system": system,
                "role": role,
                "user_id": user if role != "System" else "system",
                "invoice_amount": amount,
                "currency": "EUR",
                "country": country,
                "vendor_id": vendor_id,
                "vendor_risk": vendor_risk,
                "po_number": po_number,
                "exception_type": exception_type,
                "status": status,
                "is_hidden_step": hidden,
                "hidden_issue_type": hidden_issue,
            }
        )

    add("Invoice received", "Coupa", "System", 0.1)
    add("Validate invoice data", "Coupa", "AP Clerk", 0.4)
    if flags["manual_email"]:
        add("Manual Email Review", "Email and Excel", "AP Clerk", rng.uniform(8, 36), hidden=True, hidden_issue="Manual Email Review")
    add("Check PO exists", "SAP", "System", 0.3)

    if exception == "missing_po":
        add("Create missing PO exception", "ServiceNow", "System", 0.2, exception_type="missing_po")
        add("AP review missing PO", "ServiceNow", "AP Clerk", manual_delay(rng, flags), exception_type="missing_po")
        add("Procurement correction", "SAP", "Procurement Specialist", rng.uniform(8, 48), exception_type="missing_po")
        add("Check PO exists", "SAP", "System", 0.2, exception_type="missing_po")

    add("Run three-way match", "SAP", "System", 0.5)
    if exception in {"price_mismatch", "quantity_mismatch", "missing_gr"}:
        if exception == "price_mismatch":
            add("Classify exception", "ServiceNow", "AP Clerk", 0.2, exception_type=exception)
            add("Create price mismatch ticket", "ServiceNow", "System", 0.2, exception_type=exception)
            add("AP review price mismatch", "ServiceNow", "AP Clerk", manual_delay(rng, flags), exception_type=exception)
            if flags["excel"]:
                add("Excel Price Correction", "Email and Excel", "AP Clerk", rng.uniform(4, 24), hidden=True, hidden_issue="Excel Price Correction", exception_type=exception)
            add("Correction for price mismatch", "SAP", "Procurement Specialist", rng.uniform(4, 24), exception_type=exception)
        elif exception == "quantity_mismatch":
            add("Classify exception", "ServiceNow", "AP Clerk", 0.2, exception_type=exception)
            add("Create quantity mismatch ticket", "ServiceNow", "System", 0.2, exception_type=exception)
            add("AP review quantity mismatch", "ServiceNow", "AP Clerk", manual_delay(rng, flags), exception_type=exception)
            add("Correction for quantity mismatch", "SAP", "Procurement Specialist", rng.uniform(4, 24), exception_type=exception)
        else:
            add("Classify exception", "ServiceNow", "AP Clerk", 0.2, exception_type=exception)
            add("Request goods receipt confirmation", "SAP", "Procurement Specialist", rng.uniform(8, 36), exception_type=exception)
        if flags["reopened"]:
            add("Ticket Reopened", "ServiceNow", "AP Clerk", rng.uniform(8, 48), hidden=True, hidden_issue="Ticket Reopened", exception_type=exception)
            add("AP review price mismatch" if exception == "price_mismatch" else "AP review quantity mismatch", "ServiceNow", "AP Clerk", rng.uniform(8, 24), exception_type=exception)
        add("Run three-way match", "SAP", "System", 0.4, exception_type=exception)

    add("Run duplicate invoice check", "SAP", "System", 0.2)
    if exception == "duplicate":
        add("Block invoice", "SAP", "System", 0.1, exception_type="duplicate")
        if flags["bypass"]:
            add("Payment Block Bypass Attempt", "SAP", "AP Clerk", 0.1, status="blocked", hidden=True, hidden_issue="Payment Block Bypass Attempt", exception_type="duplicate")
        add("Finance controller review", "SAP", "Finance Controller", rng.uniform(8, 48), exception_type="duplicate")
        add("Invoice rejected", "SAP", "System", 0.1, status="rejected", exception_type="duplicate")
        return rows

    add("Check vendor risk", "Vendor Master Data", "System", 0.2)
    if vendor_risk == "high":
        add("Compliance review", "Vendor Master Data", "Compliance Officer", rng.uniform(8, 72))
    add("Check approval threshold", "SAP", "System", 0.1)
    if amount > 10000:
        add("Finance manager approval", "SAP", "Finance Manager", rng.uniform(4, 48))
    else:
        add("Auto approve for payment scheduling", "SAP", "System", 0.1)
    add("Schedule payment", "Payment System", "System", rng.uniform(4, 12))
    add("Send remittance notice", "Payment System", "System", 0.1)
    add("Invoice paid", "Payment System", "System", 0.1, status="paid")
    return rows


def pick_exception(rng: random.Random) -> str:
    value = rng.random()
    if value < 0.21:
        return "price_mismatch"
    if value < 0.28:
        return "quantity_mismatch"
    if value < 0.36:
        return "missing_po"
    if value < 0.44:
        return "missing_gr"
    if value < 0.47:
        return "duplicate"
    return ""


def manual_delay(rng: random.Random, flags: dict[str, bool]) -> float:
    base = rng.uniform(24, 120)
    return base + (rng.uniform(24, 72) if flags["queue_delay"] else 0)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            serialized = row.copy()
            serialized["timestamp"] = row["timestamp"].isoformat()
            writer.writerow(serialized)


def summarize_rows(rows: list[dict[str, Any]], seed: int | None = None) -> dict[str, Any]:
    hidden = [row for row in rows if row.get("is_hidden_step")]
    issue_counts: dict[str, int] = {}
    for row in hidden:
        issue = row.get("hidden_issue_type") or "unknown"
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
    top_issue = max(issue_counts.items(), key=lambda item: item[1])[0] if issue_counts else ""
    return {
        "seed": seed,
        "total_events": len(rows),
        "total_cases": len({row["case_id"] for row in rows}),
        "hidden_step_count": len(hidden),
        "hidden_case_rate": round(len({row["case_id"] for row in hidden}) / max(1, len({row["case_id"] for row in rows})), 4),
        "top_hidden_issue": top_issue,
        "hidden_issue_counts": issue_counts,
    }


def parse_csv_rows(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(content.splitlines())
    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    rows: list[dict[str, Any]] = []
    for raw in reader:
        rows.append(
            {
                "case_id": raw["case_id"],
                "invoice_id": raw["invoice_id"],
                "activity": raw["activity"],
                "timestamp": datetime.fromisoformat(raw["timestamp"]),
                "system": raw["system"],
                "role": raw["role"],
                "user_id": raw["user_id"],
                "invoice_amount": float(raw["invoice_amount"]),
                "currency": raw["currency"],
                "country": raw["country"],
                "vendor_id": raw["vendor_id"],
                "vendor_risk": raw["vendor_risk"],
                "po_number": raw["po_number"],
                "exception_type": raw["exception_type"],
                "status": raw["status"],
                "is_hidden_step": str(raw["is_hidden_step"]).lower() in {"1", "true", "yes"},
                "hidden_issue_type": raw["hidden_issue_type"],
            }
        )
    return rows
