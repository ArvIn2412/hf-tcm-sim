# M6d — protocol for receiving and evaluating author clarification

**Preparation only.** No author response is currently recorded. This protocol
does not authorize changing code, configuration, ADR status, or historical
results after a response.

## 1. Preserve the received evidence

For every response, create a new immutable intake record under a distinct
author-response namespace (for example, `docs/author_responses/<response-id>/`).
Do not overwrite this protocol, the M6d ledger, the M6c/M6b files, or M5
outputs. Record:

- intake ID and date/time received, including timezone;
- exact source document/version being discussed;
- source type: signed letter, email, tracked manuscript, official supplement,
  or other (describe);
- sender/author name and role **only if verifiable in the received material**;
- message/document provenance, original filename, and SHA-256 of original
  bytes; retain an unedited original where permitted;
- the exact question IDs Q1–Q7 answered and any cross-references;
- exact mathematical notation/table/example as received, preserving indices,
  signs, superscripts, bit order, and units;
- any transcription separately from the source, identifying who transcribed
  it and how it was checked;
- unresolved subquestions, caveats, and statements that are opinions rather
  than formal definitions.

Do not use an informal paraphrase as an exact equation. If a screenshot,
attachment, or equation is unreadable, mark that item `SOURCE_UNAVAILABLE` and
request a clearer copy rather than reconstructing it.

## 2. Evidence classification

For each received statement, append a new evidence row; do not modify the
historical M6d claim. Classify it as:

- `AUTHOR_CONFIRMED` only when direct, attributable author evidence explicitly
  answers that exact definition;
- `SOURCE_EXPLICIT` when the received authoritative document itself prints the
  definition, whether or not an email also points to it;
- `SOURCE_DERIVABLE` only when the result follows uniquely from explicit
  definitions;
- `SOURCE_AMBIGUOUS` when multiple readings remain;
- `EXTERNAL_REFERENCE_ONLY` for [B], [C], or another work not explicitly
  adopted by [A];
- `UNAVAILABLE` when evidence cannot be read or is not supplied.

One answer may resolve one part of a question and leave other parts open. Do
not propagate a confirmation from the label `b` to state numbering, bit order,
complex I/Q convention, sample timing, or update semantics unless those are
also directly defined.

## 3. Independent review and reconciliation

1. Map each answer to Q1–Q7 and quote only the minimum text needed, with a
   page/figure/table/equation or message locator.
2. Independently transcribe any equations and compare signs, summation bounds,
   conditioning, and time indices against the original response.
3. For a provided numerical example, hand-compute it in a separate review
   record. Do not use the receiver implementation as its own oracle.
4. Update the evidence matrix in a **new versioned copy** and preserve both the
   prior matrix hash and the new matrix hash.
5. Record disagreements between the answer and current project conventions as
   explicit discrepancies, not silent corrections.
6. Leave every unanswered item OPEN and name the missing evidence.

## 4. If the answer differs from project ADR-002

If an authoritative mapping differs from ADR-002:

- preserve ADR-002 as the historical accepted reconstructed convention;
- record the exact source/project discrepancy and evidence provenance;
- do not rewrite M5f/M5h/M5j/M6b results, code fingerprints, or hashes;
- do not run source-aligned BER tests or alter `iq_prediction.py`;
- propose a separate source-aligned branch and precise scientific comparison;
- require a separate explicit user decision before any implementation or
  receiver evaluation.

The same approval boundary applies to ADR-005, ADR-012, estimator clocks, and
`U⁰`/`U**` treatment. A source clarification alone is not an implementation
authorization or a new ADR.

## 5. Current intake state

| Field | State |
|---|---|
| Author response records | None |
| Questions with author confirmation | None |
| `paper_exact` | `false` |
| `receiver_enabled` | `false` |
| SCI-02 / SCI-03 / SCI-METRIC-02 | OPEN |
| Receiver change / M6e authorization | None |
