# Qwen narration under the grounding guard: results

Produced by `experiments/narration_evaluation.py`, following `narration_evaluation.md` (SHA-256 e15023bb12e5f191). Model `Qwen/Qwen2.5-1.5B-Instruct`, local, half precision, greedy. 100 held-out alerts, each in English and Hindi.

| Language | Accepted | New word | New number | Main fact left out | Accusing term | Empty or failed | Median seconds |
|---|---|---|---|---|---|---|---|
| English | **46 of 100** | 54 | 0 | 0 | 0 | 0 | 1.6 |
| Hindi | **61 of 100** | 29 | 7 | 3 | 0 | 0 | 2.6 |

## Faithfulness of the English narrations (DeBERTa-v3 NLI, every sentence against the facts)

| Narrations | Count | Entailed | Neutral | Contradiction |
|---|---|---|---|---|
| Accepted by the checks | 46 | 43 | 1 | 2 |
| Rejected by the checks | 54 | 33 | 17 | 4 |

Accepted English narrations judged a contradiction, to be read by hand:

- Alert 248: "Amount Rs. 4,55,872 is 1.9x this vendor's usual of Rs. 2,35,735, which is 91% of the Rs. 5,00,000 approval limit." (facts: Amount Rs. 4,55,872 is 1.9x this vendor's usual of Rs. 2,35,735 | Amount Rs. 4,55,872 is 91% of the Rs. 5,00,000 approval limit)
- Alert 160: "Amount Rs. 1,01,302 is 3.3x this vendor's usual of Rs. 30,741. Processing took 10 days against the usual 6 days." (facts: Amount Rs. 1,01,302 is 3.3x this vendor's usual of Rs. 30,741 | Processing took 10 days against the usual 6 days)

Accepted narrations average 76 characters.

## Examples

- en, accepted: "Amount Rs. 2,67,921 is 1.7x this vendor's usual of Rs. 1,56,939."
- en, accepted: "The invoice came 1 day after the previous one, while the usual gap is 7 days. Processing took 5 days against the usual 2 days."
- en, new word: "The order was approved the same day, while the usual process takes 2 days."
- en, new word: "Invoices arrived three times faster than usual, at an alarming 3.2 times the normal pace."
- hi, new number: "दैनिक समय में 3 चालान रु. 3200 होते हैं।"
- hi, new number: "दैनिक समय में 3 चालान रु. 3,100 प्रति दिन वाली आवश्यक दर के बराबर है।"
- hi, main fact left out: "दिनों में 6 चालान, अपेक्षित दर का 12.8x है।"
- hi, main fact left out: "चालान पिछले वाले के उसी दिन आया। इसलिए सामान्य अंतर का उपयोग किया गया।"
