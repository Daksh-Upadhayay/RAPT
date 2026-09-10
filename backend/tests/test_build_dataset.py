import random

from app.core.enums import TicketCategory
from scripts.build_dataset import fill_placeholders, skeleton
from scripts.ticket_templates import generate
from scripts.urgency_phrases import compose


def test_fill_placeholders_replaces_every_placeholder() -> None:
    text = fill_placeholders("refund of {{Currency Symbol}}{{Refund Amount}} for {{Order Number}}", random.Random(0))
    assert "{{" not in text
    assert text.startswith("refund of $")


def test_skeleton_groups_near_duplicates() -> None:
    assert skeleton("Cancel order #12345!") == skeleton("cancel order 999")


def test_generate_returns_unique_rows_for_the_category() -> None:
    rows = generate(TicketCategory.DAMAGED_ITEM, 200, random.Random(0))
    assert len(rows) == 200
    assert len({r["text"].lower() for r in rows}) == 200
    assert {r["category"] for r in rows} == {"damaged_item"}
    assert all(r["group"].startswith("damaged_item:") for r in rows)


def test_generate_without_tone_adds_no_tone_sentences() -> None:
    rows = generate(TicketCategory.CANCELLATION, 100, random.Random(0), tone=False)
    assert not any("chargeback" in r["text"] or "No rush" in r["text"] for r in rows)


def test_compose_keeps_the_ticket_and_varies_the_wrapping() -> None:
    rng = random.Random(0)
    base = "My blender arrived cracked."
    wrapped = [compose(base, rng) for _ in range(200)]
    assert all(base in w for w in wrapped)
    assert base in wrapped  # some tickets get no urgency phrasing at all
    assert len(set(wrapped)) > 100  # ~30% stay unwrapped (identical), nearly all others differ


def test_stakes_phrases_are_calm_and_mostly_labelled_high() -> None:
    from app.core.enums import TicketUrgency
    from app.ml.weak_labels import weak_label
    from scripts.urgency_phrases import STAKES_KINDS

    rng = random.Random(0)
    phrases = [kind(rng) for kind in STAKES_KINDS for _ in range(50)]
    assert not any("!" in p for p in phrases)
    high = sum(weak_label(p).label is TicketUrgency.HIGH for p in phrases)
    assert high / len(phrases) > 0.8  # some misses are deliberate label noise
