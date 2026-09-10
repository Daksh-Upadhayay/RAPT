"""Train the urgency classifier with weak supervision.

1. Label every row of the dataset (default data/processed/urgency_tickets.csv, built by
   scripts/build_urgency_dataset.py) with the keyword/heuristic rules in
   app/ml/weak_labels.py (no human urgency labels exist for this data).
2. Train four candidates on the train split's weak labels: {TF-IDF + tone features,
   TF-IDF + tone + sentence embeddings} x {logistic regression, XGBoost}. Each family's
   hyperparameters (C, tree depth/count) are tuned on the weak-labelled val split.
3. Pick the candidate with the best macro-F1 on the human-labelled dev set
   (scripts.ml_training.load_urgency_dev). Then tune per-class probability weights on
   the same dev set, so the model trades a few extra `medium`/`high` calls for fewer
   missed ones.
4. Save app/ml/artifacts/urgency_classifier/<version>/{model.joblib, metrics.json, report.md}

The dev set is used for choices here, so its scores are optimistic. The real number comes
from a fresh set scored once with scripts/evaluate_model.py after training.

Version history: v1 = XGBoost on tickets.csv; v2 = val-selected LogReg on
urgency_tickets.csv; v3 = this script (revised rules, embeddings, dev-set selection).

Usage (from backend/):
    uv run python -m scripts.train_urgency_model --version v3
"""

import argparse
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from app.core.enums import ModelName, TicketUrgency
from app.ml.store import ModelBundle
from app.ml.text_features import SentenceEmbeddings, ToneFeatures, normalize_text
from app.ml.weak_labels import LABELING_FUNCTIONS, weak_label
from scripts.build_urgency_dataset import OUTPUT_PATH as URGENCY_DATASET_PATH
from scripts.ml_training import (
    URGENCY_HOLDOUT_PATH,
    Trained,
    ensure_new_version,
    evaluate,
    file_sha256,
    load_splits,
    load_urgency_dev,
    md_confidence,
    md_confusion,
    md_errors,
    md_per_class,
    md_summary,
    metadata,
    save_outputs,
    top_coefficients,
    top_features,
    train_logreg,
    train_xgboost,
    tune_class_weights,
)

MODEL = ModelName.URGENCY_CLASSIFIER
CLASSES = [str(u) for u in TicketUrgency]


def tfidf_tone() -> FeatureUnion:
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(preprocessor=normalize_text, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("tone", ToneFeatures()),
        ]
    )


def tfidf_tone_embeddings() -> FeatureUnion:
    return FeatureUnion([*tfidf_tone().transformer_list, ("emb", SentenceEmbeddings())])


FEATURE_SETS: dict[str, Callable[[], FeatureUnion]] = {
    "tfidf+tone": tfidf_tone,
    "tfidf+tone+emb": tfidf_tone_embeddings,
}


def encode(labels) -> np.ndarray:
    return np.array([CLASSES.index(label) for label in labels])


def md_lf_coverage(texts) -> str:
    labels = [weak_label(t) for t in texts]
    fired = Counter(name for wl in labels for name in wl.fired)
    lines = ["| rule | votes | strong | fires on (train) |", "|---|---|---|---|"]
    for lf in LABELING_FUNCTIONS:
        lines.append(f"| `{lf.name}` | {lf.vote} | {'yes' if lf.strong else ''} | {fired[lf.name] / len(texts):.1%} |")
    none = sum(not wl.fired for wl in labels) / len(texts)
    lines.append(f"\nNo rule fires (→ low by default) on {none:.1%} of train rows.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dataset", type=Path, default=URGENCY_DATASET_PATH, help="v1 used data/processed/tickets.csv")
    parser.add_argument("--force", action="store_true", help="overwrite an existing version")
    args = parser.parse_args()
    out_dir = ensure_new_version(MODEL, args.version, args.force)

    splits = load_splits(args.dataset)
    for df in splits.values():
        df["urgency_weak"] = [str(weak_label(t).label) for t in df["text"]]
    dev = load_urgency_dev()
    dev_texts, dev_true = dev["text"].tolist(), dev["urgency"].tolist()
    data = {name: (df["text"].tolist(), encode(df["urgency_weak"])) for name, df in splits.items()}
    train_dist = Counter(splits["train"]["urgency_weak"])
    print("Weak label distribution (train):", dict(train_dist))

    candidates: dict[str, Trained] = {}
    for feature_name, make_features in FEATURE_SETS.items():
        print(f"Training LogReg / XGBoost on {feature_name} ...")
        candidates[f"LogReg {feature_name}"] = train_logreg(make_features(), data["train"], data["val"], balance_classes=True)
        candidates[f"XGBoost {feature_name}"] = train_xgboost(make_features(), data["train"], data["val"], balance_classes=True)

    eval_sets = {
        "val (weak)": (splits["val"]["text"].tolist(), splits["val"]["urgency_weak"].tolist()),
        "test (weak)": (splits["test"]["text"].tolist(), splits["test"]["urgency_weak"].tolist()),
        "dev (human)": (dev_texts, dev_true),
    }
    results: dict[str, dict[str, dict]] = {}
    for name, trained in candidates.items():
        bundle = ModelBundle(trained.pipeline, CLASSES, args.version)
        results[name] = {}
        for set_name, (texts, y_true) in eval_sets.items():
            y_pred, conf = bundle.predict_many(texts)
            results[name][set_name] = evaluate(y_true, y_pred, CLASSES, conf)
        print(f"  {name}: dev macro-F1 {results[name]['dev (human)']['macro_f1']:.3f}")

    # Choose on human labels, then tune the decision weights on the same dev set
    shipped = max(candidates, key=lambda n: results[n]["dev (human)"]["macro_f1"])
    dev_proba = candidates[shipped].pipeline.predict_proba(dev_texts)
    weights, tuned_f1 = tune_class_weights(dev_proba, dev_true, CLASSES)
    bundle = ModelBundle(candidates[shipped].pipeline, CLASSES, args.version, class_weights=weights)
    print(f"Shipping {shipped} with class weights {dict(zip(CLASSES, weights, strict=True))} (dev macro-F1 {tuned_f1:.3f})")

    final_name = f"{shipped} + weights"
    results[final_name] = {}
    final_preds = {}
    for set_name, (texts, y_true) in eval_sets.items():
        y_pred, conf = bundle.predict_many(texts)
        final_preds[set_name] = (y_pred, conf)
        results[final_name][set_name] = evaluate(y_true, y_pred, CLASSES, conf)
    rules_dev = evaluate(dev_true, [str(weak_label(t).label) for t in dev_texts], CLASSES)

    fr = results[final_name]
    dev_pred, dev_conf = final_preds["dev (human)"]
    shipped_pipeline = candidates[shipped].pipeline
    if shipped.startswith("XGBoost"):
        features_md = ", ".join(f"`{name}`" for name, _ in top_features(shipped_pipeline))
    else:
        features_md = "\n".join(
            f"- **{c}**: " + ", ".join(f"`{f}`" for f in feats)
            for c, feats in top_coefficients(shipped_pipeline, CLASSES).items()
        )
    selection_lines = [f"- **{name}** (val-tuned params): {t.selection}" for name, t in candidates.items()]

    report = f"""# Urgency classifier {args.version}

Weak supervision: keyword/heuristic rules (`app/ml/weak_labels.py`) label the training
data (`{args.dataset.name}`), then four candidates learn from those labels:
TF-IDF word 1-2-grams + tone features (VADER, caps, `!`/`?`, length), with or without
sentence embeddings (`all-MiniLM-L6-v2`), each through logistic regression and XGBoost.
The best candidate on the **human-labelled dev set** ({len(dev)} tickets) is shipped,
with per-class probability weights tuned on the same dev set:

**Shipped: {shipped}**, class weights {", ".join(f"{c} ×{w}" for c, w in zip(CLASSES, weights, strict=True))}.

Weak label distribution (train, {len(splits["train"])} rows):
{", ".join(f"{c} {train_dist[c]} ({train_dist[c] / len(splits["train"]):.0%})" for c in CLASSES)}.

## Summary

{md_summary(results)}

**Rules alone on the dev set:** macro-F1 {rules_dev["macro_f1"]:.2f} / accuracy {rules_dev["accuracy"]:.2f}.

- **val / test (weak)**: agreement with the rules' labels on held-out data. This measures
  how well a model *learned the rules*.
- **dev (human)**: human labels. The rules were revised on this set and the model and
  class weights were chosen on it, so **all dev numbers (rules included) are optimistic**.
  They are for comparing candidates, not for reporting.
- **The real number** comes from a fresh set scored once with `scripts/evaluate_model.py`.

## Shipped model: dev set (human labels)

{md_per_class(fr["dev (human)"])}

{md_confusion(fr["dev (human)"], CLASSES)}

### Rules alone

{md_per_class(rules_dev)}

{md_confusion(rules_dev, CLASSES)}

### Tickets the shipped model got wrong

{md_errors(dev_texts, dev_true, dev_pred, dev_conf, limit=40)}

## Confidence vs. the 0.6 escalation threshold

Confidence is the model's own probability for the chosen label (before class weights).

{md_confidence({k: fr[k] for k in ("test (weak)", "dev (human)")})}

## Labeling functions

`calm_language` cancels `time_pressure` and sentiment votes. Then: HIGH if any strong
HIGH rule fires, two weak HIGH rules fire, or a weak HIGH rule fires together with a
MEDIUM rule; MEDIUM if one weak HIGH or any MEDIUM rule fires; otherwise LOW.

{md_lf_coverage(splits["train"]["text"])}

## Hyperparameter selection (weak val)

{chr(10).join(selection_lines)}

## Most useful features ({shipped})

{features_md}
"""
    metrics = {
        "model": str(MODEL),
        "version": args.version,
        "classes": CLASSES,
        "shipped": shipped,
        "class_weights": dict(zip(CLASSES, weights, strict=True)),
        "params": {k: v for k, v in candidates[shipped].params.items() if k != "n_jobs"},
        "selection": {name: t.selection for name, t in candidates.items()},
        "weak_label_distribution_train": dict(train_dist),
        "results": results | {"Rules alone": {"dev (human)": rules_dev}},
        "metadata": metadata(
            args.dataset,
            {"n_train": len(splits["train"]), "n_dev": len(dev), "holdout_sha256": file_sha256(URGENCY_HOLDOUT_PATH)},
        ),
    }
    save_outputs(out_dir, MODEL, bundle, metrics, report)

    print(md_summary(results))
    print(f"Rules alone on dev: macro-F1 {rules_dev['macro_f1']:.2f} / acc {rules_dev['accuracy']:.2f}")
    print(f"\nSaved {shipped} to {out_dir}")


if __name__ == "__main__":
    main()
