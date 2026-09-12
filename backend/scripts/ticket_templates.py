"""Template-based synthetic support tickets for all six categories.

Bitext (the public dataset) only covers order_status, refund_request and cancellation.
Templates fill damaged_item, delivery_delay and product_question, and are also mixed
into the Bitext classes so that "template writing style" doesn't predict the category.

Each ticket is built from one *core* sentence (which carries the category) plus optional
opener, tone sentence and closer, or is a short keyword-style query. Some tickets get
typo/lowercase noise so terse, messy text isn't unique to Bitext either. The core
sentence id is returned as the ticket's `group`, so the train/val/test split can keep
all variants of one core sentence in the same split.

Category labelling rules (also in data/README.md):
- damage takes priority: "it arrived broken, I want a refund" is damaged_item
- cancelling takes priority over the refund that follows: cancellation
- delivery_delay means past the promised date; "where is it / any update" is order_status
"""

import random
import string

from app.core.enums import TicketCategory as C

ITEMS = [
    "headphones", "blender", "office chair", "backpack", "coffee maker", "laptop stand", "desk lamp",
    "running shoes", "winter jacket", "bluetooth speaker", "yoga mat", "kitchen scale", "phone case",
    "electric kettle", "board game", "water bottle", "garden hose", "bookshelf", "wireless mouse",
    "picture frame", "throw blanket", "air fryer", "toolset", "camera tripod", "night lamp",
    "smartwatch", "robot vacuum", "mechanical keyboard", "rice cooker", "duvet cover", "monitor",
    "sneakers", "stand mixer", "car seat cover", "hair dryer", "tent", "suitcase", "mirror",
]
COMPAT = ["an iPhone 15", "Android phones", "a MacBook", "Windows 11", "a standard US outlet", "my old model", "a PS5"]
DAYS = ["2 days", "3 days", "4 days", "5 days", "6 days", "a week", "8 days", "over a week", "10 days", "two weeks"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NAMES = ["Sam", "Priya", "Jordan", "Maria", "Chen", "Alex", "Fatima", "Tom", "Aisha", "Luca"]


def order_id(rng: random.Random) -> str:
    n = rng.randint(10000, 99999)
    return rng.choice([f"#{n}", f"{n}", f"#{n}", f"ORD-{n}"])


CORES: dict[C, list[str]] = {
    C.ORDER_STATUS: [
        "I placed my order {days} ago and it still says processing. Can you check on it?",
        "Just checking in on order {oid}. When will it ship?",
        "Can you give me an update on my order status? I haven't received a shipping confirmation for my {item} yet.",
        "I ordered a {item} {days} ago and still don't have a tracking number. Is that normal?",
        "My order confirmation says it shipped but the tracking link isn't working. What's the current status?",
        "I'd like to know the status of order {oid}, please.",
        "Just wondering if my {item} order has left the warehouse yet.",
        "I haven't gotten any email updates since I placed my order. Can you check where it is?",
        "Is my package still on track to arrive this week? I can't find any status update.",
        "Can someone tell me if my {item} has been packed yet? No updates on the site.",
        "My dashboard shows the order as 'pending'. Is that expected?",
        "What's happening with order {oid}? It's been sitting at 'order received' for a while now.",
        "I want to confirm my {item} order actually went through and is being processed.",
        "Could you check the current status of order {oid}? I haven't heard anything since checkout.",
        "Can you tell me when order {oid} will ship?",
        "Has my {item} shipped yet?",
        "I never got an order confirmation email for my {item}. Did the order go through?",
        "What does 'label created' mean on my tracking? Has it actually been picked up?",
        "Could you send me the tracking number for order {oid}?",
        "Where can I track my order? I can't find the link in my account.",
        "My order page says 'in transit'. Which carrier is delivering it?",
        "Is order {oid} still on schedule for delivery?",
        "I'd like an ETA for my {item}, please.",
        "The tracking number you sent me shows 'not found' on the carrier site.",
        "Has my payment for order {oid} gone through? The status hasn't changed.",
        "When is my {item} expected to arrive?",
        "What stage is order {oid} at right now?",
        # v2: "arrived" in a tracking status, not at the customer's door
        "Tracking shows order {oid} arrived at the sorting facility. What happens next?",
        "My {item} order says 'arrived at carrier hub'. Does that mean it has shipped?",
    ],
    C.DELIVERY_DELAY: [
        "My package was supposed to arrive {days} ago and it's still not here, no courier updates.",
        "The estimated delivery date has already passed and I still haven't received my {item}.",
        "Why is my delivery taking so long? It was supposed to arrive last week.",
        "Tracking says 'out for delivery' since yesterday but nothing has shown up.",
        "My order {oid} is now {days} late. Can you tell me what's causing the delay?",
        "The shipment has been stuck at the same tracking checkpoint for {days} now, past the delivery date.",
        "I was promised delivery days ago and it's still not here.",
        "Delivery keeps getting pushed back on the tracking page for my {item} order.",
        "My package missed its delivery window and there's been no update since.",
        "It's been {days} past the delivery estimate and the courier still hasn't delivered my {item}.",
        "The delivery date keeps changing every time I check, it's now well past the original estimate.",
        "My order {oid} was marked 'delayed' with no explanation and no new delivery date given.",
        "I paid for expedited shipping but my {item} is now later than standard delivery would've been.",
        "The courier attempted delivery once and never came back, now it's been {days} with no update.",
        "My {item} order has been in transit for {days}, way longer than the delivery estimate.",
        "Delivery was supposed to happen already but tracking still shows it in a different city.",
        "This is the second delay notice I've received for order {oid}. What's going on?",
        "My package is significantly overdue.",
        "The delivery for my {item} has been rescheduled multiple times without a clear reason.",
        "I'm still waiting on order {oid} that was due {days} ago.",
        "My {item} was due on {weekday} and it never showed up.",
        "My package has said 'delayed in transit' for {days}.",
        "The carrier keeps saying 'delivery exception' and my {item} is now late.",
        "I was told it would arrive by {weekday}. It's now {days} past that.",
        "My order is late. It was supposed to be here already.",
        "It's been stuck in customs for {days} and is now past the delivery estimate.",
        "The package is overdue by {days} and the courier won't give me a new date.",
        # v2: "not arrived" phrasings. In v1 "arrived" only ever appeared in damaged_item
        # rows, so the model took the word itself as a sign of damage.
        "I ordered a {item} {days} ago and it still hasn't arrived. Where is it?",
        "My order hasn't arrived yet and it was meant to be here by {weekday}.",
        "Order {oid} never arrived. The delivery date was {days} ago.",
        "It's been {days} and my parcel has not arrived.",
        "My {item} still has not arrived even though it was due {days} ago.",
        "Nothing has arrived for order {oid} and it's now {days} overdue.",
        "My package didn't arrive on {weekday} like the tracking said it would.",
        "Still waiting for my {item}. It hasn't arrived and the delivery date has passed.",
        "Tracking says it arrived at the local depot {days} ago but it still hasn't been delivered to me.",
    ],
    C.DAMAGED_ITEM: [
        "I ordered a {item} and when it arrived, the box was completely crushed and the item is broken.",
        "The {item} I ordered arrived cracked. Clearly damaged in shipping.",
        "My package showed up today but the {item} inside is dented and doesn't work anymore.",
        "The {item} I ordered came with a large tear. It looks like it was damaged before packing.",
        "I received my order but the {item} is cracked right out of the box.",
        "My {item} arrived broken into pieces, the packaging was torn open too.",
        "My new {item} has several parts physically broken off. It arrived like this.",
        "I opened the box and my {item} already has a large scratch and dent on it.",
        "My {item} arrived soaking wet and the box was falling apart, the item itself is stained.",
        "The {item} I bought is bent out of shape, definitely damaged during delivery.",
        "I got order {oid} today and the {item} is completely shattered inside the packaging.",
        "The {item} arrived with missing pieces and a cracked casing.",
        "The {item} I ordered has a broken part right out of the package.",
        "I received a damaged item. My {item} won't function properly because of visible damage.",
        "My order arrived with the box soaked and the {item} inside no longer works.",
        "The {item} I purchased came with a snapped part, unusable as is.",
        "The box was fine but the {item} inside was broken.",
        "My {item} arrived dented and I'd like a replacement.",
        "Half of the {item} was smashed when I opened the package.",
        "The glass on my {item} was shattered in the box. Can I get a replacement or refund?",
        "My {item} came scratched all over and one part is snapped.",
        "The {item} was damaged in transit, the corner is crushed and it won't turn on.",
        "Received order {oid} and the {item} is defective, it has a big crack down the side.",
        "The {item} leaked everywhere inside the box, it's ruined.",
        "I got the {item} today but it's broken. I can send photos.",
    ],
    C.REFUND_REQUEST: [
        "I returned the {item} {days} ago and still haven't received my refund.",
        "I'd like a refund for order {oid}, the {item} isn't what I expected.",
        "When will my refund of ${amount} show up on my card?",
        "I sent the {item} back last week. Has the refund been processed?",
        "Can I get my money back for the {item}? It doesn't fit.",
        "I was charged ${amount} but you only refunded part of it.",
        "What is your refund policy for items that have been opened?",
        "I want a full refund for order {oid}.",
        "The {item} isn't as described on the website, I'd like to return it for a refund.",
        "The return email said the refund takes 5 days but it's been {days}.",
        "I was charged twice for order {oid}, please refund the duplicate charge.",
        "How long do refunds usually take to process?",
        "I changed my mind about the {item}. Can I return it and get a refund?",
        "My refund for order {oid} says 'approved' but the money isn't in my account.",
        "I'm not satisfied with the {item} and would like my money back.",
        "Can the refund go to my original payment method?",
        "The return was delivered back to you {days} ago. Where is my refund of ${amount}?",
        "Do I get the shipping fee back if I return the {item}?",
        "I'd like a refund for the {item}, I don't need it anymore.",
        "You refunded me in store credit but I want the money back on my card.",
    ],
    C.CANCELLATION: [
        "Please cancel order {oid}.",
        "I'd like to cancel my {item} order before it ships.",
        "I ordered the wrong {item} by mistake, can you cancel it?",
        "How do I cancel an order I placed {days} ago?",
        "Cancel my order please, I found it cheaper elsewhere.",
        "I need to cancel order {oid}, I no longer need the {item}.",
        "Is it too late to cancel order {oid}? It still says processing.",
        "I accidentally placed the same order twice. Please cancel one of them.",
        "Can you stop my order from shipping? I want to cancel it.",
        "I want to cancel the {item} from my order but keep the rest.",
        "There's no cancel button on my order page. How do I cancel order {oid}?",
        "Please cancel my purchase of the {item} and confirm by email.",
        "I changed my mind, please cancel my order before it's sent.",
        "Can I cancel order {oid} if it has already shipped?",
        "I placed an order an hour ago and need to cancel it.",
        "I'd like to cancel my pre-order for the {item}.",
        "Please cancel the {item} order, my address is wrong and I'll reorder.",
        "I requested a cancellation for order {oid} but it still shows as active.",
    ],
    C.PRODUCT_QUESTION: [
        "Does the {item} come with a warranty?",
        "Is the {item} available in other colors?",
        "What are the dimensions of the {item}?",
        "Is the {item} compatible with {compat}?",
        "Will the {item} be back in stock soon?",
        "What material is the {item} made of?",
        "Does the {item} need batteries or does it plug in?",
        "Can the {item} be used outdoors?",
        "Is the {item} dishwasher safe?",
        "How do I set up my new {item}? The manual isn't clear.",
        "What's the difference between the two {item} models on your site?",
        "Does the {item} ship with a charger?",
        "How much weight can the {item} hold?",
        "Is the {item} suitable for a beginner?",
        "Do you sell replacement parts for the {item}?",
        "Is there a bigger size of the {item}?",
        "How do I clean the {item}?",
        "Is the {item} you sell the latest model?",
        "Does the {item} work with 220V outlets abroad?",
        "What's the battery life on the {item}?",
        "Does the {item} have a sleep or auto-off mode?",
        "Is the {item} waterproof?",
        "Can I get the {item} engraved or personalized?",
    ],
}

SHORT: dict[C, list[str]] = {
    C.ORDER_STATUS: [
        "where is my order", "order {oid} status", "tracking number for {oid}?", "has my {item} shipped",
        "status of my {item} order", "no tracking info yet", "when will my order ship", "eta on order {oid}",
        "is my order confirmed", "order still processing?",
    ],
    C.DELIVERY_DELAY: [
        "package late", "my {item} is overdue", "delivery delayed", "order {oid} late", "delivery date passed",
        "still not delivered, past due date", "parcel stuck in transit {days}", "why is my delivery so late",
        "late delivery {oid}", "my order is {days} late",
        "my order has not arrived", "{item} hasn't arrived yet", "order {oid} never arrived",
        "parcel not arrived", "still hasn't arrived, past due",
    ],
    C.DAMAGED_ITEM: [
        "{item} arrived broken", "damaged {item}", "item damaged in shipping", "broken {item} received",
        "my {item} came cracked", "order {oid} arrived damaged", "{item} smashed in box",
        "received a defective {item}", "{item} is dented", "my {item} arrived scratched",
    ],
    C.REFUND_REQUEST: [
        "refund for order {oid}", "where is my refund", "i want my money back", "refund status?",
        "still waiting on refund", "refund not received", "how do refunds work", "return and refund {item}",
        "money back for {item}", "refund to original card",
    ],
    C.CANCELLATION: [
        "cancel order {oid}", "cancel my order", "please cancel my order", "how to cancel order",
        "cancel {item} order", "want to cancel my purchase", "stop my order", "cancel before shipping",
        "cancel order {oid} pls", "cancel the {item}",
    ],
    C.PRODUCT_QUESTION: [
        "{item} warranty?", "is the {item} waterproof", "{item} dimensions", "does the {item} come in black",
        "{item} in stock?", "{item} size guide", "how to use {item}", "{item} battery life",
        "is {item} compatible with {compat}", "{item} material?",
    ],
}

OPENERS = ["", "", "Hi,", "Hello,", "Hey,", "Hi there,", "Good morning,", "Hello team,", "To whom it may concern,"]
CLOSERS = ["", "", "Thanks.", "Thank you!", "Thanks in advance.", "Regards, {name}", "Please advise.", "Cheers, {name}"]

# Tone sentences are category-agnostic. Some contain the words the urgency rules look
# for and some express the same thing in other words, so the weak labels are noisy on
# purpose, like they would be on real tickets.
TONES: dict[str, list[str]] = {
    "calm": [
        "No rush on this.", "Whenever you get a chance.", "Just curious.", "Appreciate any info.",
        "No hurry at all.", "It's not a big deal, just wanted to ask.", "Hope you're having a good day!",
    ],
    "neutral": [
        "I can send my receipt if needed.", "My email is the one on the account.",
        "Let me know what you need from me.", "I ordered it as a gift.", "I'm usually home in the afternoons.",
        "The order is under my partner's name.",
    ],
    "frustrated": [
        "This is really frustrating.", "I'm pretty disappointed, honestly.", "I've been waiting a long time for this.",
        "Not happy about this at all.", "I expected better from your store.", "Honestly I'm at my wits' end.",
        "I shouldn't have to chase you for this.", "Kind of annoyed at this point.",
    ],
    "urgent": [
        "I need this sorted out today.", "This is urgent, I need it for my son's birthday on {weekday}.",
        "Please respond ASAP.", "I need this resolved immediately.", "It's time-sensitive.",
        "It's a gift for an event this weekend so I really need an answer now.",
        "I need an answer before {weekday}.", "Please treat this as a priority, I'm travelling soon.",
    ],
    "angry": [
        "This is the third time I've contacted you about this.",
        "If this isn't fixed I'm filing a chargeback with my bank.", "This is completely unacceptable!!",
        "Worst customer service I have ever dealt with.", "I've emailed twice and nobody has replied.",
        "I will be leaving a one-star review.", "My patience has run out.",
        "I'm seriously considering never ordering from here again.", "Absolutely ridiculous.",
        "I want someone to call me back TODAY.",
    ],
}
TONE_WEIGHTS = {None: 45, "calm": 14, "neutral": 11, "frustrated": 14, "urgent": 8, "angry": 8}


def fill(template: str, rng: random.Random) -> str:
    return template.format(
        item=rng.choice(ITEMS),
        oid=order_id(rng),
        days=rng.choice(DAYS),
        weekday=rng.choice(WEEKDAYS),
        amount=f"{rng.randint(12, 450)}.{rng.randint(0, 99):02d}",
        compat=rng.choice(COMPAT),
        name=rng.choice(NAMES),
    )


def tone_sentence(rng: random.Random) -> tuple[str | None, str]:
    """Pick a tone (or none) and a sentence expressing it."""
    tone = rng.choices(list(TONE_WEIGHTS), weights=list(TONE_WEIGHTS.values()))[0]
    return tone, fill(rng.choice(TONES[tone]), rng) if tone else ""


def add_tone(text: str, rng: random.Random) -> str:
    """Append (or occasionally prepend) a tone sentence; used for Bitext rows too."""
    tone, sentence = tone_sentence(rng)
    if not sentence:
        return text
    return f"{sentence} {text}" if rng.random() < 0.2 else f"{text.rstrip()} {sentence}"


def noisify(text: str, rng: random.Random) -> str:
    """Lowercase, drop trailing punctuation and add a typo or two, like hurried real messages."""
    words = text.lower().rstrip(".!").split()
    for i, word in enumerate(words):
        if len(word) >= 5 and word.isalpha() and rng.random() < 0.1:
            j = rng.randint(1, len(word) - 3)
            if rng.random() < 0.5:
                word = word[:j] + word[j + 1] + word[j] + word[j + 2 :]  # swap two letters
            else:
                word = word[:j] + word[j + 1 :]  # drop a letter
            words[i] = word
    return " ".join(words)


def make_ticket(category: C, rng: random.Random, tone: bool = True) -> tuple[str, str]:
    """Return (text, group) for one synthetic ticket of the given category.

    With `tone=False` no tone sentence or shouting is added (the urgency dataset adds its own).
    """
    if rng.random() < 0.25:
        idx = rng.randrange(len(SHORT[category]))
        text = fill(SHORT[category][idx], rng)
        if tone and rng.random() < 0.3:
            text = add_tone(text, rng)
        return (noisify(text, rng) if rng.random() < 0.4 else text), f"{category}:short{idx}"

    idx = rng.randrange(len(CORES[category]))
    core = fill(CORES[category][idx], rng)
    tone_name, sentence = tone_sentence(rng) if tone else (None, "")
    if tone_name == "angry" and rng.random() < 0.3:
        core = core.upper()
    if tone_name in {"angry", "urgent"} and rng.random() < 0.3:
        core = core.rstrip(".?!") + "!!"
    parts = [rng.choice(OPENERS), core, sentence, fill(rng.choice(CLOSERS), rng)]
    text = " ".join(p for p in parts if p)
    if rng.random() < 0.15:
        text = noisify(text, rng)
    return text, f"{category}:core{idx}"


def generate(
    category: C, count: int, rng: random.Random, exclude: set[str] = frozenset(), tone: bool = True
) -> list[dict]:
    """Generate `count` unique tickets for a category (unique after lowercasing)."""
    rows, seen = [], set(exclude)
    for _ in range(count * 50):
        if len(rows) == count:
            break
        text, group = make_ticket(category, rng, tone=tone)
        key = text.lower().strip(string.punctuation + " ")
        if key not in seen:
            seen.add(key)
            rows.append({"text": text, "category": str(category), "source": "template", "group": group})
    return rows
