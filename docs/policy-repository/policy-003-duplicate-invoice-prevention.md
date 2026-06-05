# Policy 003: Duplicate Invoice Prevention

## Policy statement
Duplicate invoice check must pass before any payment-related action, auto-resolution, or payment scheduling recommendation.

## Why the policy exists
Duplicate reprocessing is a high-impact control failure. It can create duplicate payments and weakens audit evidence.

## Allowed actions
- Block invoices where duplicate check fails.
- Route blocked invoices to Finance Controller review.
- Release blocked invoices only after documented controller decision.

## Blocked actions
- Payment scheduling before duplicate check result exists.
- Payment block bypass attempts.
- AI recommendations that treat duplicate status as unknown but proceed anyway.

## Thresholds
- Duplicate invoice check must pass before any payment-related automation.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Finance Controller approval is required to release a blocked invoice. Process Owner approval is required for duplicate-check rule changes.

## System enforcement point
SAP mock payment block, mined hidden-path detection, and agent config validator.

## Audit requirements
- Record the policy area: duplicate invoice prevention.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
Duplicate check fails, invoice is blocked, Finance Controller reviews evidence, and only then releases or rejects the invoice.

## Example non-compliant case
An AP Clerk attempts Payment Block Bypass Attempt after duplicate check fails.
