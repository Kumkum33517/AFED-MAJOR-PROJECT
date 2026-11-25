"""Deterministic facts, a template explanation that always works, and the guarded Qwen narrator.

Facts are computed here, never by a language model. Qwen may only reword them: it receives
just the facts as JSON, and output containing a number absent from the facts, or an
accusation, is thrown away in favour of the template.
"""
import json
import logging
import os
import re
import threading
import unicodedata
from functools import lru_cache
from typing import Any

import pandas as pd
import requests

log = logging.getLogger("afed.explain")

Fact = dict[str, Any]
DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BANNED = re.compile(unicodedata.normalize("NFC", (
    r"fraud|scam|theft|stolen|embezzl|criminal|corrupt|forge|kickback|bribe|launder|illegal|collu|shell compan|"
    r"धोखाधड़ी|धोखा|फ्रॉड|घोटाल|चोरी|जालसाज|फर्जी|रिश्वत|अपराध|भ्रष्टाचार|गबन")), re.IGNORECASE)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD = re.compile(r"[a-z]+|[\u0900-\u0963\u0966-\u097f]+")  # Devanagari without the danda (।, ॥), which is punctuation
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# Besides these, narration may only use words that appear in the facts it was given. A new reason
# needs new words, so this is what stops "shell company", "kickback" or "सात करोड़" reaching a reviewer.
CONNECTIVES = frozenset(unicodedata.normalize("NFC", """
a an the and or but so as at by for from in into of on over to under up with within without while which who whose that this these those
it its is are was were be been being has have had do does did not no also both each more most less than very
flagged flag flags review reviewed reviewer reviewers risk level event events invoice invoices vendor vendors payment payments
amount amounts usual usually normal normally typical typically compared comparison against about around approximately
because due reason reasons main noted note notes shows show
it they there then also additionally too together while whereas however after before same just instead times
है हैं था थे और या का की के को में से पर ने यह ये इस इसे इन उस वह तथा लेकिन क्योंकि जो कि भी ही लिए साथ गया गई गए किया की हुआ हुई
इसलिए कारण मुख्य अन्य जानकारी समीक्षा जोखिम चिह्नित घटना चालान विक्रेता राशि भुगतान सामान्य
""").split())


def inr(amount: float) -> str:
    """Indian digit grouping: 480000 -> Rs. 4,80,000. Paise are dropped; facts quote whole rupees."""
    digits = str(int(round(abs(amount))))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join(([head] if head else []) + groups + [tail])
    return f"Rs. {'-' if amount < 0 else ''}{digits}"


def mask_account(account: Any) -> str:
    text = str(account)
    return "XXXX" + text[-4:] if len(text) >= 4 else "XXXX"


def _ratio(value: float) -> str:
    return f"{value:.1f}x"


def _days(value: float) -> str:
    return f"{value:.0f}"


def _days_en(value: float) -> str:
    return "1 day" if round(value) == 1 else f"{value:.0f} days"


def _fact(key: str, severity: float, text: str, text_hi: str, observed: Any = None, baseline: Any = None,
          ratio: float | None = None) -> Fact:
    return {"key": key, "severity": severity, "text": text, "text_hi": text_hi, "observed": observed,
            "baseline": baseline, "ratio": None if ratio is None else round(float(ratio), 2)}


def _present(value: Any) -> bool:
    return value is not None and not pd.isna(value)


def _safe_id(value: Any) -> str:
    """Uploaded identifiers reach the model inside the facts, so a sentence must not survive as one."""
    return re.sub(r"[^\w.@-]", "", str(value))[:40] or "unknown"


def build_facts(row: dict[str, Any], limit: float) -> list[Fact]:
    """Every fact quotes an observed value and, where one exists, the baseline it was measured against."""
    facts: list[Fact] = []
    amount, baseline, ratio = row["amount"], row.get("baseline_amount"), row.get("amt_ratio", 1.0)
    whose = {"vendor": "this vendor's usual", "peer": "the peer group's usual", "global": "the overall usual"}[row.get("baseline_source", "global")]
    whose_hi = {"vendor": "इस विक्रेता की सामान्य राशि", "peer": "समकक्ष समूह की सामान्य राशि", "global": "कुल सामान्य राशि"}[row.get("baseline_source", "global")]

    if _present(baseline) and (ratio >= 2 or row.get("amt_z", 0) >= 3):
        facts.append(_fact("amount", min(0.5 + ratio / 20, 0.95),
                           f"Amount {inr(amount)} is {_ratio(ratio)} {whose} of {inr(baseline)}",
                           f"राशि {inr(amount)}, {whose_hi} {inr(baseline)} की {_ratio(ratio)} है",
                           inr(amount), inr(baseline), ratio))
    if row.get("flag_invoice_splitting"):
        count = int(row["split_count"])
        facts.append(_fact("invoice_splitting", 0.85,
                           f"{count} invoices just below the {inr(limit)} approval limit within 3 days",
                           f"3 दिनों में {inr(limit)} की अनुमोदन सीमा से ठीक नीचे {count} चालान",
                           count, inr(limit)))
    if row.get("flag_duplicate_invoice"):
        days, matched, other = row["dup_days"], row.get("dup_amount", amount), _safe_id(row["dup_of"])
        when = "the same day" if round(days) == 0 else f"{_days_en(days)} earlier"
        when_hi = "उसी दिन के" if round(days) == 0 else f"{_days(days)} दिन पहले के"
        facts.append(_fact("duplicate_invoice", 0.8,
                           f"Matches invoice {other} for {inr(matched)}, raised {when}",
                           f"{when_hi} चालान {other} ({inr(matched)}) से मेल खाता है",
                           inr(amount), inr(matched), amount / matched))
    if row.get("flag_sod_violation"):
        person = _safe_id(row["created_by"])
        facts.append(_fact("sod_violation", 0.8, f"Created and approved by the same person ({person})",
                           f"एक ही व्यक्ति ({person}) ने बनाया और अनुमोदित किया", person, "two different people"))
    if row.get("flag_bank_change"):
        new, old = mask_account(row["bank_account"]), mask_account(row["usual_bank"])
        facts.append(_fact("bank_change", 0.75, f"Paid to account {new}, not the usual account {old}",
                           f"भुगतान खाता {new} में गया, सामान्य खाता {old} में नहीं", new, old))
    if row.get("flag_new_vendor_large"):
        age = row["vendor_age_days"]
        facts.append(_fact("new_vendor_large", 0.65, f"Vendor is {_days_en(age)} old and this payment is {inr(amount)}",
                           f"विक्रेता {_days(age)} दिन पुराना है और यह भुगतान {inr(amount)} का है", inr(amount), inr(limit), amount / limit))
    if row.get("flag_burst"):
        count, burst = int(row["count_7d"]), row["burst_ratio"]
        expected = row.get("expected_week")
        facts.append(_fact("burst", 0.55, f"{count} invoices in 7 days, {_ratio(burst)} the expected rate",
                           f"7 दिनों में {count} चालान, अपेक्षित दर का {_ratio(burst)}", count,
                           f"{expected:.1f} a week" if _present(expected) else None, burst))
    if row.get("flag_off_hours_approval") and _present(row.get("approval_date")):
        when = pd.Timestamp(row["approval_date"])
        day, day_hi = DAYS_EN[when.day_of_week], DAYS_HI[when.day_of_week]
        if row.get("approval_timed"):
            clock = when.strftime("%H:%M")
            text, text_hi, observed = f"Approved at {clock} on a {day}, outside working hours", f"{day_hi} को {clock} बजे अनुमोदित, कार्य समय से बाहर", clock
        else:  # the record has a date only, so no clock time may be quoted
            text, text_hi, observed = f"Approved on a {day}, outside working days", f"{day_hi} को अनुमोदित, कार्य दिवसों से बाहर", day
        facts.append(_fact("off_hours_approval", 0.45, text, text_hi, observed, "weekdays 07:00 to 21:00"))
    if row.get("flag_rushed_approval"):
        usual = row["base_proc"]
        facts.append(_fact("rushed_approval", 0.45, f"Approved the same day, while the usual is {_days_en(usual)}",
                           f"उसी दिन अनुमोदित, जबकि सामान्यतः {_days(usual)} दिन लगते हैं", "same day", _days_en(usual)))
    if row.get("flag_round_amount"):
        facts.append(_fact("round_amount", 0.45, f"Amount {inr(amount)} is an exact multiple of {inr(10_000)}",
                           f"राशि {inr(amount)}, {inr(10_000)} का सटीक गुणज है", inr(amount), None))
    if row.get("freq_z", 0) >= 3 and _present(row.get("gap_days")) and _present(row.get("base_gap")):
        gap, usual = row["gap_days"], row["base_gap"]
        after = "on the same day as the previous one" if round(gap) == 0 else f"{_days_en(gap)} after the previous one"
        after_hi = "पिछले वाले के उसी दिन" if round(gap) == 0 else f"पिछले के {_days(gap)} दिन बाद"
        facts.append(_fact("frequency", 0.4, f"Invoice came {after}, while the usual gap is {_days_en(usual)}",
                           f"चालान {after_hi} आया, जबकि सामान्य अंतर {_days(usual)} दिन है", _days_en(gap), _days_en(usual),
                           usual / gap if gap > 0 else None))
    proc_z = row.get("proc_z", 0)
    if abs(proc_z) >= 3 and _present(row.get("base_proc")) and _present(row.get("processing_days")) and not row.get("flag_rushed_approval"):
        taken, usual = row["processing_days"], row["base_proc"]
        # Fast approval raises the risk score; slow approval does not, so it is only ever an aside.
        fast = proc_z < 0
        facts.append(_fact("processing", 0.4 if fast else 0.15,
                           f"{'Approved' if fast else 'Processing took'} {'in ' if fast else ''}{_days_en(taken)} against the usual {_days_en(usual)}",
                           f"{'अनुमोदन' if fast else 'प्रक्रिया'} में {_days(taken)} दिन लगे, सामान्यतः {_days(usual)} दिन",
                           _days_en(taken), _days_en(usual), taken / usual if usual else None))
    if row.get("flag_near_limit"):
        share = amount / limit * 100
        facts.append(_fact("near_limit", 0.2, f"Amount {inr(amount)} is {share:.0f}% of the {inr(limit)} approval limit",
                           f"राशि {inr(amount)}, {inr(limit)} की अनुमोदन सीमा का {share:.0f}% है", inr(amount), inr(limit)))
    if row.get("baseline_source") in ("peer", "global"):
        history = int(row.get("history_len", 0))
        facts.append(_fact("thin_history", 0.1, f"Only {history} earlier invoices, so {whose.replace(' usual', '')} baseline was used",
                           f"केवल {history} पिछले चालान, इसलिए तुलनात्मक आधार का उपयोग किया गया", history, 8))
    percentile = row.get("if_percentile")
    if _present(percentile):
        share = min(float(percentile) * 100, 99.9)  # no event is more unusual than all of them, itself included
        facts.append(_fact("model_rank", 0.05, f"Overall pattern is more unusual than {share:.1f}% of events",
                           f"समग्र पैटर्न {share:.1f}% घटनाओं से अधिक असामान्य है", f"{share:.1f}%", None))
    return sorted(facts, key=lambda f: -f["severity"])


def main_facts(facts: list[Fact], key: str = "text") -> list[str]:
    """The reasons an explanation must give: up to three facts of real weight, or the first one."""
    return [f[key] for f in facts if f["severity"] >= 0.2 and f["key"] != "thin_history"][:3] or [f[key] for f in facts[:1]]


def template_explanation(facts: list[Fact], level: str, risk: float, language: str = "en") -> str:
    """The reasons, one sentence each, straight from the facts. This path has no dependencies and cannot fail.

    The level and risk score are not repeated: every screen and report shows them beside the text.
    """
    key = "text_hi" if language == "hi" else "text"
    main = main_facts(facts, key)
    other = [f[key] for f in facts if f[key] not in main and f["key"] != "model_rank"][:1]
    if not main:  # nothing computed to explain with: say only what the score says
        names = {"Low": "कम", "Medium": "मध्यम", "High": "उच्च", "Critical": "गंभीर"}
        return (f"समीक्षा के लिए {names.get(level, level)} जोखिम ({risk:.2f}) पर चिह्नित।" if language == "hi"
                else f"Flagged for review at {level} risk ({risk:.2f}).")
    if language == "hi":
        return "। ".join(main) + "।" + (f" अन्य जानकारी: {other[0]}।" if other else "")
    return ". ".join(main) + "." + (f" Also noted: {other[0]}." if other else "")


SYSTEM_PROMPT = (
    "You join audit facts into 2 or 3 short, plain sentences for a procurement reviewer. "
    "The facts are already correct sentences. Keep each fact's own words and copy every number exactly, as digits. "
    "You may only reorder the facts, join them with short linking words such as and, also, while, because, "
    "and drop a fact that repeats another. Do not explain, interpret, judge or add advice, and do not say what a fact "
    "might mean. Do not restate the risk level. Never accuse anyone. Output only the sentences.\n\n"
    "Example facts: [\"Amount Rs. 2,40,000 is 4.0x this vendor's usual of Rs. 60,000\", "
    "\"Approved on a Sunday\", \"Paid to account XXXX1234, not the usual account XXXX5678\"]\n"
    "Example output: Amount Rs. 2,40,000 is 4.0x this vendor's usual of Rs. 60,000. "
    "It was approved on a Sunday and paid to account XXXX1234, not the usual account XXXX5678."
)


def _numbers(text: str) -> set[str]:
    cleaned = text.translate(DEVANAGARI_DIGITS)
    found = set()
    for match in NUMBER.findall(cleaned):
        value = match.replace(",", "").rstrip(".")
        found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return found


def _payload(facts: list[Fact], level: str, risk: float, language: str) -> dict[str, Any]:
    """Everything the model is shown, and so everything it may repeat: the finished fact sentences only.

    Raw observed values, baselines and ratios are left out on purpose: shown them, a small model re-derives
    its own numbers and gets them wrong. Level and risk are left out because the screen shows them already.
    """
    key = "text_hi" if language == "hi" else "text"
    return {"facts": [f[key] for f in facts[:6] if f["key"] != "model_rank"]}


def is_grounded(output: str, payload: dict[str, Any]) -> bool:
    """True only if the narration adds no number, no word beyond the facts and connectives, and no accusation.

    Deliberately strict. A free rewording fails this and the template is used instead, because
    a check that passes new words cannot tell a synonym from an invented reason.
    """
    text = unicodedata.normalize("NFC", output)
    if not text.strip() or BANNED.search(text):
        return False
    source = unicodedata.normalize("NFC", json.dumps(payload, ensure_ascii=False))
    if not _numbers(text) <= _numbers(source):
        return False
    return set(WORD.findall(text.lower())) <= set(WORD.findall(source.lower())) | CONNECTIVES


def is_complete(output: str, facts: list[Fact], language: str = "en") -> bool:
    """True if every number in the main facts appears in the narration, so no reason was dropped.

    The grounding check stops additions; this stops omissions, such as a rewording that keeps the amount
    and quietly leaves out the change of bank account.
    """
    key = "text_hi" if language == "hi" else "text"
    needed = set().union(*(_numbers(text) for text in main_facts(facts, key)))
    return needed <= _numbers(unicodedata.normalize("NFC", output))


def _hf_api(system: str, user: str) -> str:
    response = requests.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"},
        json={"model": os.getenv("QWEN_HF_MODEL", "Qwen/Qwen2.5-7B-Instruct"), "temperature": 0.2, "max_tokens": 300,
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _ollama(system: str, user: str) -> str:
    response = requests.post(
        f"{os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')}/api/chat",
        json={"model": os.getenv("QWEN_OLLAMA_MODEL", "qwen2.5:3b"), "stream": False, "options": {"temperature": 0.2},
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        timeout=60)
    response.raise_for_status()
    return response.json()["message"]["content"]


@lru_cache(maxsize=1)
def _local_pipeline() -> Any:
    import torch
    from transformers import pipeline  # optional and heavy, so only imported when selected
    # Half precision: a 1.5B model needs about 3 GB instead of 6, which fits beside the app on an 8 GB machine.
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cpu" else torch.float16
    return pipeline("text-generation", model=os.getenv("QWEN_LOCAL_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"), dtype=dtype, device=device)


_local_lock = threading.Lock()  # one model in memory, used by the API's worker threads: one generation at a time


def _local(system: str, user: str) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    with _local_lock:
        return _local_pipeline()(messages, max_new_tokens=200, do_sample=False)[0]["generated_text"][-1]["content"]


PROVIDERS = {"hf_api": _hf_api, "ollama": _ollama, "local": _local}


TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|[a-z]+|[\u0900-\u0963\u0966-\u097f]+")
# Function words only, plus currency, the "x" of "9.6x" and the "s" of "vendor's": anchors must be words that say
# what a number measures (amount, usual, limit, days), so these are skipped when looking for one.
NOT_ANCHORS = frozenset(unicodedata.normalize("NFC", """
a an the and or but so as at by for from in into of on over to under up with within without while which who whose that this
these those it its is are was were be been being has have had do does did not no also both each than very there then too
together whereas however same just instead times rs x s
है हैं था थे और या का की के को में से पर ने यह ये इस इसे इन उस वह तथा लेकिन क्योंकि जो कि भी ही लिए साथ
""").split())


def _anchors(text: str) -> set[tuple[str, str]]:
    """(number, nearest preceding meaningful word) pairs. "^" when nothing meaningful comes before the number."""
    pairs, anchor = set(), "^"
    for token in TOKEN.findall(unicodedata.normalize("NFC", text).translate(DEVANAGARI_DIGITS).lower()):
        if token[0].isdigit():
            value = token.replace(",", "").rstrip(".")
            pairs.add((value.rstrip("0").rstrip(".") if "." in value else value, anchor))
        elif token not in NOT_ANCHORS:
            anchor = token
    return pairs


def numbers_anchored(output: str, sources: list[str]) -> bool:
    """True if every number in the output follows the same meaningful word as it does in some source fact.

    Catches a number moved to the wrong quantity: "usual of Rs. 2,35,735, which is 91% of the limit" puts 91 after
    "usual", while the fact says "Amount Rs. 4,55,872 is 91% of the ... limit". The word check alone passes it.
    """
    allowed = set().union(*(_anchors(text) for text in sources)) if sources else set()
    return _anchors(output) <= allowed


FACT_PROMPT = (
    "Rewrite this single audit fact as one short, plain sentence for a procurement reviewer. Keep its own words and "
    "copy every number exactly, as digits. Do not add, explain, interpret, judge or advise, and never accuse anyone. "
    "Output only the sentence.\n\nExample fact: Approved at 22:38 on a Tuesday, outside working hours\n"
    "Example output: It was approved at 22:38 on a Tuesday, outside working hours."
)


def narrate_per_fact(facts: list[Fact], level: str, risk: float, language: str, provider: str) -> tuple[str, str]:
    """Narration v2: one fact at a time, each sentence checked against its own fact only, plus the anchor check.

    Each main fact is reworded on its own, so the model never has two facts' numbers to mix. Every sentence must pass
    grounding, keep its fact's numbers, and keep each number beside its own words. Any failure: the whole template.
    """
    fallback = template_explanation(facts, level, risk, language)
    key = "text_hi" if language == "hi" else "text"
    main = main_facts([f for f in facts if f["key"] != "model_rank"], key) if any(f["key"] != "model_rank" for f in facts) else []
    if provider not in PROVIDERS or not main:
        return fallback, "template"
    system = FACT_PROMPT + (" Write in Hindi using Devanagari script." if language == "hi" else " Write in English.")
    sentences = []
    for fact in main:
        try:
            sentence = PROVIDERS[provider](system, fact).strip().strip('"“”').strip()
        except Exception as error:  # an outage must never block an alert
            log.warning("Qwen provider %s failed: %s", provider, error)
            return fallback, "template"
        payload = {"facts": [fact]}
        if not (is_grounded(sentence, payload) and _numbers(fact) <= _numbers(sentence) and numbers_anchored(sentence, [fact])):
            log.warning("Qwen per-fact output rejected: %r", sentence[:200])
            return fallback, "template"
        sentences.append(sentence if sentence.endswith((".", "।")) else sentence + ("।" if language == "hi" else "."))
    other = [f[key] for f in facts if f[key] not in main and f["key"] != "model_rank"][:1]
    tail = (f" अन्य जानकारी: {other[0]}।" if language == "hi" else f" Also noted: {other[0]}.") if other else ""
    return " ".join(sentences) + tail, provider


def narrate(facts: list[Fact], level: str, risk: float, language: str = "en", provider: str = "template",
            mode: str = "paragraph") -> tuple[str, str]:
    """Return (text, provider actually used). Any failure or ungrounded output falls back to the template.

    mode "paragraph" is v1 (all facts at once); "per_fact" is narration v2 (narrate_per_fact).
    """
    if mode == "per_fact":
        return narrate_per_fact(facts, level, risk, language, provider)
    fallback = template_explanation(facts, level, risk, language)
    if provider not in PROVIDERS:
        return fallback, "template"
    payload = _payload(facts, level, risk, language)
    if not payload["facts"]:  # only the model's rank to go on: nothing for a narrator to join
        return fallback, "template"
    system = SYSTEM_PROMPT + (" Write in Hindi using Devanagari script." if language == "hi" else " Write in English.")
    try:
        output = PROVIDERS[provider](system, json.dumps(payload, ensure_ascii=False)).strip().strip('"“”').strip()  # small models often quote their answer
    except Exception as error:  # A narrator outage must never block an alert: the template is always available.
        log.warning("Qwen provider %s failed: %s", provider, error)
        return fallback, "template"
    if not is_grounded(output, payload):
        log.warning("Qwen output rejected by the grounding check: %r", output[:200])
        return fallback, "template"
    if not is_complete(output, facts, language):
        log.warning("Qwen output rejected for leaving out a main fact: %r", output[:200])
        return fallback, "template"
    return output, provider
