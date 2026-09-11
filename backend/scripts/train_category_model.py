"""Train the ticket category classifier: TF-IDF (word + character n-grams) + XGBoost.

- fits on the train split of data/processed/tickets.csv, plus reviewers' category
  corrections from data/feedback/corrections.csv (scripts/export_feedback.py), weighted
  by --feedback-weight
- picks tree depth and tree count on the val split
- reports per-class precision/recall/F1 + confusion matrices on the test split (held-out,
  in-distribution) and on data/eval/handwritten_test_set.csv (out-of-distribution)
- compares against a logistic-regression baseline on the same features
- saves app/ml/artifacts/category_classifier/<version>/{model.joblib, metrics.json, report.md}

Usage (from backend/):
    uv run python -m scripts.train_category_model --version v1
"""

import argparse
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from app.core.enums import ModelName, TicketCategory
from app.ml.store import ModelBundle
from app.ml.text_features import normalize_text
from scripts.ml_training import (
    DATASET_PATH,
    FEEDBACK_PATH,
    ensure_new_version,
    evaluate,
    feedback_metadata,
    load_feedback,
    load_handwritten,
    load_splits,
    md_confidence,
    md_confusion,
    md_errors,
    md_per_class,
    md_summary,
    metadata,
    predict_labels,
    save_outputs,
    top_features,
    train_logreg_baseline,
    train_xgboost,
)

MODEL = ModelName.CATEGORY_CLASSIFIER
CLASSES = [str(c) for c in TicketCategory]
# Starting weight for a reviewer correction vs one synthetic row. Corrections are real
# tickets the model got wrong, and few; tune it by cross-validation over them (as urgency
# v4 does for human labels) once there are enough to measure (~50+).
DEFAULT_FEEDBACK_WEIGHT = 10.0


def make_features() -> FeatureUnion:
    # Character n-grams make the model robust to typos ("cacnel", "refudned") that
    # word features would treat as unknown words
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(preprocessor=normalize_text, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            (
                "char",
                TfidfVectorizer(
                    preprocessor=normalize_text, analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=40000
                ),
            ),
        ]
    )


def encode(labels) -> np.ndarray:
    return np.array([CLASSES.index(label) for label in labels])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--force", action="store_true", help="overwrite an existing version")
    parser.add_argument(
        "--feedback-weight", type=float, default=DEFAULT_FEEDBACK_WEIGHT, help="weight of each reviewer correction (0 = ignore them)"
    )
    parser.add_argument("--feedback", type=Path, default=FEEDBACK_PATH, help="corrections file (scripts/export_feedback.py)")
    args = parser.parse_args()
    out_dir = ensure_new_version(MODEL, args.version, args.force)

    splits = load_splits()
    handwritten = load_handwritten()
    data = {name: (df["text"].tolist(), encode(df["category"])) for name, df in splits.items()}

    # Reviewer corrections join the train split only: val/test/hand-written stay as they were
    feedback = load_feedback("category", args.feedback)
    if args.feedback_weight == 0:
        feedback = feedback.iloc[:0]
    train_texts = data["train"][0] + feedback["text"].tolist()
    train_labels = np.concatenate([data["train"][1], encode(feedback["category"])]).astype(int)
    sample_weight = np.r_[np.ones(len(data["train"][0])), np.full(len(feedback), args.feedback_weight)]
    print(f"Train rows: {len(data['train'][0])} synthetic + {len(feedback)} reviewer corrections (weight {args.feedback_weight})")

    print("Training XGBoost ...")
    xgb = train_xgboost(make_features(), (train_texts, train_labels), data["val"], sample_weight=sample_weight)
    print(f"  selected {xgb.selection}")
    print("Training logistic-regression baseline ...")
    logreg = train_logreg_baseline(make_features(), (train_texts, train_labels), sample_weight=sample_weight)

    eval_sets = {
        "val": (splits["val"]["text"], splits["val"]["category"]),
        "test": (splits["test"]["text"], splits["test"]["category"]),
        "handwritten": (handwritten["text"], handwritten["category"]),
    }
    results: dict[str, dict[str, dict]] = {"XGBoost": {}, "LogReg baseline": {}}
    predictions = {}
    for name, (texts, y_true) in eval_sets.items():
        y_pred, conf = predict_labels(xgb.pipeline, CLASSES, texts)
        predictions[name] = (y_pred, conf)
        results["XGBoost"][name] = evaluate(y_true.tolist(), y_pred, CLASSES, conf)
        lr_pred, _ = predict_labels(logreg, CLASSES, texts)
        results["LogReg baseline"][name] = evaluate(y_true.tolist(), lr_pred, CLASSES)

    xr = results["XGBoost"]
    hw_pred, hw_conf = predictions["handwritten"]
    report = f"""# Category classifier {args.version}

TF-IDF (word 1-2-grams + character 3-5-grams) → XGBoost. Generated by
`scripts/train_category_model.py`; numbers are in `metrics.json`.

Training data: `{DATASET_PATH.name}` — train {len(splits["train"])} / val {len(splits["val"])} /
test {len(splits["test"])} rows (grouped split, see `scripts/build_dataset.py`), plus
{len(feedback)} reviewer corrections in train (weight {args.feedback_weight}). Hand-written
out-of-distribution set: {len(handwritten)} tickets.

## Summary

{md_summary(results)}

- **val**: used to choose depth and the number of trees (early stopping), so slightly optimistic.
- **test**: held-out split of the same Bitext + template data, never used for any decision.
  Sentence phrasings in it are unseen, but the style is the same as training.
- **handwritten**: realistic tickets written separately from the templates. **This is the
  headline number** — it is what to expect on real tickets.

## XGBoost — test split (in-distribution)

{md_per_class(xr["test"])}

{md_confusion(xr["test"], CLASSES)}

## XGBoost — hand-written set (out-of-distribution)

{md_per_class(xr["handwritten"])}

{md_confusion(xr["handwritten"], CLASSES)}

### Misclassified hand-written tickets

{md_errors(handwritten["text"], handwritten["category"], hw_pred, hw_conf)}

## Confidence vs. the 0.6 escalation threshold

The Escalation Agent flags tickets whose category confidence is below 0.6.

{md_confidence({k: xr[k] for k in ("test", "handwritten")})}

## Model selection (val)

{chr(10).join(f"- max_depth={s['max_depth']}: {s['best_iteration'] + 1} trees, val macro-F1 {s['val_macro_f1']:.3f}" for s in xgb.selection)}

## Most useful features (XGBoost total gain)

{", ".join(f"`{name}`" for name, _ in top_features(xgb.pipeline))}
"""
    metrics = {
        "model": str(MODEL),
        "version": args.version,
        "classes": CLASSES,
        "params": {k: v for k, v in xgb.params.items() if k != "n_jobs"},
        "selection": xgb.selection,
        "results": results,
        "metadata": metadata(
            DATASET_PATH,
            {
                "n_train": len(train_texts),
                "feedback": feedback_metadata("category", args.feedback, args.feedback_weight) | {"rows": len(feedback)},
            },
        ),
    }
    save_outputs(out_dir, MODEL, ModelBundle(xgb.pipeline, CLASSES, args.version), metrics, report)

    print(md_summary(results))
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
