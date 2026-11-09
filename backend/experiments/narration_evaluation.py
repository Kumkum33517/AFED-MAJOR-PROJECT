"""Pre-registered in narration_evaluation.md: Qwen narration on 100 held-out alerts, English and Hindi.

    python experiments/narration_evaluation.py           # needs transformers, and downloads the two models once

Step 1 narrates with Qwen and frees it; step 2 judges the English narrations with an NLI model, so the two
never sit in memory together (the whole run fits in 8 GB).
"""
import gc
import hashlib
import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import explain  # noqa: E402

OUT = Path(__file__).parent
NLI_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
DEV, TEST = 30, 100


def alerts() -> list[tuple[int, str, float, list[dict[str, Any]]]]:
    rows = sqlite3.connect(ROOT / "afed.db").execute("select id, level, risk, facts from alerts order by id").fetchall()
    random.Random(1).shuffle(rows)
    return [(i, level, risk, json.loads(facts)) for i, level, risk, facts in rows[DEV:DEV + TEST]]


def reason(output: str, facts: list[dict[str, Any]], language: str) -> str:
    payload = explain._payload(facts, "", 0.0, language)
    source = json.dumps(payload, ensure_ascii=False)
    if not output.strip():
        return "empty"
    if explain.BANNED.search(output):
        return "accusing term"
    if not explain._numbers(output) <= explain._numbers(source):
        return "new number"
    if not explain.is_grounded(output, payload):
        return "new word"
    if not explain.is_complete(output, facts, language):
        return "main fact left out"
    return "accepted"


def narrate_all(test: list) -> list[dict[str, Any]]:
    results = []
    explain.PROVIDERS["local"]("Reply with OK.", "OK")  # load once, outside the timings
    for language in ("en", "hi"):
        system = explain.SYSTEM_PROMPT + (" Write in Hindi using Devanagari script." if language == "hi" else " Write in English.")
        for alert_id, level, risk, facts in test:
            payload = explain._payload(facts, level, risk, language)
            started = time.perf_counter()
            try:
                output = explain.PROVIDERS["local"](system, json.dumps(payload, ensure_ascii=False)).strip() if payload["facts"] else ""
            except Exception as error:  # noqa: BLE001 - reported as a failure, like narrate() does
                output = f"<error {error}>"
            results.append({"alert": alert_id, "language": language, "level": level, "output": output,
                            "seconds": time.perf_counter() - started, "outcome": reason(output, facts, language),
                            "facts": [f["text_hi" if language == "hi" else "text"] for f in facts if f["key"] != "model_rank"][:6]})
            print(f"{language} {alert_id}: {results[-1]['outcome']}", flush=True)
    explain._local_pipeline.cache_clear()
    gc.collect()
    return results


def judge(results: list[dict[str, Any]]) -> None:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL).eval()
    labels = {i: name.lower() for i, name in model.config.id2label.items()}
    for r in results:
        if r["language"] != "en" or not r["output"] or r["output"].startswith("<error"):
            continue
        premise = ". ".join(r["facts"]) + "."
        verdicts = []
        for sentence in [s for s in re.split(r"(?<=[.!?])\s+", r["output"]) if s.strip()]:
            inputs = tokenizer(premise, sentence, return_tensors="pt", truncation=True)
            with torch.no_grad():
                verdicts.append(labels[int(model(**inputs).logits.argmax(-1))])
        r["nli"] = "entailment" if all(v == "entailment" for v in verdicts) else (
            "contradiction" if "contradiction" in verdicts else "neutral")


def report(results: list[dict[str, Any]]) -> None:
    plan = hashlib.sha256((OUT / "narration_evaluation.md").read_bytes()).hexdigest()[:16]
    lines = ["# Qwen narration under the grounding guard: results", "",
             f"Produced by `experiments/narration_evaluation.py`, following `narration_evaluation.md` (SHA-256 {plan}). "
             f"Model `Qwen/Qwen2.5-1.5B-Instruct`, local, half precision, greedy. {TEST} held-out alerts, each in English and Hindi.", "",
             "| Language | Accepted | New word | New number | Main fact left out | Accusing term | Empty or failed | Median seconds |",
             "|---|---|---|---|---|---|---|---|"]
    for language, name in (("en", "English"), ("hi", "Hindi")):
        part = [r for r in results if r["language"] == language]
        c = Counter(r["outcome"] for r in part)
        lines.append(f"| {name} | **{c['accepted']} of {len(part)}** | {c['new word']} | {c['new number']} | {c['main fact left out']} | "
                     f"{c['accusing term']} | {c['empty']} | {median(r['seconds'] for r in part):.1f} |")
    english = [r for r in results if r["language"] == "en" and "nli" in r]
    lines += ["", "## Faithfulness of the English narrations (DeBERTa-v3 NLI, every sentence against the facts)", "",
              "| Narrations | Count | Entailed | Neutral | Contradiction |", "|---|---|---|---|---|"]
    for name, group in (("Accepted by the checks", [r for r in english if r["outcome"] == "accepted"]),
                        ("Rejected by the checks", [r for r in english if r["outcome"] != "accepted"])):
        c = Counter(r["nli"] for r in group)
        lines.append(f"| {name} | {len(group)} | {c['entailment']} | {c['neutral']} | {c['contradiction']} |")
    flagged = [r for r in english if r["outcome"] == "accepted" and r["nli"] == "contradiction"]
    lines += ["", "Accepted English narrations judged a contradiction, to be read by hand:" if flagged else
              "No accepted English narration was judged a contradiction.", ""]
    lines += [f"- Alert {r['alert']}: \"{r['output']}\" (facts: {' | '.join(r['facts'])})" for r in flagged]
    accepted = [r for r in results if r["outcome"] == "accepted"]
    lines += ["", f"Accepted narrations average {mean(len(r['output']) for r in accepted):.0f} characters."
              if accepted else "", "", "## Examples", ""]
    for outcome in ("accepted", "new word", "new number", "main fact left out"):
        for r in [r for r in results if r["outcome"] == outcome][:2]:
            lines.append(f"- {r['language']}, {outcome}: \"{r['output'][:300]}\"")
    (OUT / "narration_evaluation_results.md").write_text("\n".join(lines) + "\n")
    (OUT / ".cache").mkdir(exist_ok=True)
    (OUT / ".cache" / "narration_outputs.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))


def main() -> None:
    results = narrate_all(alerts())
    judge(results)
    report(results)
    print("written")


if __name__ == "__main__":
    main()
