# Policy 006: Payment Block Controls

## Policy statement
Payment blocks must not be bypassed. Release requires documented controller review and preserved audit evidence.

## Why the policy exists
Payment block bypass is a critical hidden-risk path that can lead to duplicate or unauthorized payments.

## Allowed actions
- Create a payment block when duplicate check fails or required control evidence is missing.
- Release a payment block after Finance Controller review.
- Generate monitoring alerts for bypass attempts.

## Blocked actions
- Manual payment block bypass.
- Agent-generated config that enables payment release automatically.
- Payment scheduling when block status is active or unknown.

## Thresholds
- Duplicate invoice check must pass before any payment-related automation.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Finance Controller approval is required for release. Process Owner approval is required for block-control workflow changes.

## System enforcement point
SAP mock payment block controls and agent schema validation.

## Audit requirements
- Record the policy area: payment block controls.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
Duplicate check fails, SAP blocks payment, controller reviews, and rejection or release is logged.

## Example non-compliant case
An AP Clerk uses a hidden bypass step to schedule payment before controller review.
