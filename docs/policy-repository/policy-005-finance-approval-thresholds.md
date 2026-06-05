# Policy 005: Finance Approval Thresholds

## Policy statement
Invoices above 10,000 EUR require Finance Manager approval before payment scheduling.

## Why the policy exists
Large invoices carry higher financial exposure and must remain under explicit human approval control.

## Allowed actions
- Auto-approve for payment scheduling only when invoice amount is at or below 10,000 EUR and all prior controls pass.
- Route invoices above 10,000 EUR to Finance Manager approval.
- Store approval decision, approver, timestamp, and supporting evidence.

## Blocked actions
- Payment scheduling for invoices above 10,000 EUR without manager approval.
- Splitting invoices to avoid approval threshold.
- AI-generated threshold changes without policy update approval.

## Thresholds
- Finance manager approval required above 10,000 EUR.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Finance Manager approval is required above 10,000 EUR. Finance Controller approval is required for threshold policy changes.

## System enforcement point
SAP approval threshold task and mock agent validator.

## Audit requirements
- Record the policy area: finance approval thresholds.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A 14,500 EUR invoice passes matching and duplicate checks, then waits for Finance Manager approval before scheduling.

## Example non-compliant case
A 14,500 EUR invoice is auto-approved because it is from a preferred vendor.
