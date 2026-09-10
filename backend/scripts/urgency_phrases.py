"""Compositional urgency phrasing for the urgency training corpus (v2).

v1 took all its urgency signal from ~45 fixed tone sentences, and the model memorised
them instead of learning urgency. Here each urgency *kind* (deadline, repeat contact,
threat, safety, anger, money, impact, frustration, calm) is built from slot-filled
pieces, giving thousands of distinct phrasings, and an urgent ticket usually carries
two or three of them.

Two properties matter for weak supervision:
- Many phrasings avoid the keywords in app/ml/weak_labels.py. The rules miss those, so
  labels stay noisy, the way they would be on real tickets.
- Urgent tickets mix caught and uncaught phrasings. When the rules label a ticket high
  because of one phrase, the model also sees the phrases next to it, which is how it
  can learn to generalise past the rules.

The rules in weak_labels.py were not changed for v2: only the text they label changed.
"""

import random

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _pick(rng: random.Random, options: list[str]) -> str:
    return rng.choice(options)


# --- HIGH kinds -------------------------------------------------------------------------


def deadline(rng: random.Random) -> str:
    need = _pick(rng, [
        "I need this", "I really need it", "It has to be here", "I need an answer", "This has to be sorted",
        "I need it delivered", "Please get this to me", "I have to have it", "I need a resolution",
        "Someone needs to fix this", "I need a replacement", "I need to hear back",
    ])
    when = _pick(rng, [
        "today", "by tomorrow", f"before {_pick(rng, WEEKDAYS)}", "by the weekend", "within 24 hours",
        f"before my flight on {_pick(rng, WEEKDAYS)}", f"by {_pick(rng, WEEKDAYS)} at the latest",
        "in the next two days", "this afternoon", "before the 15th", "by end of day", "first thing tomorrow",
        "before we leave on holiday", "this week, not next",
    ])
    why = _pick(rng, [
        "", "", "it's for my daughter's graduation", "it's a wedding present", "I need it for a work presentation",
        "we're going camping", "I'm moving out", "the event can't be moved", "my mum is coming home from hospital",
        "we leave the country", "I have an exam", "it's for a funeral", "the builders arrive then",
        "my son's party is that day", "I start a new job",
    ])
    return f"{need} {when}" + (f" because {why}." if why else ".")


def repeat_contact(rng: random.Random) -> str:
    return _pick(rng, [
        f"This is the {_pick(rng, ['second', 'third', 'fourth', 'fifth'])} {_pick(rng, ['time', 'email', 'message'])} I've sent about this.",
        f"I've {_pick(rng, ['contacted', 'emailed', 'called', 'messaged'])} you {_pick(rng, ['twice', 'three times', 'several times', 'multiple times'])} already.",
        f"I've been on {_pick(rng, ['live chat', 'the phone', 'hold'])} {_pick(rng, ['three times', 'for over an hour', 'every day this week'])} and nothing has changed.",
        "Nobody has replied to any of my emails.",
        "I keep getting the same copy-paste answer.",
        "Each time I'm told someone will call back and they never do.",
        "All I get are automated replies.",
        f"I opened a ticket {_pick(rng, ['last week', 'ten days ago', 'on the 2nd', 'a fortnight ago'])} and heard nothing.",
        "Your agent promised a callback that never came.",
        "I'm tired of chasing you for updates.",
        "I've explained this to four different people now.",
        "My previous messages have been completely ignored.",
    ])


def threat(rng: random.Random) -> str:
    intro = _pick(rng, [
        "If this isn't resolved soon I will", "Next step is to", "I'm about to", "Don't make me",
        "I'm fully prepared to", "I will have no choice but to", "Tomorrow I'm going to",
    ])
    action = _pick(rng, [
        "file a chargeback", "dispute this with my card issuer", "contact my bank", "report this to trading standards",
        "go to the consumer ombudsman", "post about this on social media", "leave a review warning other shoppers",
        "speak to a lawyer", "take this to small claims court", "report you to the BBB",
        "ask my credit card company to reverse the payment", "tell everyone I know to avoid your shop",
    ])
    return f"{intro} {action}."


def safety(rng: random.Random) -> str:
    thing = _pick(rng, ["It", "The plug", "The battery", "The cable", "The base", "The motor", "The charger", "The unit"])
    hazard = _pick(rng, [
        "started smoking", "gave off sparks", "gets dangerously hot", "smells like burning plastic",
        "gave my son a shock", "has a sharp edge that cut my finger", "is leaking battery fluid",
        "overheated and melted", "caught fire on the counter", "has small parts my toddler could swallow",
        "nearly fell on my kid", "tripped the electrics in the whole flat", "made a loud bang and went dead",
        "is scorched on one side",
    ])
    return f"{thing} {hazard}."


def anger(rng: random.Random) -> str:
    return _pick(rng, [
        "This is absolutely unacceptable.", "I am furious.", "What a joke of a company.", "Honestly disgraceful.",
        "I've never been treated this badly by a shop.", "This is beyond a joke.", "You people are useless.",
        "I'm livid.", "Complete shambles.", "I'm done being polite.", "This is outrageous.",
        "Totally incompetent service.", "I am so angry right now.", "Shocking service from start to finish.",
        "How is this acceptable?", "Worst experience I've ever had online.", "I'm fuming.",
        "This is a total disgrace.", "Unbelievable.", "Do you even care about your customers?",
    ])


def money(rng: random.Random) -> str:
    amount = rng.randint(80, 1500)
    return _pick(rng, [
        f"That was ${amount} of my rent money.", f"I can't afford to lose ${amount}.",
        f"I've paid ${amount} and have nothing to show for it.", "This has left me overdrawn.",
        f"${amount} is a lot of money to just disappear.", "I'm on a tight budget and need that money back.",
        "My bills are due and that money is stuck with you.",
    ])


def impact(rng: random.Random) -> str:
    return _pick(rng, [
        "I'm disabled and rely on this every day.", "My elderly dad can't manage without it.",
        "It's for my newborn and we have nothing else.", "I can't work without it.",
        "My business is losing sales every day this goes on.", "It's medical equipment.",
        "We have no heating until it arrives.", "My kids have nothing to sleep on.",
    ])


# --- MEDIUM kinds -----------------------------------------------------------------------


def frustration(rng: random.Random) -> str:
    return _pick(rng, [
        "This is getting frustrating.", "I'm a bit disappointed.", "Not ideal.", "I was really looking forward to this.",
        "Kind of annoying, to be honest.", "Bit of a let down.", "I'd appreciate a quicker response this time.",
        "Starting to get a little worried.", "I've been patient so far.", "Not the experience I expected.",
        "It's a shame, I usually like your shop.", "I'm not thrilled about this.", "This has been a hassle.",
        "Hoping this gets sorted soon.", "I'm getting a bit fed up with waiting.", "Slightly concerned now.",
    ])


def inconvenience(rng: random.Random) -> str:
    return _pick(rng, [
        "I've had to rearrange my week around this.", "I took a morning off to wait in for it.",
        "It's holding up a project I'm working on.", "I've got nothing to use in the meantime.",
        "This is the second problem with this order.", "I had to borrow one from a neighbour.",
        "I've wasted a lot of time on this already.", "I planned my weekend around it arriving.",
    ])


def action_request(rng: random.Random) -> str:
    return _pick(rng, [
        "Please look into this.", "Can someone get back to me?", "I'd like this fixed.",
        "What are you going to do about it?", "Please let me know the next steps.", "Can you sort this out?",
        "I'd like a proper explanation.", "Please confirm what happens now.",
    ])


# --- LOW --------------------------------------------------------------------------------


def calm(rng: random.Random) -> str:
    return _pick(rng, [
        "No rush.", "Whenever suits.", "No worries if not.", "Just curious!", "Thanks so much, love the store.",
        "Hope your week is going well.", "Not urgent at all.", "Only asking out of interest.", "Take your time.",
        "Appreciate it!", "Thanks for the great service so far.", "Just planning ahead.", "Cheers in advance!",
        "Totally fine either way.", "Happy to wait.", "It's not a problem, just wanted to check.",
    ])


HIGH_KINDS = [deadline, repeat_contact, threat, safety, anger, money, impact]
MEDIUM_KINDS = [frustration, inconvenience, action_request]
LEVEL_WEIGHTS = {"none": 30, "calm": 15, "medium": 30, "high": 25}


def compose(text: str, rng: random.Random) -> str:
    """Wrap an issue-only ticket in urgency phrasing of a randomly chosen intensity."""
    level = rng.choices(list(LEVEL_WEIGHTS), weights=list(LEVEL_WEIGHTS.values()))[0]
    if level == "none":
        return text
    if level == "calm":
        extra = [calm(rng)]
    elif level == "medium":
        extra = [kind(rng) for kind in rng.sample(MEDIUM_KINDS, k=rng.choice([1, 1, 2]))]
    else:
        extra = [kind(rng) for kind in rng.sample(HIGH_KINDS, k=rng.choice([1, 2, 2, 3]))]
        if rng.random() < 0.4:
            extra.append(rng.choice(MEDIUM_KINDS)(rng))
        rng.shuffle(extra)
        if rng.random() < 0.15:
            extra[0] = extra[0].upper()
        if rng.random() < 0.2:
            extra[-1] = extra[-1].rstrip(".") + rng.choice(["!", "!!", "!!!"])

    before = [s for s in extra if rng.random() < 0.25]
    after = [s for s in extra if s not in before]
    return " ".join([*before, text.rstrip(), *after])
