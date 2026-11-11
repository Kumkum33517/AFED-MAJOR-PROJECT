# Qwen narration v2: results

Produced by `experiments/narration_v2.py`, following `narration_v2.md`. 100 new alerts (synthetic seed 11), each in English and Hindi. Qwen2.5-1.5B-Instruct, local, half precision, greedy.

| Language | Arm | accepted | new word | new number | misplaced number | main fact left out | accusing term | empty or failed | Median seconds |
|---|---|---|---|---|---|---|---|---|---|
| English | v1 paragraph | 54 | 46 | 0 | 0 | 0 | 0 | 0 | 1.8 |
| English | v2 per fact | 9 | 80 | 1 | 10 | 0 | 0 | 0 | 1.5 |
| Hindi | v1 paragraph | 60 | 33 | 2 | 0 | 5 | 0 | 0 | 2.8 |
| Hindi | v2 per fact | 37 | 63 | 0 | 0 | 0 | 0 | 0 | 2.6 |

English v2 accepted that the NLI gate also passes: **9 of 100**.

v1 narrations that pass the v1 checks but fail the anchor check: English 3, Hindi 1.

## NLI verdicts, English (DeBERTa-v3, every sentence against the alert's facts)

| Arm | Narrations | Entailed | Neutral | Contradiction |
|---|---|---|---|---|
| v1, accepted | 54 | 47 | 1 | 6 |
| v1, refused | 46 | 19 | 22 | 5 |
| v2, accepted | 9 | 9 | 0 | 0 |
| v2, refused | 91 | 83 | 1 | 7 |

Accepted English narrations judged a contradiction, to be read by hand:

- EV-009217: v1 "Amount Rs. 2,20,354 is 2.9x this vendor's usual of Rs. 75,549." (accepted, contradiction); v2 "The amount of Rs. 2,20,354 is 2.9 times the usual amount from this vendor, which is Rs. 75,549." (misplaced number, entailment). Facts: Amount Rs. 2,20,354 is 2.9x this vendor's usual of Rs. 75,549
- EV-007168: v1 "Matches invoice EV-007151 for Rs. 1,00,228, raised 1 day earlier than usual. Invoice came 1 day after the previous one, while the usual gap is 6 days. Processing took 6 days against the usual 3 days." (accepted, contradiction); v2 "Invoice EV-007151 matches with an amount of Rs. 1,00,228, which was raised one day prior. The invoice arrived 1 day after the previous one, which is 6 days less than usual." (new word, entailment). Facts: Matches invoice EV-007151 for Rs. 1,00,228, raised 1 day earlier | Invoice came 1 day after the previous one, while the usual gap is 6 days | Processing took 6 days against the usual 3 days
- EV-007167: v1 "Amount Rs. 4,58,746 is 27.2x this vendor's usual of Rs. 16,840. Also, 4 invoices just below the Rs. 5,00,000 approval limit within 3 days. Matches invoice EV-007140 for Rs. 4,59,483, raised 1 day earlier. Invoice came 1 day after the previous one, while the usual gap is 8 days." (accepted, contradiction); v2 "The amount of Rs. 4,58,746 is 27.2 times the usual amount from this vendor, which is Rs. 16,840. Four invoices were processed under the Rs. 5,00,000 threshold within three business days. Invoice EV-007140 matches with an amount of Rs. 4,59,483, which was raised one day prior." (misplaced number, contradiction). Facts: Amount Rs. 4,58,746 is 27.2x this vendor's usual of Rs. 16,840 | 4 invoices just below the Rs. 5,00,000 approval limit within 3 days | Matches invoice EV-007140 for Rs. 4,59,483, raised 1 day earlier | 6 invoices in 7 days, 7.4x the expected rate | Invoice came 1 day after the previous one, while the usual gap is 8 days | Amount Rs. 4,58,746 is 92% of the Rs. 5,00,000 approval limit
- EV-004716: v1 "Amount Rs. 4,97,745 is 3.6x this vendor's usual of Rs. 1,39,816 and is 100% of the Rs. 5,00,000 approval limit." (accepted, contradiction); v2 "The amount of Rs. 4,97,745 is 3.6 times the usual amount from this vendor, which is Rs. 1,39,816. Rs. 4,97,745 represents 100% of the Rs. 5,00,000 approval limit." (misplaced number, neutral). Facts: Amount Rs. 4,97,745 is 3.6x this vendor's usual of Rs. 1,39,816 | Amount Rs. 4,97,745 is 100% of the Rs. 5,00,000 approval limit
- EV-009479: v1 "Amount Rs. 1,24,845 is 3.5x this vendor's usual of Rs. 36,040." (accepted, contradiction); v2 "The amount of Rs. 1,24,845 is 3.5 times the usual amount from this vendor, which is Rs. 36,040." (misplaced number, entailment). Facts: Amount Rs. 1,24,845 is 3.5x this vendor's usual of Rs. 36,040
- EV-008468: v1 "3 invoices just below the Rs. 5,00,000 approval limit within 3 days. Also, amount Rs. 4,67,312 is 6.1x this vendor's usual of Rs. 76,833, which is 93% of the Rs. 5,00,000 approval limit." (accepted, contradiction); v2 "Three invoices, each under Rs. 5,00,000, were processed within three business days. The amount of Rs. 4,67,312 is 6.1 times the usual amount from this vendor, which is Rs. 76,833. Rs. 4,67,312 represents 93% of the Rs. 5,00,000 approval limit." (new word, contradiction). Facts: 3 invoices just below the Rs. 5,00,000 approval limit within 3 days | Amount Rs. 4,67,312 is 6.1x this vendor's usual of Rs. 76,833 | Amount Rs. 4,67,312 is 93% of the Rs. 5,00,000 approval limit

## Read by hand (as the plan requires)

Of the six accepted v1 English narrations the NLI judge called a contradiction:

- **Real errors (2):** EV-008468, "...usual of Rs. 76,833, which is 93% of the Rs. 5,00,000 approval limit": the 93%
  belongs to the invoice amount, the known failure of attaching a number to the wrong quantity. EV-007168, "raised 1
  day earlier than usual": the fact says the matching invoice was raised 1 day earlier; "than usual" adds a comparison
  the facts do not make.
- **Judge errors (4):** EV-009217 and EV-009479 copy their fact word for word; EV-007167 and EV-004716 keep each fact's
  meaning ("Amount ... and is 100% of the ... limit" keeps the amount as the subject).

None of the accepted v2 narrations is in that list: all 9 accepted English v2 narrations were judged entailed.

## What this shows

- Per-fact narration removed errors from what it accepted (9 of 9 English accepted were entailed), but acceptance
  fell from 54 to 9 in English and from 60 to 37 in Hindi.
- The v2 checks refuse mostly faithful wording: of the 91 refused English v2 narrations, the NLI judge called 83
  entailed. The per-fact prompt makes Qwen rephrase ("2.9 times the usual amount from this vendor, which is
  Rs. 75,549"), which the word check and the anchor check refuse even when the meaning is kept.
- The anchor check alone flags 3 English v1 narrations that the v1 checks accept, including EV-008468. Adding it to
  paragraph mode was not an arm of this test, so no acceptance figure is claimed for it.
- No default changes: the template stays the default provider and paragraph mode stays the default.
