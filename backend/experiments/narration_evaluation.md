# Qwen narration under the grounding guard: pre-registration

Written on 10 Nov 2026 and committed to git before the test run. Results go to `narration_evaluation_results.md`.

## Question

When a small local Qwen model rewrites an alert's facts, how often is its wording accepted by AFED's checks, how
often is it rejected and why, and are the accepted narrations faithful to the facts?

## Model and settings

`Qwen/Qwen2.5-1.5B-Instruct` through the `local` provider (transformers, half precision, greedy decoding,
at most 200 new tokens), with the prompt and checks in `ml/explain.py` as committed with this file.

## Development and test alerts

The 717 alerts of the demo database (`scripts/seed.py`, seed 42) are shuffled with `random.Random(1)`. The first
30 were used to develop the prompt and checks; they are not reported here. The test set is the next 100. Each
test alert is narrated once in English and once in Hindi.

## Measures

1. **Accepted**: passes both checks: grounding (no number or word beyond the facts and the allowed linking
   words, no accusing term) and completeness (every number of the main facts appears).
2. **Rejection reasons**: new number, new word, accusing term, a main fact left out, empty or failed output.
3. **Faithfulness of English narrations**: an independent natural-language-inference model
   (`MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`) judges each sentence of the narration against the
   alert's fact sentences. A narration counts as entailed when every sentence is judged "entailment". Reported
   for accepted and for rejected narrations separately. Hindi is not judged: the model is English only.
4. **Time** per narration, after the model has loaded.

## What would count as a problem

Any accepted English narration that the inference model judges a contradiction is read by hand and reported
with its text. Nothing is re-run or changed after seeing the test results; changes would need a new test set.
