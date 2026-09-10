from app.core.config import settings
from app.core.enums import ModelName, TicketCategory
from app.ml.store import load_bundle
from app.schemas.prediction import CategoryPrediction


def predict_category(text: str) -> CategoryPrediction:
    """Classify ticket text (subject + body) into one of the six categories.

    Trained by scripts/train_category_model.py; the version comes from settings.
    """
    bundle = load_bundle(ModelName.CATEGORY_CLASSIFIER, settings.category_model_version)
    label, confidence = bundle.predict(text)
    return CategoryPrediction(label=TicketCategory(label), confidence=confidence, model_version=bundle.version)
