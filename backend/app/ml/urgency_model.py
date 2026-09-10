from app.core.config import settings
from app.core.enums import ModelName, TicketUrgency
from app.ml.store import load_bundle
from app.schemas.prediction import UrgencyPrediction


def predict_urgency(text: str) -> UrgencyPrediction:
    """Classify ticket text (subject + body) as low / medium / high urgency.

    Trained on weak labels by scripts/train_urgency_model.py; the version comes from settings.
    """
    bundle = load_bundle(ModelName.URGENCY_CLASSIFIER, settings.urgency_model_version)
    label, confidence = bundle.predict(text)
    return UrgencyPrediction(label=TicketUrgency(label), confidence=confidence, model_version=bundle.version)
