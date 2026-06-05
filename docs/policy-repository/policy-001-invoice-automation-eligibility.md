# Policy 001: Invoice Automation Eligibility

## Policy statement
Invoice automation is permitted only for low-risk, fully evidenced cases that have passed the required process controls.

## Why the policy exists
The invoice process includes financial controls, vendor-risk controls, and duplicate-payment controls. Automation must reduce manual load without bypassing those controls.

## Allowed actions
- Recommend automation candidates from mined evidence and retrieved SOP or policy context.
- Generate disabled mock workflow rules for low-risk cases after human approval.
- Route invoices to payment scheduling only after duplicate check, vendor risk check, and approval threshold checks are satisfied.

## Blocked actions
- Automating invoices with missing PO, missing goods receipt, high-risk vendor status, failed duplicate check, or unresolved compliance review.
- Using hidden email or spreadsheet activity as an approved automation path.
- Executing any generated configuration without human approval.

## Thresholds
- Duplicate invoice check must pass before any payment-related automation.
- High-risk vendors always require compliance review.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Process Owner approval is required for workflow changes. Finance Controller approval is required when the action affects payment eligibility.

## System enforcement point
Improve Process proposal validation and agent execution precondition checks.

## Audit requirements
- Record the policy area: invoice automation eligibility.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A low-risk invoice with PO, goods receipt, passed duplicate check, and amount below approval threshold is proposed for auto-routing, then approved before mock config generation.

## Example non-compliant case
A missing goods receipt invoice is auto-routed to payment scheduling because the AI inferred that receipt would arrive later.
