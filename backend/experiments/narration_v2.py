"""Step 2f, pre-registered in narration_v2.md: narration v1 against v2 on 100 new alerts, English and Hindi.

    pip install -r requirements-qwen.txt && python experiments/narration_v2.py
Qwen and the NLI judge are never in memory together, so it fits in 8 GB.
"""
import gc
import json
import random
import re
import time
from collections import Counter
from statistics import median

from v2_common import OUT, raw_frame
from ml import explain, pipeline

NLI_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
REASONS = ["accepted", "new word", "new number", "misplaced number", "main fact left out", "accusing term", "empty or failed"]


def alerts() -> list[dict]:
    scored = pipeline.run_pipeline(raw_frame("afed_synthetic", 11), None, evaluate_labels=False).scored
    rows = scored[scored["level"] != "Low"].sort_values("event_id").to_dict("records")
    random.Random(2).shuffle(rows)
    return [{"event_id": r["event_id"], "level": r["level"], "risk": float(r["risk"]), "facts": explain.build_facts(r, 500_000)} for r in rows[:100]]


def reason(text: str, sources: list[str], facts: list, language: str, per_fact: bool) -> str:
    """Why a narration is refused, in the order the checks run. Per fact, sources hold one fact per sentence."""
    if not text.strip():
        return "empty or failed"
    if explain.BANNED.search(text):
        return "accusing term"
    payload = {"facts": sources}
    if not explain._numbers(text) <= explain._numbers(json.dumps(payload, ensure_ascii=False)):
        return "new number"
    if not explain.is_grounded(text, payload):
        return "new word"
    if not explain.is_complete(text, facts, language):
        return "main fact left out"
    if per_fact and not explain.numbers_anchored(text, sources):
        return "misplaced number"
    return "accepted"


def narrate_all(items: list[dict]) -> list[dict]:
    out = []
    local = explain.PROVIDERS["local"]
    local("Reply with OK.", "OK")  # load once, outside the timings
    for language in ("en", "hi"):
        key = "text_hi" if language == "hi" else "text"
        para_system = explain.SYSTEM_PROMPT + (" Write in Hindi using Devanagari script." if language == "hi" else " Write in English.")
        fact_system = explain.FACT_PROMPT + (" Write in Hindi using Devanagari script." if language == "hi" else " Write in English.")
        for item in items:
            facts = item["facts"]
            payload = explain._payload(facts, item["level"], item["risk"], language)
            started = time.perf_counter()
            para = local(para_system, json.dumps(payload, ensure_ascii=False)).strip().strip('"“”').strip() if payload["facts"] else ""
            para_seconds = time.perf_counter() - started
            main = explain.main_facts([f for f in facts if f["key"] != "model_rank"], key)
            started = time.perf_counter()
            sentences, outcome = [], "accepted"
            for fact in main:  # v2: one fact at a time, each checked on its own; the first refusal decides
                sentence = local(fact_system, fact).strip().strip('"“”').strip()
                sentences.append(sentence)
                why = reason(sentence, [fact], [{"key": "x", "severity": 1.0, "text": fact, "text_hi": fact}], language, True)
                if why != "accepted" and outcome == "accepted":
                    outcome = why
            fact_seconds = time.perf_counter() - started
            out.append({"event_id": item["event_id"], "language": language, "facts": [f[key] for f in facts if f["key"] != "model_rank"][:6],
                        "main": main, "v1": para, "v1_outcome": reason(para, payload["facts"], facts, language, False),
                        "v1_anchored": explain.numbers_anchored(para, payload["facts"]), "v1_seconds": para_seconds,
                        "v2": " ".join(sentences), "v2_sentences": sentences, "v2_outcome": outcome if main else "empty or failed",
                        "v2_seconds": fact_seconds})
            print(language, item["event_id"], out[-1]["v1_outcome"], "|", out[-1]["v2_outcome"], flush=True)
    explain._local_pipeline.cache_clear()
    gc.collect()
    return out


def judge(results: list[dict]) -> None:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL).eval()
    labels = {i: name.lower() for i, name in model.config.id2label.items()}

    def verdict(text: str, premise: str) -> str:
        found = []
        for sentence in [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]:
            with torch.no_grad():
                found.append(labels[int(model(**tokenizer(premise, sentence, return_tensors="pt", truncation=True)).logits.argmax(-1))])
        return "entailment" if found and all(v == "entailment" for v in found) else "contradiction" if "contradiction" in found else "neutral"

    for r in results:
        if r["language"] != "en":
            continue
        premise = ". ".join(r["facts"]) + "."
        r["v1_nli"] = verdict(r["v1"], premise) if r["v1"] else "neutral"
        r["v2_nli"] = verdict(r["v2"], premise) if r["v2"] else "neutral"


def main() -> None:
    items = alerts()
    results = narrate_all(items)
    judge(results)
    summary = {}
    for language in ("en", "hi"):
        part = [r for r in results if r["language"] == language]
        summary[language] = {
            "v1": dict(Counter(r["v1_outcome"] for r in part)), "v2": dict(Counter(r["v2_outcome"] for r in part)),
            "v1_median_seconds": median(r["v1_seconds"] for r in part), "v2_median_seconds": median(r["v2_seconds"] for r in part),
            "v1_accepted_but_misanchored": sum(r["v1_outcome"] == "accepted" and not r["v1_anchored"] for r in part)}
        if language == "en":
            summary[language]["v2_with_nli_gate"] = sum(r["v2_outcome"] == "accepted" and r["v2_nli"] == "entailment" for r in part)
            for arm in ("v1", "v2"):
                for side in ("accepted", "refused"):
                    group = [r for r in part if (r[f"{arm}_outcome"] == "accepted") == (side == "accepted")]
                    summary[language][f"{arm}_nli_{side}"] = dict(Counter(r[f"{arm}_nli"] for r in group))
    flagged = [r for r in results if r["language"] == "en" and ((r["v1_outcome"] == "accepted" and r["v1_nli"] == "contradiction")
                                                                  or (r["v2_outcome"] == "accepted" and r["v2_nli"] == "contradiction"))]
    (OUT / "narration_v2_results.json").write_text(json.dumps({"summary": {l: {**s["v2"]} for l, s in summary.items()},
                                                              "detail": summary, "narrations": results}, indent=1, ensure_ascii=False, default=float))
    L = ["# Qwen narration v2: results", "",
         "Produced by `experiments/narration_v2.py`, following `narration_v2.md`. 100 new alerts (synthetic seed 11), each in English and Hindi. "
         "Qwen2.5-1.5B-Instruct, local, half precision, greedy.", "",
         "| Language | Arm | " + " | ".join(REASONS) + " | Median seconds |", "|---|---|" + "---|" * len(REASONS) + "---|"]
    for language, s in summary.items():
        for arm in ("v1", "v2"):
            L.append(f"| {'English' if language == 'en' else 'Hindi'} | {arm} {'paragraph' if arm == 'v1' else 'per fact'} | "
                     + " | ".join(str(s[arm].get(k, 0)) for k in REASONS) + f" | {s[f'{arm}_median_seconds']:.1f} |")
    en = summary["en"]
    L += ["", f"English v2 accepted that the NLI gate also passes: **{en['v2_with_nli_gate']} of 100**.", "",
          f"v1 narrations that pass the v1 checks but fail the anchor check: English {summary['en']['v1_accepted_but_misanchored']}, "
          f"Hindi {summary['hi']['v1_accepted_but_misanchored']}.", "",
          "## NLI verdicts, English (DeBERTa-v3, every sentence against the alert's facts)", "",
          "| Arm | Narrations | Entailed | Neutral | Contradiction |", "|---|---|---|---|---|"]
    for arm in ("v1", "v2"):
        for side in ("accepted", "refused"):
            c = en[f"{arm}_nli_{side}"]
            L.append(f"| {arm}, {side} | {sum(c.values())} | {c.get('entailment', 0)} | {c.get('neutral', 0)} | {c.get('contradiction', 0)} |")
    L += ["", "Accepted English narrations judged a contradiction, to be read by hand:" if flagged else "No accepted English narration was judged a contradiction.", ""]
    for r in flagged:
        L.append(f"- {r['event_id']}: v1 \"{r['v1']}\" ({r['v1_outcome']}, {r['v1_nli']}); v2 \"{r['v2']}\" ({r['v2_outcome']}, {r['v2_nli']}). Facts: {' | '.join(r['facts'])}")
    (OUT / "narration_v2_results.md").write_text("\n".join(L) + "\n")
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
