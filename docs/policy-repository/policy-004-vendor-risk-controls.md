# Policy 004: Vendor Risk Controls

## Policy statement
High-risk vendors require compliance review before approval, auto-resolution, or payment-related configuration.

## Why the policy exists
Vendor risk controls prevent automation from weakening sanctions, compliance, fraud, or onboarding checks.

## Allowed actions
- Retrieve vendor risk status from Vendor Master Data.
- Route high-risk vendor invoices to Compliance Officer review.
- Use low-risk vendor status as one precondition for bounded automation.

## Blocked actions
- Auto-approving high-risk vendor invoices.
- Treating missing vendor risk as low risk.
- Generating payment-related configs when vendor risk evidence is absent.

## Thresholds
- High-risk vendors always require compliance review.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Compliance Officer approval is required for high-risk vendor release and vendor-risk rule changes.

## System enforcement point
Vendor Master Data mock connector, policy retrieval checks, and improvement proposal preconditions.

## Audit requirements
- Record the policy area: vendor risk controls.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A high-risk vendor invoice is routed to compliance review and approved before threshold and payment checks continue.

## Example non-compliant case
An invoice with missing vendor risk is assumed low risk because it has no prior exceptions.
