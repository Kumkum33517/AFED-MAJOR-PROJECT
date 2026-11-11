# Qwen narration v2: one fact at a time, with a number-anchor check (step 2f). Pre-registration

Written and committed on 11 Nov 2026 before `narration_v2.py` first ran. Results: `narration_v2_results.md` and
`narration_v2_results.json`.

## Question

Does narrating one fact at a time, with a check that every number stays beside its own words, remove the known
failure (a number attached to the wrong quantity) without losing too many acceptances?

## Alerts: 100 new ones

Neither the 30 development alerts nor the 100 test alerts of `narration_evaluation` are reused: those came from the
demo database (synthetic seed 42). These 100 come from a fresh run on synthetic seed 11 (v1 settings): its alerts
(Medium and above) shuffled with `random.Random(2)`, the first 100. Each is narrated in English and in Hindi.

## Arms

| Arm | Prompt | Checks |
|---|---|---|
| v1 paragraph | all facts at once (`SYSTEM_PROMPT`) | grounding, completeness (as committed in `ml/explain.py`) |
| v2 per fact | one fact at a time (`FACT_PROMPT`) | per sentence: grounding against its own fact, its numbers kept, number anchors |
| v2 + NLI gate | as v2 | also every English sentence judged "entailment" by DeBERTa-v3 against the facts (English only) |

Model: Qwen2.5-1.5B-Instruct, local, half precision, greedy decoding, as before.

## Measures

Per arm and language: accepted out of 100; reasons for refusal (new word, new number, misplaced number, main fact
left out, accusing term, empty or failed); median seconds per alert. For English: NLI verdicts of accepted and of
refused narrations. Also: how many v1 narrations that pass the v1 checks would fail the anchor check. Every
accepted English narration judged a contradiction is read by hand and quoted.

## No default changes

The template stays the default provider and paragraph stays the default narration mode whatever this shows.
