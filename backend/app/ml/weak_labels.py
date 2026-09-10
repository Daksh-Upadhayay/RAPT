"""Weak supervision for urgency: keyword/heuristic labeling functions (LFs).

None of our training text carries trustworthy urgency labels, so these rules label the
training set and the urgency model is trained on their output (see 02-ml-models.md).
Each LF votes HIGH, MEDIUM or LOW when it fires; `weak_label` combines the votes:

- `calm_language` (the only LOW rule) cancels the votes that hedged wording falsely
  triggers: "not urgent" matches `time_pressure`, and "no big deal" reads as negative
  sentiment
- HIGH   if any *strong* HIGH rule fires (deadline, threat, repeat contact, safety,
         hardship, profanity), or two weak HIGH rules fire, or a weak HIGH rule fires
         alongside a MEDIUM rule
- MEDIUM if a single weak HIGH rule or any MEDIUM rule fires
- LOW    otherwise: no urgency signal found

The rules are deliberately simple and noisy. The model trained on them sees the full
text, so it can generalise past the exact keywords. The rule set was revised for
urgency v3 using the 170-ticket human-labelled dev set (DECISIONS.md, Phase 2); v1 and
v2 were trained on the earlier rules.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.core.enums import TicketUrgency
from app.ml.text_features import sentiment

HIGH, MEDIUM, LOW = TicketUrgency.HIGH, TicketUrgency.MEDIUM, TicketUrgency.LOW


@dataclass(frozen=True)
class LabelingFunction:
    name: str
    vote: TicketUrgency
    fires: Callable[[str], bool]
    strong: bool = False  # a strong HIGH vote decides the label on its own


def _matches(pattern: str) -> Callable[[str], bool]:
    regex = re.compile(pattern, re.IGNORECASE)
    return lambda text: regex.search(text) is not None


_WEEKDAY = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
# Carrier names and common acronyms that are written in caps without shouting
_ACRONYMS = {"UPS", "USPS", "DHL", "ETA", "FAQ", "USB", "LED", "BPA", "FEDEX", "PDF", "ORD"}
_WORD = re.compile(r"[A-Za-z]{3,}")


def _is_shouting(text: str) -> bool:
    """At least two ALL-CAPS words, and either a third of the text or two 4+ letter words."""
    words = _WORD.findall(text)
    shouted = [w for w in words if w.isupper() and w not in _ACRONYMS]
    return len(shouted) >= 2 and (len(shouted) / len(words) >= 0.3 or sum(len(w) >= 4 for w in shouted) >= 2)


LABELING_FUNCTIONS: tuple[LabelingFunction, ...] = (
    # --- strong HIGH -------------------------------------------------------------------
    LabelingFunction(
        "time_pressure",
        HIGH,
        _matches(
            r"\burgent(ly)?\b|\basap\b|\bimmediately\b|\bright (now|away)\b|as soon as possible"
            r"|\bemergency\b|time[- ]sensitive|\bdeadline\b|as a priority|high priority"
            rf"|\bby (today|tonight|tomorrow|this weekend|{_WEEKDAY})\b"
            rf"|\bbefore (tomorrow|tonight|the weekend|{_WEEKDAY})\b"
            r"|\b(today|tonight)\b.{0,20}\b(or|otherwise)\b"
            r"|\bneed\b.{0,60}\b(today|tonight|tomorrow)\b|\b(tomorrow|tonight) (morning|evening|night)\b"
            r"|\bbefore (my|our|the) \w+ (tomorrow|tonight)\b"
        ),
        strong=True,
    ),
    LabelingFunction(
        "escalation_threat",
        HIGH,
        _matches(
            r"charge ?back|\bdispute\b|\bmy bank\b|credit card company|\blawyer|\battorney"
            r"|legal action|\bsue\b|small claims|consumer protection|\bbbb\b|better business bureau"
            r"|(bad|negative|one[- ]star|1[- ]star) review|\breport (you|this)\b|\bfraud|\bscam"
            r"|\b(speak|talk) to (a |your )?(manager|supervisor)|\b(want|need|get) (a |your )?(manager|supervisor)"
            r"|\bescalat(e|ed|ion)\b"
        ),
        strong=True,
    ),
    LabelingFunction(
        "repeat_contact",
        HIGH,
        _matches(
            r"\b(second|third|fourth|fifth|\d+(st|nd|rd|th)) (\w+ )?(time|email|message|request|wrong|replacement|delay|complaint)"
            r"|\b(emailed|called|contacted|messaged|written|asked|reached out)\b.{0,15}"
            r"\b(twice|again|three times|multiple times|several times|many times)\b"
            r"|\bno (one|body)\b.{0,20}\b(replied|responded|answered|got back|gotten back)"
            r"|\bnobody\b.{0,20}\b(replies|responds|answers|helps)\b"
            r"|still (no|haven't had a|have not had a) (response|reply|answer)|\bignor(ed|ing) (me|my)"
        ),
        strong=True,
    ),
    LabelingFunction(
        "safety",
        HIGH,
        _matches(
            r"\bfire\b|\bsmok(e|ing)\b|\bspark(s|ing)?\b|\bburn(ed|t|ing)\b|electric(al)? shock"
            r"|\binjur|\bhurt (me|my|him|her|them)|\bdangerous\b|\bhazard|\bmelt(ed|ing)\b|\bchok(e|ing)\b"
            r"|\bmou?ld(y)?\b|\bunsafe\b|\btoxic\b|is (it|this) safe|allergic reaction|\bpoison"
        ),
        strong=True,
    ),
    LabelingFunction(
        "hardship",
        HIGH,
        _matches(
            r"\brent\b|\bbounced\b|overdrawn|can'?t afford|my bills|\bmedication\b|\binsulin\b|prescription"
            r"|\bmedical\b|\bhospital\b|\bdisabled\b|\bnewborn\b|wheelchair|\boxygen\b"
        ),
        strong=True,
    ),
    LabelingFunction(
        "profanity",
        HIGH,
        _matches(r"\bf+u+c+k|\bshit|\bdamn|\bgoddamn|\bcrap\b|\bwtf\b|\bbullshit\b|\bhell\b"),
        strong=True,
    ),
    # --- weak HIGH ---------------------------------------------------------------------
    LabelingFunction(
        "strong_anger",
        HIGH,
        _matches(
            r"unacceptable|ridiculous|outrageous|disgust|\bworst\b|furious|livid|fed up|sick of"
            r"|pathetic|incompetent|\ba joke\b|\bnever (shop|order|buy)\w* (here|from you)"
            r"|hung up on me|how i'?m (being )?treated|\btheft\b|\bstealing\b|disgrace|shambles|\buseless\b|fuming"
        ),
    ),
    LabelingFunction(
        "patience_lost",
        HIGH,
        _matches(
            r"\b(absolutely|completely|totally|utterly|beyond) (unacceptable|ridiculous|disgusting|outrageous|a joke)"
            r"|patience (has )?(completely )?(run out|worn thin)|more than patient|done being (patient|polite)"
            r"|at my wits'? end|loyal customer"
        ),
    ),
    LabelingFunction("shouting", HIGH, _is_shouting),
    LabelingFunction("exclamation_burst", HIGH, lambda t: "!!" in t or t.count("!") >= 3),
    LabelingFunction("very_negative", HIGH, lambda t: sentiment(t)["compound"] <= -0.75),
    # --- MEDIUM ------------------------------------------------------------------------
    LabelingFunction(
        "problem_reported",
        MEDIUM,
        _matches(
            r"\bbroken\b|\bbroke\b|damaged|cracked|shattered|smashed|crushed|dented|scratched|\bbent\b|\btorn\b"
            r"|defective|\bleak(s|ed|ing)?\b|\bruined\b|\bmissing\b"
            r"|\blate\b|\bdelay(s|ed)?\b|overdue|\bstuck\b|\blost\b|never (arrived|came|showed)"
            r"|(haven't|have not|hasn't|has not|didn't|did not|still not) (been )?(received|arrived|delivered|come)"
            r"|\bwrong\b|not working|doesn't work|does not work|won't (turn on|work|pair|connect|charge|lock|close)"
            r"|\bsplit\b|\bsnapped\b|\bcrack(s)?\b|\bchip(ped)?\b|\bscuff(ed)?\b|\bstain(s|ed)?\b|broken off"
            r"|doesn'?t (fit|match)|does not (fit|match)|didn'?t (fit|match)|not as (described|advertised|shown)"
            r"|different (colou?r|shade|size)|than (advertised|described|shown)|can'?t (assemble|use|install)"
            r"|\berror\b|timed out|\b404\b|never received|(nobody|no one) (showed|came|turned up)"
        ),
    ),
    LabelingFunction(
        "frustration",
        MEDIUM,
        _matches(
            # "concerned", not "concern": every "To whom it may concern" would match
            r"frustrat|disappoint|annoy|\bupset\b|unhappy|not happy|\bconcerned\b|worried|confus"
            r"|been waiting|still waiting|waiting (for|on) (my|the|a)"
        ),
    ),
    LabelingFunction(
        "money_back",
        MEDIUM,
        _matches(
            r"\b(want|need|demand|get|getting|expect|expecting|waiting for|where is) (a |my |the )?"
            r"(full )?(refund|money back|rebate|reimbursement|compensation)"
            r"|charged (me )?twice|double charged|overcharged"
        ),
    ),
    LabelingFunction(
        "stalled",
        MEDIUM,
        _matches(
            r"(hasn'?t|has not|haven'?t|have not) (been )?(moved|updated|changed|heard|shipped|processed)"
            r"|\bno (update|updates|movement|sign)\b|still (says|shows|showing|pending|processing|in transit)"
            r"|behind (the )?(estimate|schedule)|was (supposed|meant|due|scheduled|estimated) (to|for|on)"
            r"|delivery date (has )?passed|sitting (in|at)|nothing yet|heard nothing|not heard back"
        ),
    ),
    LabelingFunction(
        "billing_issue",
        MEDIUM,
        _matches(
            r"charged (me )?(full price|twice|the wrong|more|for)|double (billed|charged)|overcharged"
            r"|(promo|discount|coupon) code|(didn'?t|did not|wasn'?t|was not|not) (been )?applied"
            r"|price (dropped|changed)|total was|refunded \$?\d+|partial refund|renewed but"
        ),
    ),
    LabelingFunction(
        "action_request",
        MEDIUM,
        _matches(
            r"look into|\bchase\b|sort (this|it) out|what happened|what'?s going on|what'?s happening|what'?s holding"
            r"|next steps?|my options|exchange (this|it)|to exchange|process (to|for) return|return (it|this) for"
        ),
    ),
    LabelingFunction("negative_sentiment", MEDIUM, lambda t: -0.75 < sentiment(t)["compound"] <= -0.4),
    # --- LOW ---------------------------------------------------------------------------
    LabelingFunction(
        "calm_language",
        LOW,
        _matches(
            r"no rush|no hurry|not urgent|nothing urgent|non-urgent|not in a hurry|no big deal|not a (big|huge) deal"
            r"|no worries|whenever (you|suits|convenient|possible)|when you (get|have) a (chance|moment|minute)"
            r"|when possible|just curious|out of curiosity|for my records|no issue|just wondering|take your time"
            r"|happy to wait"
        ),
    ),
)

# Votes that hedged wording triggers falsely, dropped when calm_language fires
_CANCELLED_BY_CALM = {"time_pressure", "negative_sentiment", "very_negative"}


@dataclass(frozen=True)
class WeakLabel:
    label: TicketUrgency
    fired: tuple[str, ...]  # names of the LFs that fired, for auditing


def weak_label(text: str) -> WeakLabel:
    fired = [lf for lf in LABELING_FUNCTIONS if lf.fires(text)]
    names = tuple(lf.name for lf in fired)
    if "calm_language" in names:
        fired = [lf for lf in fired if lf.name not in _CANCELLED_BY_CALM]
    strong_high = any(lf.vote is HIGH and lf.strong for lf in fired)
    weak_high = sum(lf.vote is HIGH and not lf.strong for lf in fired)
    medium = any(lf.vote is MEDIUM for lf in fired)

    if strong_high or weak_high >= 2 or (weak_high and medium):
        label = HIGH
    elif weak_high or medium:
        label = MEDIUM
    else:
        label = LOW
    return WeakLabel(label, names)
