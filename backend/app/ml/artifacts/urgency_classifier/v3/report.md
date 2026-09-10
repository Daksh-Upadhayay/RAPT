# Urgency classifier v3

Weak supervision: keyword/heuristic rules (`app/ml/weak_labels.py`) label the training
data (`urgency_tickets.csv`), then four candidates learn from those labels:
TF-IDF word 1-2-grams + tone features (VADER, caps, `!`/`?`, length), with or without
sentence embeddings (`all-MiniLM-L6-v2`), each through logistic regression and XGBoost.
The best candidate on the **human-labelled dev set** (170 tickets) is shipped,
with per-class probability weights tuned on the same dev set:

**Shipped: LogReg tfidf+tone+emb**, class weights low ×1.0, medium ×1.25, high ×3.0.

Weak label distribution (train, 7163 rows):
low 3018 (42%), medium 2607 (36%), high 1538 (21%).

## Summary

| model | val (weak) macro-F1 / acc | test (weak) macro-F1 / acc | dev (human) macro-F1 / acc |
|---|---|---|---|
| LogReg tfidf+tone | 0.91 / 0.91 | 0.79 / 0.79 | 0.71 / 0.71 |
| XGBoost tfidf+tone | 0.92 / 0.92 | 0.80 / 0.80 | 0.60 / 0.60 |
| LogReg tfidf+tone+emb | 0.89 / 0.89 | 0.81 / 0.81 | 0.75 / 0.74 |
| XGBoost tfidf+tone+emb | 0.91 / 0.91 | 0.78 / 0.79 | 0.61 / 0.62 |
| LogReg tfidf+tone+emb + weights | 0.87 / 0.87 | 0.81 / 0.82 | 0.78 / 0.78 |

**Rules alone on the dev set:** macro-F1 0.91 / accuracy 0.90.

- **val / test (weak)**: agreement with the rules' labels on held-out data. This measures
  how well a model *learned the rules*.
- **dev (human)**: human labels. The rules were revised on this set and the model and
  class weights were chosen on it, so **all dev numbers (rules included) are optimistic**.
  They are for comparing candidates, not for reporting.
- **The real number** comes from a fresh set scored once with `scripts/evaluate_model.py`.

## Shipped model: dev set (human labels)

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| low | 0.79 | 0.77 | 0.78 | 57 |
| medium | 0.81 | 0.67 | 0.73 | 63 |
| high | 0.76 | 0.94 | 0.84 | 50 |
| **macro avg** | | | **0.78** | 170 |

Accuracy: 0.78

| true \ predicted | low | medium | high |
|---|---|---|---|
| **low** | 44 | 8 | 5 |
| **medium** | 11 | 42 | 10 |
| **high** | 1 | 2 | 47 |

### Rules alone

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| low | 0.84 | 0.89 | 0.86 | 57 |
| medium | 0.88 | 0.84 | 0.86 | 63 |
| high | 1.00 | 0.98 | 0.99 | 50 |
| **macro avg** | | | **0.91** | 170 |

Accuracy: 0.90

| true \ predicted | low | medium | high |
|---|---|---|---|
| **low** | 51 | 6 | · |
| **medium** | 10 | 53 | · |
| **high** | · | 1 | 49 |

### Tickets the shipped model got wrong

| text | true | predicted | conf |
|---|---|---|---|
| Hi there, I ordered a pair of hiking boots on Sunday and the confirmation email said I'd get tracking within 48 hours. It's Tuesday night an… | low | high | 0.35 |
| Hello, I placed order #40213 for a standing desk frame. Could you let me know which courier it's going with? I want to make sure someone's h… | low | high | 0.25 |
| Hey, I bought a gift card and a lamp last week. The gift card showed up by email but the lamp order just says 'awaiting fulfilment'. Is that… | low | high | 0.53 |
| Just wanted to double check my order went through ok. My card was charged $64.20 but I never got the confirmation page, it just spun and tim… | medium | high | 0.66 |
| The tracking link in your email goes to a 404 page. Is there another way to see where my package is? | medium | low | 0.87 |
| Hi, I got a text saying my parcel is 'held at depot'. I don't recognise the sender. Is this related to my order #19044 with you? | medium | high | 0.68 |
| This is my third email asking for a tracking number. I've had nothing but automated replies. Where is my order? | high | low | 0.71 |
| My parcel was due yesterday but I see it's now showing Friday. No big deal, just wanted to check that's the new estimate. | low | high | 0.47 |
| Order 22851 was supposed to arrive on the 12th and it's now the 14th. Not in a hurry, just letting you know in case something's wrong. | low | medium | 0.89 |
| Hi, my mattress delivery was scheduled for Saturday between 8 and 12. Nobody showed and I didn't get a call. What's the new date? | medium | high | 0.35 |
| It's been a week past the estimated delivery for my blender. I'm getting a bit fed up of checking the tracking page every day. | medium | high | 0.57 |
| The mug set arrived today and one of the four mugs has a small chip on the handle. Not a huge deal, but can you send a replacement for just … | low | medium | 0.86 |
| Small cosmetic scratch on the side of my new monitor, works fine otherwise. Is there anything you can do? If not, no worries. | low | medium | 0.77 |
| Hi, what's your refund policy on shoes that have been worn once indoors? They're a bit tight. | low | medium | 0.58 |
| I returned a jacket last week via the prepaid label. Just wondering how long refunds usually take to hit the card? | low | high | 0.33 |
| The planter I bought is a slightly different shade than the photos. Not faulty, just not for me. How do I get my money back? | low | medium | 0.90 |
| I was refunded $45 but I paid $62 for the item. Where's the rest of the money? | medium | low | 0.57 |
| The yoga mat doesn't match the description at all - it's much thinner than advertised. I'd like to return it for a full refund. | medium | high | 0.24 |
| Hi, I placed an order about ten minutes ago and realised I picked the wrong size. Could you cancel it so I can reorder? | low | medium | 0.82 |
| I'd like to cancel my order if it hasn't shipped yet - I found the same thing at a local store. If it's already gone out, no worries, I'll j… | low | medium | 0.56 |
| I tried to cancel order 13377 through the website and it gave me an error. It still shows as active. Can you cancel it manually? | medium | high | 0.57 |
| I ordered this by accident - my toddler got hold of my phone. Please cancel before it ships. | medium | high | 0.37 |
| The price dropped $50 right after I bought the chair. I'd rather cancel and reorder than keep paying more. | medium | high | 0.27 |
| I want to cancel order 60081, the delivery estimate is now 3 weeks and that's way too long. | medium | high | 0.21 |
| I've asked twice to cancel this order and it still shipped. I don't want it. Stop it now. | high | medium | 0.51 |
| Could you tell me what the backpack is made of? I'm allergic to latex. | low | medium | 0.59 |
| I got the camera tripod but the instructions don't explain how to attach the phone mount. Is there a video or a better manual? | medium | low | 0.79 |
| Is the blender BPA-free? I bought it for making baby food and the packaging doesn't say anything. | medium | low | 0.68 |
| The item I received has mold on it and I already used it before noticing, is this safe? | high | medium | 0.55 |
| Hi, my order is a couple days behind the estimate, just wondering if there's an update. | medium | low | 0.95 |
| I noticed a small scuff on my order, not a big deal but wanted to flag it in case others report it too. | medium | high | 0.39 |
| I'd like to exchange this for a different size, what's the best way to go about that? | medium | low | 0.89 |
| The tracking hasn't updated in two days, could you check what's going on when you have a moment? | medium | low | 0.61 |
| The product works but doesn't quite match the description online, would like some clarification. | medium | low | 0.96 |
| I'd like an update on my refund request from earlier this week, it's been a few days. | medium | low | 0.71 |
| The color options shown at checkout didn't match what I actually received, please advise. | medium | low | 0.83 |
| Can you confirm if my order qualifies for the current promotion? Wasn't applied automatically. | medium | low | 0.79 |

## Confidence vs. the 0.6 escalation threshold

Confidence is the model's own probability for the chosen label (before class weights).

| eval set | mean confidence | share < 0.6 | accuracy when ≥ 0.6 | accuracy when < 0.6 |
|---|---|---|---|---|
| test (weak) | 0.84 | 10% | 0.85 | 0.51 |
| dev (human) | 0.74 | 28% | 0.85 | 0.60 |

## Labeling functions

`calm_language` cancels `time_pressure` and sentiment votes. Then: HIGH if any strong
HIGH rule fires, two weak HIGH rules fire, or a weak HIGH rule fires together with a
MEDIUM rule; MEDIUM if one weak HIGH or any MEDIUM rule fires; otherwise LOW.

| rule | votes | strong | fires on (train) |
|---|---|---|---|
| `time_pressure` | high | yes | 3.6% |
| `escalation_threat` | high | yes | 5.1% |
| `repeat_contact` | high | yes | 1.4% |
| `safety` | high | yes | 2.6% |
| `hardship` | high | yes | 7.7% |
| `profanity` | high | yes | 1.0% |
| `strong_anger` | high |  | 6.2% |
| `patience_lost` | high |  | 1.2% |
| `shouting` | high |  | 4.0% |
| `exclamation_burst` | high |  | 3.6% |
| `very_negative` | high |  | 1.4% |
| `problem_reported` | medium |  | 27.5% |
| `frustration` | medium |  | 6.2% |
| `money_back` | medium |  | 3.6% |
| `stalled` | medium |  | 6.0% |
| `billing_issue` | medium |  | 0.5% |
| `action_request` | medium |  | 7.4% |
| `negative_sentiment` | medium |  | 12.7% |
| `calm_language` | low |  | 7.8% |

No rule fires (→ low by default) on 36.7% of train rows.

## Hyperparameter selection (weak val)

- **LogReg tfidf+tone** (val-tuned params): [{'C': 0.5, 'val_macro_f1': 0.8911}, {'C': 2.0, 'val_macro_f1': 0.9052}, {'C': 8.0, 'val_macro_f1': 0.9118}, {'C': 32.0, 'val_macro_f1': 0.9104}]
- **XGBoost tfidf+tone** (val-tuned params): [{'max_depth': 4, 'best_iteration': 634, 'val_macro_f1': 0.9037}, {'max_depth': 6, 'best_iteration': 515, 'val_macro_f1': 0.9169}]
- **LogReg tfidf+tone+emb** (val-tuned params): [{'C': 0.5, 'val_macro_f1': 0.8781}, {'C': 2.0, 'val_macro_f1': 0.8909}, {'C': 8.0, 'val_macro_f1': 0.8838}, {'C': 32.0, 'val_macro_f1': 0.8844}]
- **XGBoost tfidf+tone+emb** (val-tuned params): [{'max_depth': 4, 'best_iteration': 507, 'val_macro_f1': 0.9082}, {'max_depth': 6, 'best_iteration': 358, 'val_macro_f1': 0.9027}]

## Most useful features (LogReg tfidf+tone+emb)

- **low**: `word__cancel`, `emb__emb_142`, `word__been`, `emb__emb_336`, `emb__emb_263`, `emb__emb_209`, `word__rush`, `word__no rush`, `emb__emb_284`, `word__assistance`, `emb__emb_297`, `word__longer`
- **medium**: `word__late`, `word__bit disappointed`, `word__disappointed`, `word__look`, `word__look into`, `word__into this`, `word__please look`, `tone__vader_neg`, `word__to get`, `word__into`, `word__get`, `word__you sort`
- **high**: `tone__caps_ratio`, `word__fucking`, `word__can afford`, `tone__log_length`, `word__damn`, `word__afford`, `word__this is`, `word__goddamn`, `emb__emb_247`, `tone__vader_neg`, `word__fuming`, `word__started`
