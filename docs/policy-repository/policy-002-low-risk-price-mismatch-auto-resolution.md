# Policy 002: Low-Risk Price Mismatch Auto-Resolution

## Policy statement
Low-risk price mismatch auto-resolution may be proposed only for tightly bounded cases below the defined amount and tolerance thresholds.

## Why the policy exists
Price mismatch loops are a major AP delay source, but incorrect auto-resolution can create overpayment and audit risk.

## Allowed actions
- Propose auto-resolution when vendor risk is low, invoice amount is below 1,000 EUR, mismatch is at or below 1.5 percent, duplicate check passed, and goods receipt exists.
- Generate a disabled Coupa mock exception rule with audit notes and fallback to AP manual review.
- Monitor reopened ticket rate and exception reversal rate after approval.

## Blocked actions
- Auto-resolving high-risk vendor price mismatches.
- Auto-resolving any mismatch above 1,000 EUR or above 1.5 percent.
- Skipping duplicate invoice control or goods receipt evidence.

## Thresholds
- Low-risk price mismatch auto-resolution can be proposed only below 1,000 EUR.
- Price mismatch tolerance for demo is 1.5 percent.
- Duplicate invoice check must pass before any payment-related automation.
- High-risk vendors always require compliance review.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Finance Controller and Compliance Officer approval are required before agent execution.

## System enforcement point
Coupa mock configuration schema, improvement action approval status, and RAG policy retrieval.

## Audit requirements
- Record the policy area: low-risk price mismatch auto-resolution.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A 740 EUR invoice from a low-risk vendor has a 1.1 percent price mismatch, passed duplicate check, and goods receipt exists. A disabled mock auto-resolution rule is generated after approval.

## Example non-compliant case
A 1,350 EUR invoice with a 1.2 percent price mismatch is auto-resolved because the mismatch percentage is low.
