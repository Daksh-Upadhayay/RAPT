# Data

| Path | What | In git |
|---|---|---|
| `raw/bitext_customer_support.csv` | [Bitext customer-support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) (CDLA-Sharing-1.0), downloaded by `build_dataset.py` | no |
| `processed/tickets.csv` | category dataset: `text, category, source, group, split` | yes |
| `knowledge_base.json` | 27 policy/FAQ entries (`title`, `content`, `categories`) embedded into the `knowledge_base` table by `seed_knowledge_base.py`; `categories` is used only by `evaluate_retrieval.py` | yes |
| `processed/urgency_tickets.csv` | urgency corpus (v2): same columns, text wrapped in varied urgency phrasing | yes |
| `eval/handwritten_test_set.csv` | 120 hand-written tickets with human `category` + `urgency` labels, written by Claude. Clean for category v1; used to diagnose urgency v1, so no longer clean for urgency | yes |
| `eval/urgency_holdout_test.csv` | 50 tickets with `urgency` labels, written by the project owner. Scored once to choose urgency v2; since v3 part of the urgency **dev set** | yes |
| `eval/urgency_fresh_test.csv` | 64 tickets (17 low / 30 medium / 17 high) written by the project owner after v3 was frozen. Scored once; chose urgency v3 over v2. Since v4 used as training data (with the dev set), so spent | yes |
| `eval/urgency_blind_eval_v2.csv` | 55 tickets (15 low / 15 medium / 25 high) written by the project owner after v4 was frozen. Scored once; confirmed v4 over v3. Now spent for decisions | yes |

Rebuild (from `backend/`): `uv run python -m scripts.build_dataset` and
`uv run python -m scripts.build_urgency_dataset`.

## How `processed/tickets.csv` is made

- 900 rows per category, 5,400 total.
- **Bitext** supplies half of `order_status` (`track_order`), `refund_request`
  (`get_refund`, `track_refund`, `check_refund_policy`) and `cancellation`
  (`cancel_order`, 409 unique rows). Its `{{Order Number}}`-style placeholders are
  filled with random values, and 35% of rows get a tone sentence appended.
- **Templates** (`backend/scripts/ticket_templates.py`) supply the rest, including all of
  `damaged_item`, `delivery_delay` and `product_question`.
- **Split** 70/15/15, grouped: all variants of one template sentence (or one Bitext
  sentence skeleton) stay in the same split.
- There is **no urgency column**. `train_urgency_model.py` labels urgency with the rules
  in `backend/app/ml/weak_labels.py` (weak supervision).

## How `processed/urgency_tickets.csv` is made

The same Bitext + template tickets, built *without* tone sentences, then each wrapped
twice by `backend/scripts/urgency_phrases.py` (30% none, 15% calm, 30% medium, 25% high
phrasing; urgent tickets usually carry 2-3 signals such as a deadline, a threat or
repeat contact). 10,273 rows after de-duplication, grouped 70/15/15 split.

## Urgency dev set (from v3)

`handwritten_test_set.csv` (urgency column) + `urgency_holdout_test.csv` = 170 human-labelled
tickets. Both were already used for decisions, so they are no longer clean tests. They are
used to tune urgency v3: the rules were revised on them, the model and class weights were
chosen on them, so dev scores are optimistic. Load with `scripts.ml_training.load_urgency_dev()`.

## Scoring a fresh test set

A fresh set is a CSV with `text` plus `urgency` and/or `category`, written without
looking at the templates or rules. Score frozen models with (from `backend/`):

```bash
uv run python -m scripts.evaluate_model --model urgency_classifier --versions v1 v2 --eval-set ../data/eval/urgency_holdout_test.csv
```

Once a set has been used to make a decision, it is no longer a clean test for the next version.

## Labelling guidelines

Used to label the hand-written set. The templates follow the same category rules.

**Category:** pick the customer's main issue.
- `damaged_item` wins when the item arrived damaged or defective, even if they ask for a refund.
- `cancellation` wins when they want to stop an order, even if a refund would follow.
  A refund *status* question after a cancellation is `refund_request`.
- `delivery_delay` means the package is past its promised date. "Where is it?", "any
  update?" and "no tracking yet" without a missed date are `order_status`.
- `product_question` covers questions about the product itself (specs, compatibility,
  setup, stock), not about an order.

**Urgency:**
- `high`: any of an explicit deadline or time pressure, repeated contact without an
  answer, a threat (chargeback, dispute, legal, public review), a safety risk, fraud,
  strong anger or abuse.
- `medium`: something has gone wrong and needs action (damage, lateness, missing money,
  errors), or the customer is mildly frustrated, but none of the `high` signals apply.
- `low`: informational questions or simple requests, with nothing broken and no pressure.
