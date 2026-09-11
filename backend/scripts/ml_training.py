"""Shared training + evaluation helpers for train_category_model.py and train_urgency_model.py."""

import hashlib
import itertools
import json
import platform
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from app.core.enums import ModelName
from app.ml.store import ModelBundle, artifact_dir, save_bundle

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATASET_PATH = DATA_DIR / "processed" / "tickets.csv"
HANDWRITTEN_PATH = DATA_DIR / "eval" / "handwritten_test_set.csv"
URGENCY_HOLDOUT_PATH = DATA_DIR / "eval" / "urgency_holdout_test.csv"
URGENCY_FRESH_PATH = DATA_DIR / "eval" / "urgency_fresh_test.csv"
# Reviewer corrections exported from the database by scripts/export_feedback.py (not in git)
FEEDBACK_PATH = DATA_DIR / "feedback" / "corrections.csv"
SEED = 42
CONFIDENCE_THRESHOLD = 0.6  # the Escalation Agent's cut-off (03-agent-architecture.md)


def load_splits(path: Path = DATASET_PATH) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise SystemExit(f"{path} not found; run the matching scripts.build_* script first")
    df = pd.read_csv(path)
    return {split: df[df["split"] == split].reset_index(drop=True) for split in ("train", "val", "test")}


def load_handwritten() -> pd.DataFrame:
    return pd.read_csv(HANDWRITTEN_PATH)


def load_urgency_dev() -> pd.DataFrame:
    """Human urgency labels used for tuning from urgency v3 on: the 120 hand-written
    tickets plus the owner's 50-ticket holdout. Both were used for earlier decisions, so
    they are no longer clean test sets."""
    parts = [pd.read_csv(path)[["text", "urgency"]] for path in (HANDWRITTEN_PATH, URGENCY_HOLDOUT_PATH)]
    return pd.concat(parts, ignore_index=True)


def load_urgency_human() -> pd.DataFrame:
    """Every human urgency label we have (from urgency v4 on): the dev set plus the fresh
    set that chose v3. Used as training data with cross-validation, so none of it is a
    clean test any more; v4 needs a new fresh set."""
    dev = load_urgency_dev().assign(source="dev")
    fresh = pd.read_csv(URGENCY_FRESH_PATH)[["text", "urgency"]].assign(source="fresh_v3")
    # Reviewers' urgency corrections on real tickets (Phase 6), when exported
    feedback = load_feedback("urgency").assign(source="feedback")
    return pd.concat([dev, fresh, feedback], ignore_index=True)


def load_feedback(label: str, path: Path = FEEDBACK_PATH) -> pd.DataFrame:
    """Real tickets whose `label` ("category" or "urgency") a reviewer corrected:
    columns `text` and `label`. Empty if nothing has been exported yet."""
    if not path.exists():
        return pd.DataFrame({"text": pd.Series(dtype=str), label: pd.Series(dtype=str)})
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return df.loc[df[label] != "", ["text", label]].reset_index(drop=True)


def feedback_metadata(label: str, path: Path = FEEDBACK_PATH, weight: float | None = None) -> dict:
    """What a model was trained with, so scripts/export_feedback.py can tell whether newer
    corrections exist than the served model has seen."""
    rows = len(load_feedback(label, path))
    return {
        "path": str(path.relative_to(DATA_DIR.parent)) if path.is_relative_to(DATA_DIR.parent) else str(path),
        "sha256": file_sha256(path) if path.exists() else None,
        "rows": rows,
        **({"weight": weight} if weight is not None else {}),
    }


def tune_class_weights(
    proba: np.ndarray,
    y_true: Sequence[str],
    classes: list[str],
    grid: Sequence[float] = (0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0),
    min_last_recall: float = 0.0,
) -> tuple[tuple[float, ...], float]:
    """Pick per-class probability multipliers (first class fixed at 1) that maximise
    macro-F1 among the settings whose recall on the last class (`high`) is at least
    `min_last_recall`; if none reach it, the highest recall wins. Ties go to higher
    last-class recall, then to the weights closest to 1."""
    best_key, best = None, None
    for rest in itertools.product(grid, repeat=len(classes) - 1):
        weights = (1.0, *rest)
        y_pred = [classes[i] for i in (proba * np.asarray(weights)).argmax(axis=1)]
        f1 = f1_score(y_true, y_pred, labels=classes, average="macro", zero_division=0)
        last_recall = recall_score(y_true, y_pred, labels=[classes[-1]], average="macro", zero_division=0)
        feasible = last_recall >= min_last_recall
        key = (feasible, round(f1, 4) if feasible else 0.0, round(last_recall, 4), -sum(abs(w - 1) for w in weights))
        if best_key is None or key > best_key:
            best_key, best = key, weights
    return best, best_key[1]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_new_version(model_name: ModelName, version: str, force: bool) -> Path:
    """Refuse to overwrite a version that stored predictions may already reference."""
    out_dir = artifact_dir(model_name, version)
    if (out_dir / "model.joblib").exists() and not force:
        raise SystemExit(f"{out_dir} already exists; pass a new --version (or --force to overwrite)")
    return out_dir


# --- training -------------------------------------------------------------------------


@dataclass
class Trained:
    pipeline: Pipeline
    params: dict
    selection: list[dict] = field(default_factory=list)  # every candidate's val score


def train_xgboost(
    features: FeatureUnion,
    train: tuple[Sequence[str], np.ndarray],
    val: tuple[Sequence[str], np.ndarray],
    max_depths: Sequence[int] = (4, 6),
    balance_classes: bool = False,
    sample_weight: np.ndarray | None = None,
) -> Trained:
    """Fit TF-IDF(+extra) features on train, then pick XGBoost depth by val macro-F1.

    The number of trees is chosen by early stopping on the val split (val mlogloss).
    The test split is never touched here. `sample_weight` up-weights rows (e.g. reviewer
    corrections); it multiplies the class balancing when both are used.
    """
    features = clone(features).fit(train[0])
    X_train, X_val = features.transform(train[0]), features.transform(val[0])
    weights = compute_sample_weight("balanced", train[1]) if balance_classes else None
    if sample_weight is not None:
        weights = sample_weight if weights is None else weights * sample_weight

    best, best_score, selection = None, -1.0, []
    for depth in max_depths:
        params = dict(
            n_estimators=1000,
            learning_rate=0.1,
            max_depth=depth,
            subsample=0.8,
            colsample_bytree=0.5,
            tree_method="hist",
            early_stopping_rounds=30,
            eval_metric="mlogloss",
            random_state=SEED,
            n_jobs=-1,
        )
        clf = XGBClassifier(**params).fit(X_train, train[1], sample_weight=weights, eval_set=[(X_val, val[1])], verbose=False)
        score = f1_score(val[1], clf.predict(X_val), average="macro")
        chosen = {"max_depth": depth, "best_iteration": int(clf.best_iteration), "val_macro_f1": round(score, 4)}
        selection.append(chosen)
        if score > best_score:
            best, best_score = Trained(Pipeline([("features", features), ("clf", clf)]), params | chosen), score
    best.selection = selection
    return best


def train_logreg_baseline(
    features: FeatureUnion, train: tuple[Sequence[str], np.ndarray], sample_weight: np.ndarray | None = None
) -> Pipeline:
    """Same features + logistic regression: the simple baseline XGBoost has to beat."""
    pipeline = Pipeline([("features", clone(features)), ("clf", LogisticRegression(max_iter=3000, C=5.0))])
    return pipeline.fit(*train, clf__sample_weight=sample_weight)


def train_logreg(
    features: FeatureUnion,
    train: tuple[Sequence[str], np.ndarray],
    val: tuple[Sequence[str], np.ndarray],
    Cs: Sequence[float] = (0.5, 2.0, 8.0, 32.0),
    balance_classes: bool = False,
) -> Trained:
    """Fit features on train, then pick logistic regression's C by val macro-F1."""
    features = clone(features).fit(train[0])
    X_train, X_val = features.transform(train[0]), features.transform(val[0])
    class_weight = "balanced" if balance_classes else None

    best, best_score, selection = None, -1.0, []
    for C in Cs:
        params = dict(C=C, class_weight=class_weight, max_iter=5000)
        clf = LogisticRegression(**params).fit(X_train, train[1])
        score = f1_score(val[1], clf.predict(X_val), average="macro")
        selection.append({"C": C, "val_macro_f1": round(score, 4)})
        if score > best_score:
            best, best_score = Trained(Pipeline([("features", features), ("clf", clf)]), params), score
    best.selection = selection
    return best


# --- evaluation -----------------------------------------------------------------------


def evaluate(y_true: Sequence[str], y_pred: Sequence[str], classes: list[str], confidence: np.ndarray | None = None) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    result = {
        "n": len(y_true),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=classes, average="macro", zero_division=0), 4),
        "per_class": {
            c: {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "support": int(s)}
            for c, p, r, f, s in zip(classes, precision, recall, f1, support, strict=True)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=classes).tolist(),
    }
    if confidence is not None:
        correct = np.asarray(y_true) == np.asarray(y_pred)
        low = confidence < CONFIDENCE_THRESHOLD
        result["confidence"] = {
            "mean": round(float(confidence.mean()), 4),
            "share_below_threshold": round(float(low.mean()), 4),
            "accuracy_above_threshold": round(float(correct[~low].mean()), 4) if (~low).any() else None,
            "accuracy_below_threshold": round(float(correct[low].mean()), 4) if low.any() else None,
        }
    return result


def predict_labels(pipeline: Pipeline, classes: list[str], texts: Sequence[str]) -> tuple[list[str], np.ndarray]:
    proba = pipeline.predict_proba(list(texts))
    return [classes[i] for i in proba.argmax(axis=1)], proba.max(axis=1)


def top_features(pipeline: Pipeline, n: int = 20) -> list[tuple[str, float]]:
    """Features XGBoost gained the most from, summed over all trees."""
    names = pipeline.named_steps["features"].get_feature_names_out()
    gain = pipeline.named_steps["clf"].get_booster().get_score(importance_type="total_gain")
    ranked = sorted(((names[int(k[1:])], v) for k, v in gain.items()), key=lambda kv: -kv[1])
    return [(name, round(v, 1)) for name, v in ranked[:n]]


def top_coefficients(pipeline: Pipeline, classes: list[str], n: int = 12) -> dict[str, list[str]]:
    """Logistic regression: the features pushing hardest towards each class."""
    names = pipeline.named_steps["features"].get_feature_names_out()
    coef = pipeline.named_steps["clf"].coef_
    return {c: [names[i] for i in np.argsort(-coef[k])[:n]] for k, c in enumerate(classes)}


def metadata(dataset_path: Path, extra: dict) -> dict:
    return {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": str(dataset_path.relative_to(DATA_DIR.parent)),
        "dataset_sha256": file_sha256(dataset_path),
        "handwritten_sha256": file_sha256(HANDWRITTEN_PATH),
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "xgboost": xgboost.__version__,
        **extra,
    }


# --- report ---------------------------------------------------------------------------


def md_per_class(result: dict) -> str:
    lines = ["| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    for c, m in result["per_class"].items():
        lines.append(f"| {c} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['support']} |")
    lines.append(f"| **macro avg** | | | **{result['macro_f1']:.2f}** | {result['n']} |")
    lines.append(f"\nAccuracy: {result['accuracy']:.2f}")
    return "\n".join(lines)


def md_confusion(result: dict, classes: list[str]) -> str:
    short = [c.replace("_", " ") for c in classes]
    lines = ["| true \\ predicted | " + " | ".join(short) + " |", "|---" * (len(classes) + 1) + "|"]
    for c, row in zip(short, result["confusion_matrix"], strict=True):
        lines.append(f"| **{c}** | " + " | ".join(str(v) if v else "·" for v in row) + " |")
    return "\n".join(lines)


def md_confidence(results: dict[str, dict]) -> str:
    lines = [
        f"| eval set | mean confidence | share < {CONFIDENCE_THRESHOLD} | accuracy when ≥ {CONFIDENCE_THRESHOLD} | accuracy when < {CONFIDENCE_THRESHOLD} |",
        "|---|---|---|---|---|",
    ]
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"
    for name, r in results.items():
        c = r["confidence"]
        lines.append(
            f"| {name} | {c['mean']:.2f} | {c['share_below_threshold']:.0%} | "
            f"{fmt(c['accuracy_above_threshold'])} | {fmt(c['accuracy_below_threshold'])} |"
        )
    return "\n".join(lines)


def md_summary(rows: dict[str, dict[str, dict]]) -> str:
    """rows: model name -> eval set name -> result."""
    sets = list(next(iter(rows.values())))
    lines = ["| model | " + " | ".join(f"{s} macro-F1 / acc" for s in sets) + " |", "|---" * (len(sets) + 1) + "|"]
    for model, results in rows.items():
        cells = [f"{results[s]['macro_f1']:.2f} / {results[s]['accuracy']:.2f}" for s in sets]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def md_errors(texts: Sequence[str], y_true: Sequence[str], y_pred: Sequence[str], confidence: np.ndarray, limit: int = 20) -> str:
    rows = [(t, a, p, c) for t, a, p, c in zip(texts, y_true, y_pred, confidence, strict=True) if a != p]
    if not rows:
        return "_No errors._"
    lines = ["| text | true | predicted | conf |", "|---|---|---|---|"]
    for t, a, p, c in rows[:limit]:
        t = t.replace("|", "/").replace("\n", " ")
        lines.append(f"| {t[:140] + ('…' if len(t) > 140 else '')} | {a} | {p} | {c:.2f} |")
    if len(rows) > limit:
        lines.append(f"\n_…and {len(rows) - limit} more._")
    return "\n".join(lines)


def save_outputs(out_dir: Path, model_name: ModelName, bundle: ModelBundle, metrics: dict, report: str) -> None:
    save_bundle(bundle, model_name)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out_dir / "report.md").write_text(report)
