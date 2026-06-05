# SOP 001: Invoice Intake and Data Validation

## Purpose
Define the governed procedure for invoice intake and data validation in the invoice exception handling process.

## Scope
Applies to synthetic Coupa, SAP, ServiceNow, Vendor Master Data, Payment System, and policy repository records in this local demo.

## Systems involved
Coupa, SAP, ServiceNow, Vendor Master Data, and Payment System as applicable to the canonical BPM process.

## Roles involved
AP Clerk, Procurement Specialist, Finance Manager, Finance Controller, Compliance Officer, and System.

## Trigger
The procedure starts when the process reaches invoice intake and data validation or an exception related to that area is detected.

## Step-by-step procedure
Follow the canonical BPM sequence, record every status change, keep exception work inside governed systems, and retry the canonical control point after correction.

## Required data fields
case_id, invoice_id, activity, timestamp, system, role, invoice_amount, currency, vendor_id, vendor_risk, po_number, exception_type, and status.

## Control points
Three-way match, duplicate invoice check, vendor risk check, approval threshold, compliance review, and controller review where applicable.

## Evidence required
System event timestamp, actor role, source system, exception ticket reference, control result, approval decision, and audit note.

## Exceptions
Missing PO, price mismatch, quantity mismatch, missing goods receipt, duplicate invoice, high-risk vendor, approval delay, and reopened ticket.

## Escalation path
AP Team Lead for queue delay, Procurement Specialist for PO or receipt correction, Finance Controller for duplicate or block review, Compliance Officer for high-risk vendors.

## Audit log requirements
Log inputs, decision, approver, timestamp, source document, system state before and after, and any retry path.

## KPIs
Cycle time hours, exception rate, hidden step rate, SLA breach estimate, first-pass match rate, duplicate block rate, and approval aging.

## Common failure modes
Manual email review, Excel correction, reopened tickets, missing evidence, duplicate reprocessing, and unapproved payment block bypass attempts.
