# Urgency classifier v4

Weak supervision **plus human labels**: the rules (`app/ml/weak_labels.py`) label the
7219-row train split of `urgency_tickets.csv`, and all 234 human-labelled
tickets are added with weight ×100. Features: TF-IDF word 1-2-grams + tone features +
MiniLM sentence embeddings → logistic regression (C=2.0, balanced classes).
Class weights: low ×1.0, medium ×0.8, high ×1.0, tuned for the best
macro-F1 that keeps cross-validated high recall ≥ 0.85.

Weak label distribution (train): low 2666 (37%), medium 2566 (36%), high 1987 (28%).
Human tickets: low 74, medium 93, high 67.

## Human-label cross-validation (5-fold)

Each human ticket is predicted by a model that never saw it. Human weight 0 = weak labels
only (the v3 recipe, on the v4 corpus and rules).

| model | human CV macro-F1 / acc |
|---|---|
| human weight 0 (weak labels only) | 0.73 / 0.73 |
| human weight 3 | 0.75 / 0.75 |
| human weight 10 | 0.77 / 0.77 |
| human weight 30 | 0.77 / 0.77 |
| human weight 100 | 0.80 / 0.80 |
| human weight 100 + class weights | 0.80 / 0.80 |

Context on the same 234 tickets (**not** a fair test: v3 was tuned on 170 of them and
chosen on the other 64):

| model | human macro-F1 / acc |
|---|---|
| v3 (served before) | 0.76 / 0.76 |
| rules alone | 0.86 / 0.85 |

**Caveats:** the rules were revised while reading these tickets, and the class weights
were tuned on the same out-of-fold predictions, so the CV numbers are somewhat optimistic.
The real number comes from a new fresh set scored once with `scripts/evaluate_model.py`.

## Shipped recipe — cross-validated per class

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| low | 0.81 | 0.81 | 0.81 | 74 |
| medium | 0.84 | 0.74 | 0.79 | 93 |
| high | 0.76 | 0.88 | 0.81 | 67 |
| **macro avg** | | | **0.80** | 234 |

Accuracy: 0.80

| true \ predicted | low | medium | high |
|---|---|---|---|
| **low** | 60 | 8 | 6 |
| **medium** | 11 | 69 | 13 |
| **high** | 3 | 5 | 59 |

### Tickets it got wrong (out-of-fold)

| text | true | predicted | conf |
|---|---|---|---|
| Hi there, I ordered a pair of hiking boots on Sunday and the confirmation email said I'd get tracking within 48 hours. It's Tuesday night an… | low | medium | 0.73 |
| Hello, I placed order #40213 for a standing desk frame. Could you let me know which courier it's going with? I want to make sure someone's h… | low | high | 0.89 |
| Hey, I bought a gift card and a lamp last week. The gift card showed up by email but the lamp order just says 'awaiting fulfilment'. Is that… | low | high | 0.92 |
| Is there a way to see an estimated delivery date for order 77120? The order page only shows 'processing'. | low | medium | 0.90 |
| Just wanted to double check my order went through ok. My card was charged $64.20 but I never got the confirmation page, it just spun and tim… | medium | high | 0.83 |
| The tracking link in your email goes to a 404 page. Is there another way to see where my package is? | medium | low | 0.64 |
| Where's my stuff?? Paid for the vacuum on the 3rd, no email, no tracking, nothing. Kind of annoyed. | medium | high | 0.45 |
| Hi, I got a text saying my parcel is 'held at depot'. I don't recognise the sender. Is this related to my order #19044 with you? | medium | high | 0.98 |
| This is my third email asking for a tracking number. I've had nothing but automated replies. Where is my order? | high | low | 0.47 |
| My parcel was due yesterday but I see it's now showing Friday. No big deal, just wanted to check that's the new estimate. | low | medium | 0.89 |
| Order 22851 was supposed to arrive on the 12th and it's now the 14th. Not in a hurry, just letting you know in case something's wrong. | low | high | 0.77 |
| Hi, my mattress delivery was scheduled for Saturday between 8 and 12. Nobody showed and I didn't get a call. What's the new date? | medium | high | 0.51 |
| THIS IS RIDICULOUS. Three weeks late and nobody can tell me where my order is. I want answers. | high | medium | 0.79 |
| The mug set arrived today and one of the four mugs has a small chip on the handle. Not a huge deal, but can you send a replacement for just … | low | medium | 0.78 |
| Small cosmetic scratch on the side of my new monitor, works fine otherwise. Is there anything you can do? If not, no worries. | low | medium | 0.85 |
| I ordered a set of 6 wine glasses, three arrived smashed. There was barely any bubble wrap. | medium | high | 0.88 |
| The planter I bought is a slightly different shade than the photos. Not faulty, just not for me. How do I get my money back? | low | medium | 0.91 |
| I noticed I paid full price for my order the day before the sale started. Is there any way to get the difference refunded? | low | medium | 0.93 |
| My order was cancelled on your end because it was out of stock, but I haven't seen the money come back yet. It's been 8 days. | medium | high | 0.52 |
| you charged me for 3 items and sent 1. I want a refund for the other two right now, not a voucher. | high | medium | 0.61 |
| Hi, I placed an order about ten minutes ago and realised I picked the wrong size. Could you cancel it so I can reorder? | low | medium | 0.94 |
| I'd like to cancel my order if it hasn't shipped yet - I found the same thing at a local store. If it's already gone out, no worries, I'll j… | low | high | 0.48 |
| I tried to cancel order 13377 through the website and it gave me an error. It still shows as active. Can you cancel it manually? | medium | high | 0.95 |
| I requested a cancellation yesterday and got no confirmation. Is the order cancelled or not? | medium | low | 0.49 |
| The price dropped $50 right after I bought the chair. I'd rather cancel and reorder than keep paying more. | medium | low | 0.73 |
| I want to cancel order 60081, the delivery estimate is now 3 weeks and that's way too long. | medium | low | 0.92 |
| I've asked twice to cancel this order and it still shipped. I don't want it. Stop it now. | high | low | 0.56 |
| Could you tell me what the backpack is made of? I'm allergic to latex. | low | high | 0.49 |
| I got the camera tripod but the instructions don't explain how to attach the phone mount. Is there a video or a better manual? | medium | low | 0.38 |
| Is the blender BPA-free? I bought it for making baby food and the packaging doesn't say anything. | medium | high | 0.87 |
| Is there a warranty on this item? Just want to know for my records, no issue right now. | low | high | 0.57 |
| Hi, my order is a couple days behind the estimate, just wondering if there's an update. | medium | low | 0.99 |
| I noticed a small scuff on my order, not a big deal but wanted to flag it in case others report it too. | medium | low | 0.92 |
| I'd like to exchange this for a different size, what's the best way to go about that? | medium | low | 0.95 |
| I need this exchanged before Friday, that's when I need it for a wedding, please let me know if that's possible. | medium | high | 0.53 |
| I need to change my shipping address before the order ships out tomorrow. | medium | high | 0.42 |
| The item description said machine washable but the tag says dry clean only, which is correct? | medium | low | 0.82 |
| I need an exchange processed soon since the current item doesn't fit and I need one for an event this weekend. | medium | high | 0.83 |
| Can someone confirm this order will still arrive by the date originally promised? It's important for a deadline. | medium | low | 0.91 |
| I noticed my card was billed the wrong amount, could someone correct this soon. | medium | high | 0.96 |

_…and 6 more._

## Confidence vs. the 0.6 escalation threshold

| eval set | mean confidence | share < 0.6 | accuracy when ≥ 0.6 | accuracy when < 0.6 |
|---|---|---|---|---|
| human CV | 0.85 | 12% | 0.84 | 0.56 |
| test (weak) | 0.86 | 10% | 0.90 | 0.48 |

## Final model vs weak labels (held-out corpus splits)

| model | val (weak) macro-F1 / acc | test (weak) macro-F1 / acc |
|---|---|---|
| final model | 0.82 / 0.82 | 0.86 / 0.86 |

## Labeling functions

`calm_language` cancels `time_pressure` and sentiment votes. Then: HIGH if any strong
HIGH rule fires, two weak HIGH rules fire, or a weak HIGH rule fires together with a
MEDIUM rule; MEDIUM if one weak HIGH or any MEDIUM rule fires; otherwise LOW.

| rule | votes | strong | fires on (train) |
|---|---|---|---|
| `time_pressure` | high | yes | 8.3% |
| `escalation_threat` | high | yes | 3.6% |
| `repeat_contact` | high | yes | 1.6% |
| `safety` | high | yes | 3.8% |
| `hardship` | high | yes | 7.0% |
| `fraud_or_privacy` | high | yes | 2.3% |
| `money_lost` | high | yes | 1.8% |
| `profanity` | high | yes | 0.8% |
| `strong_anger` | high |  | 4.5% |
| `patience_lost` | high |  | 0.7% |
| `shouting` | high |  | 2.8% |
| `exclamation_burst` | high |  | 2.4% |
| `very_negative` | high |  | 1.3% |
| `problem_reported` | medium |  | 31.6% |
| `frustration` | medium |  | 5.4% |
| `money_back` | medium |  | 3.8% |
| `stalled` | medium |  | 6.2% |
| `billing_issue` | medium |  | 0.6% |
| `action_request` | medium |  | 7.5% |
| `negative_sentiment` | medium |  | 11.7% |
| `calm_language` | low |  | 7.1% |

No rule fires (→ low by default) on 32.4% of train rows.

## Features pushing hardest towards each class

- **low**: `word__just`, `word__no`, `word__cancel`, `word__not`, `emb__emb_209`, `emb__emb_263`, `word__rush`, `word__no rush`, `emb__emb_142`, `emb__emb_328`, `word__please cancel`, `word__is the`
- **medium**: `word__exchange`, `word__got`, `word__late`, `word__can you`, `word__to get`, `word__correct`, `word__look`, `word__look into`, `word__still`, `word__the tracking`, `emb__emb_107`, `emb__emb_248`
- **high**: `tone__caps_ratio`, `word__fucking`, `word__can afford`, `tone__log_length`, `word__damn`, `word__afford`, `word__this is`, `word__account`, `word__tomorrow`, `word__immediately`, `word__right now`, `emb__emb_104`
