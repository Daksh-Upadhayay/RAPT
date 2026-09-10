import pytest

from app.core.enums import TicketUrgency
from app.ml.weak_labels import weak_label


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Does the kettle come with a warranty?", TicketUrgency.LOW),
        ("where is my order", TicketUrgency.LOW),
        # "concern" in a greeting is not frustration
        ("To whom it may concern, please cancel order 12345.", TicketUrgency.LOW),
        # carrier acronyms are not shouting
        ("My UPS tracking says it was handed to USPS.", TicketUrgency.LOW),
        ("My blender arrived cracked.", TicketUrgency.MEDIUM),
        ("I'm pretty disappointed with how long this is taking.", TicketUrgency.MEDIUM),
        ("I want a full refund for order 555.", TicketUrgency.MEDIUM),
        ("I need this sorted out today or I'm filing a chargeback.", TicketUrgency.HIGH),
        ("This is the third time I've contacted you about this.", TicketUrgency.HIGH),
        ("The heater started sparking when I plugged it in.", TicketUrgency.HIGH),
        # two weak HIGH signals: shouting + strong anger
        ("THIS IS RIDICULOUS, WHERE IS IT", TicketUrgency.HIGH),
        # weak HIGH + MEDIUM
        ("My package is late!!", TicketUrgency.HIGH),
    ],
)
def test_weak_label(text: str, expected: TicketUrgency) -> None:
    assert weak_label(text).label is expected


def test_weak_label_reports_which_rules_fired() -> None:
    result = weak_label("Please respond ASAP, I will dispute the charge with my bank.")
    assert {"time_pressure", "escalation_threat"} <= set(result.fired)
    assert weak_label("Is the lamp dimmable?").fired == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # calm_language cancels the false "urgent" hit
        ("Just wanted to update my email preferences, nothing urgent.", TicketUrgency.LOW),
        ("The tracking hasn't updated in three days, can you check?", TicketUrgency.MEDIUM),
        ("My discount code didn't apply at checkout.", TicketUrgency.MEDIUM),
        ("I need it for a wedding tomorrow morning and it's nowhere to be seen.", TicketUrgency.HIGH),
        ("That refund was my rent money.", TicketUrgency.HIGH),
        ("I want to speak to a manager about this order.", TicketUrgency.HIGH),
    ],
)
def test_weak_label_v3_rules(text: str, expected: TicketUrgency) -> None:
    assert weak_label(text).label is expected


@pytest.mark.parametrize(
    "text",
    [
        # calm but high-stakes (v4): no anger, the situation is what makes them urgent
        "I have a flight tomorrow and the adapter never arrived.",
        "The outlet on the power strip feels warm to the touch.",
        "There's a charge on my card from you that I didn't make.",
        "My refund went to a closed account.",
        "The confirmation email shows another customer's name and address.",
    ],
)
def test_weak_label_calm_high_stakes(text: str) -> None:
    assert weak_label(text).label is TicketUrgency.HIGH


def test_trip_months_away_is_not_a_deadline() -> None:
    assert weak_label("Just wondering when my trip gear ships, the trip is in August.").label is TicketUrgency.LOW
