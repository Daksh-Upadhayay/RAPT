import numpy as np

from app.ml.store import ModelBundle
from scripts.ml_training import tune_class_weights


class FixedProba:
    """Stands in for a fitted pipeline: returns the same probabilities for every text."""

    def __init__(self, proba: list[float]) -> None:
        self.proba = np.asarray(proba)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return np.tile(self.proba, (len(texts), 1))


def test_class_weights_change_the_label_but_not_the_confidence() -> None:
    pipeline = FixedProba([0.5, 0.2, 0.3])
    assert ModelBundle(pipeline, ["low", "medium", "high"], "vX").predict("x") == ("low", 0.5)

    weighted = ModelBundle(pipeline, ["low", "medium", "high"], "vX", class_weights=(1.0, 1.0, 2.0))
    label, confidence = weighted.predict("x")
    assert label == "high"
    assert confidence == 0.3  # the model's own probability, not the weighted score


def test_tune_class_weights_boosts_an_underpredicted_class() -> None:
    classes = ["low", "medium", "high"]
    # "high" tickets get only 0.4 probability; plain argmax calls them low
    proba = np.array([[0.8, 0.1, 0.1]] * 5 + [[0.5, 0.1, 0.4]] * 5)
    y_true = ["low"] * 5 + ["high"] * 5
    weights, f1 = tune_class_weights(proba, y_true, classes)
    assert weights[0] == 1.0
    assert 0.4 * weights[2] > 0.5  # high now wins on the high tickets
    assert 0.1 * weights[2] < 0.8  # ...but not on the low ones
    assert f1 > 0.6
