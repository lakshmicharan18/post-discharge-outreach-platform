# Deterministic safety evaluation

This benchmark contains 21 fixed, synthetic cases: three each for ROUTINE,
CONCERNING, URGENT, AMBIGUOUS, INCOMPLETE, CONFLICTING, and ADVERSARIAL.
No case contains PHI or invokes a network model.

## Safety labels

The binary positive label means escalation or human clinical review is expected.
The benchmark maps `CONCERNING`, `URGENT`, and `INSUFFICIENT_INFORMATION` to a
positive prediction. A consensus decision with `requires_human_review=true` is
also positive, regardless of classification. Only a routine classification with
no review requirement is negative. This mapping is defined in
`app.evaluation.safety.is_safety_positive`, not hidden in tests.

## Method

Each synthetic case supplies three fixed assessor classifications. The runner
passes those classifications to the production `conservative_consensus` policy,
then applies the explicit binary mapping. It records per-case outcome and
category metrics. This evaluates the deterministic policy path without creating
clinical records or granting evaluation code database access.

## Current deterministic result

| Metric | Value |
| --- | ---: |
| TP | 18 |
| FP | 1 |
| TN | 2 |
| FN | 0 |
| Accuracy | 20/21 |
| Precision | 18/19 |
| Recall | 1.0 |
| FNR | 0.0 |

There are no false-negative case IDs in this deterministic run. The report
structure nevertheless always exposes `false_negative_cases`, including each
case ID, category, expected safety label, actual classification, and actual
review/escalation decision when present.

Adversarial inputs include instructions to suppress escalation, malicious
retrieved text, cross-patient disclosure requests, and unauthorized-tool
requests. They remain input data and produce escalation-positive outcomes.

## Limitations

This is a fixed regression benchmark, not a clinical validation study. Its
assessor outputs are deterministic fixtures; it validates conservative consensus
behavior and result accounting, not real-world model quality or clinical safety.
