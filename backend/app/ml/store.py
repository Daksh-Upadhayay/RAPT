"""Saving and loading trained classifier artifacts.

Layout: app/ml/artifacts/<model_name>/<version>/
    model.joblib   - ModelBundle (fitted sklearn pipeline + class labels)
    metrics.json   - evaluation numbers + training metadata
    report.md      - human-readable evaluation report

Artifacts are pickles: only load files produced by the training scripts in this repo.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

from app.core.enums import ModelName

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


@dataclass
class ModelBundle:
    pipeline: Pipeline  # raw text in -> class probabilities out
    classes: list[str]  # label for each predict_proba column
    version: str
    # Per-class multipliers applied to the probabilities before picking a label, tuned on a
    # dev set to trade errors (e.g. miss fewer `high` tickets). None = plain argmax.
    # Bundles pickled before this field existed fall back to this class default.
    class_weights: tuple[float, ...] | None = None

    def predict_many(self, texts: list[str]) -> tuple[list[str], np.ndarray]:
        """Labels plus the model's probability for each chosen label (unweighted, so a
        label picked only thanks to its weight reports a low confidence)."""
        proba = self.pipeline.predict_proba(texts)
        scores = proba * np.asarray(self.class_weights) if self.class_weights else proba
        best = scores.argmax(axis=1)
        return [self.classes[i] for i in best], proba[np.arange(len(texts)), best]

    def predict(self, text: str) -> tuple[str, float]:
        """Chosen label and its probability."""
        labels, confidence = self.predict_many([text])
        return labels[0], float(confidence[0])


def artifact_dir(model_name: ModelName, version: str) -> Path:
    return ARTIFACTS_DIR / model_name / version


def save_bundle(bundle: ModelBundle, model_name: ModelName) -> Path:
    path = artifact_dir(model_name, bundle.version) / "model.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return path


@cache
def load_bundle(model_name: ModelName, version: str) -> ModelBundle:
    path = artifact_dir(model_name, version) / "model.joblib"
    if not path.exists():
        raise FileNotFoundError(f"No trained {model_name} {version} at {path}; run the training script first")
    return joblib.load(path)
