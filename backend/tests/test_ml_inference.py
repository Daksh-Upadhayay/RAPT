"""Smoke tests for the committed model artifacts and the inference wrappers."""

import pytest

from app.core.config import settings
from app.core.enums import ModelName, TicketCategory, TicketUrgency
from app.ml.category_model import predict_category
from app.ml.store import load_bundle
from app.ml.urgency_model import predict_urgency


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Please cancel order 12345, I ordered it by mistake.", TicketCategory.CANCELLATION),
        ("I returned the jacket two weeks ago and still haven't got my refund.", TicketCategory.REFUND_REQUEST),
        ("The lamp arrived broken, the glass shade is shattered.", TicketCategory.DAMAGED_ITEM),
        ("Does the air fryer come with a warranty?", TicketCategory.PRODUCT_QUESTION),
        # v1 read "arrived" as damage: every training row with the word was damaged_item
        ("my order has not arrived", TicketCategory.DELIVERY_DELAY),
        ("I ordered a lamp two weeks ago and it still has not arrived.", TicketCategory.DELIVERY_DELAY),
        ("The kettle arrived cracked.", TicketCategory.DAMAGED_ITEM),
    ],
)
def test_predict_category(text: str, expected: TicketCategory) -> None:
    prediction = predict_category(text)
    assert prediction.label is expected
    assert 0 <= prediction.confidence <= 1
    assert prediction.model_version == settings.category_model_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Does the lamp come in white? No rush.", TicketUrgency.LOW),
        ("I need this sorted out TODAY or I'm disputing the charge with my bank!!", TicketUrgency.HIGH),
    ],
)
def test_predict_urgency(text: str, expected: TicketUrgency) -> None:
    prediction = predict_urgency(text)
    assert prediction.label is expected
    assert 0 <= prediction.confidence <= 1
    assert prediction.model_version == settings.urgency_model_version


def test_unknown_version_raises() -> None:
    with pytest.raises(FileNotFoundError, match="run the training script"):
        load_bundle(ModelName.CATEGORY_CLASSIFIER, "v999")
