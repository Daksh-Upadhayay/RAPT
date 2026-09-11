"""Train the urgency classifier: weak supervision + human labels (v4 procedure).

1. Label every row of the urgency corpus (data/processed/urgency_tickets.csv, built by
   scripts/build_urgency_dataset.py) with the rules in app/ml/weak_labels.py.
2. Add every human-labelled ticket we have to the training data, weighted up by
   `human_weight` (scripts.ml_training.load_urgency_human: 234 written rows, plus
   reviewers' urgency corrections exported by scripts/export_feedback.py).
3. Features: TF-IDF word 1-2-grams + tone features + sentence embeddings (MiniLM), then
   logistic regression. That combination won on human labels for v3.
4. 5-fold cross-validation over the human tickets picks `human_weight` (0 means weak
   labels only, like v3). Each fold trains on the weak train split plus the other human
   folds and predicts the held-out human fold. The class weights are then tuned on the
   out-of-fold predictions: best macro-F1 among settings that keep high recall
   >= MIN_HIGH_RECALL, because a missed high ticket costs more than a false alarm.
5. The final model trains on the weak train split plus all human tickets.

Every human label is now used in training, so the cross-validated scores are the only
human-label numbers here, and slightly optimistic (the rules were revised while reading
these tickets). The real number comes from a new fresh set scored once with
scripts/evaluate_model.py.

Earlier procedures: v3 (weak labels only, dev-set selection) is at commit 6271db2.

Usage (from backend/):
    uv run python -m scripts.train_urgency_model --version v4
"""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline

from app.core.enums import ModelName, TicketUrgency
from app.ml.store import ModelBundle, load_bundle
from app.ml.text_features import SentenceEmbeddings, ToneFeatures, normalize_text
from app.ml.weak_labels import LABELING_FUNCTIONS, weak_label
from scripts.build_urgency_dataset import OUTPUT_PATH as URGENCY_DATASET_PATH
from scripts.ml_training import (
    SEED,
    URGENCY_FRESH_PATH,
    URGENCY_HOLDOUT_PATH,
    ensure_new_version,
    evaluate,
    feedback_metadata,
    file_sha256,
    load_splits,
    load_urgency_human,
    md_confidence,
    md_confusion,
    md_errors,
    md_per_class,
    md_summary,
    metadata,
    save_outputs,
    top_coefficients,
    tune_class_weights,
)

MODEL = ModelName.URGENCY_CLASSIFIER
CLASSES = [str(u) for u in TicketUrgency]
C = 2.0  # chosen on val for the same features in v3
HUMAN_WEIGHTS = (0, 3, 10, 30, 100)
# Missing a high ticket costs more than over-flagging one: class weights must keep high
# recall at or above this (cross-validated), then maximise macro-F1
MIN_HIGH_RECALL = 0.85
N_FOLDS = 5


def make_features() -> FeatureUnion:
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(preprocessor=normalize_text, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("tone", ToneFeatures()),
            ("emb", SentenceEmbeddings()),
        ]
    )


def fit(texts: list[str], labels: list[str], weights: np.ndarray) -> Pipeline:
    pipeline = Pipeline(
        [("features", make_features()), ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=5000))]
    )
    # Integer labels in CLASSES order, so predict_proba columns line up with CLASSES
    return pipeline.fit(texts, [CLASSES.index(label) for label in labels], clf__sample_weight=weights)


def training_rows(weak_texts, weak_labels, human_texts, human_labels, human_weight: float):
    """Weak rows at weight 1, human rows at `human_weight` (dropped when it is 0)."""
    if human_weight == 0:
        return list(weak_texts), list(weak_labels), np.ones(len(weak_texts))
    texts = [*weak_texts, *human_texts]
    labels = [*weak_labels, *human_labels]
    weights = np.concatenate([np.ones(len(weak_texts)), np.full(len(human_texts), float(human_weight))])
    return texts, labels, weights


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
    parser.add_argument("--dataset", type=Path, default=URGENCY_DATASET_PATH)
    parser.add_argument("--force", action="store_true", help="overwrite an existing version")
    args = parser.parse_args()
    out_dir = ensure_new_version(MODEL, args.version, args.force)

    splits = load_splits(args.dataset)
    for df in splits.values():
        df["urgency_weak"] = [str(weak_label(t).label) for t in df["text"]]
    weak_texts, weak_labels = splits["train"]["text"].tolist(), splits["train"]["urgency_weak"].tolist()
    human = load_urgency_human()
    h_texts, h_labels = human["text"].tolist(), human["urgency"].tolist()
    train_dist = Counter(weak_labels)
    print(f"Weak train rows: {len(weak_texts)} {dict(train_dist)}; human rows: {len(human)} {dict(Counter(h_labels))}")

    # --- cross-validation over the human tickets ---------------------------------------
    folds = list(StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED).split(h_texts, h_labels))
    oof = {w: np.zeros((len(human), len(CLASSES))) for w in HUMAN_WEIGHTS}
    for k, (tr, te) in enumerate(folds, 1):
        for w in HUMAN_WEIGHTS:
            texts, labels, weights = training_rows(
                weak_texts, weak_labels, [h_texts[i] for i in tr], [h_labels[i] for i in tr], w
            )
            oof[w][te] = fit(texts, labels, weights).predict_proba([h_texts[i] for i in te])
        print(f"  fold {k}/{N_FOLDS} done")

    cv_results, cv_f1 = {}, {}
    for w in HUMAN_WEIGHTS:
        result = evaluate(h_labels, [CLASSES[i] for i in oof[w].argmax(axis=1)], CLASSES, oof[w].max(axis=1))
        cv_results[f"human weight {w}" + (" (weak labels only)" if w == 0 else "")] = {"human CV": result}
        cv_f1[w] = result["macro_f1"]
        print(f"  human weight {w}: CV macro-F1 {cv_f1[w]:.3f}")
    best_w = max(HUMAN_WEIGHTS, key=cv_f1.get)
    class_weights, _ = tune_class_weights(oof[best_w], h_labels, CLASSES, min_last_recall=MIN_HIGH_RECALL)
    weighted_scores = oof[best_w] * np.asarray(class_weights)
    cv_pred = [CLASSES[i] for i in weighted_scores.argmax(axis=1)]
    cv_conf = oof[best_w][np.arange(len(human)), weighted_scores.argmax(axis=1)]
    shipped = f"human weight {best_w} + class weights"
    cv_results[shipped] = {"human CV": evaluate(h_labels, cv_pred, CLASSES, cv_conf)}
    print(f"Chose human weight {best_w}, class weights {class_weights}")

    # Context: the previous model and the rules on the same tickets (not a fair test for v3:
    # 170 of these tuned it and the other 64 chose it)
    v3 = load_bundle(MODEL, "v3")
    v3_pred, v3_conf = v3.predict_many(h_texts)
    context = {
        "v3 (served before)": evaluate(h_labels, v3_pred, CLASSES, v3_conf),
        "rules alone": evaluate(h_labels, [str(weak_label(t).label) for t in h_texts], CLASSES),
    }

    # --- final model: weak train + all human tickets -----------------------------------
    texts, labels, weights = training_rows(weak_texts, weak_labels, h_texts, h_labels, best_w)
    final = fit(texts, labels, weights)
    bundle = ModelBundle(final, CLASSES, args.version, class_weights=class_weights)
    weak_eval = {}
    for name in ("val", "test"):
        y_pred, conf = bundle.predict_many(splits[name]["text"].tolist())
        weak_eval[f"{name} (weak)"] = evaluate(splits[name]["urgency_weak"].tolist(), y_pred, CLASSES, conf)

    best = cv_results[shipped]["human CV"]
    report = f"""# Urgency classifier {args.version}

Weak supervision **plus human labels**: the rules (`app/ml/weak_labels.py`) label the
{len(weak_texts)}-row train split of `{args.dataset.name}`, and all {len(human)} human-labelled
tickets are added with weight ×{best_w}. Features: TF-IDF word 1-2-grams + tone features +
MiniLM sentence embeddings → logistic regression (C={C}, balanced classes).
Class weights: {", ".join(f"{c} ×{w}" for c, w in zip(CLASSES, class_weights, strict=True))}, tuned for the best
macro-F1 that keeps cross-validated high recall ≥ {MIN_HIGH_RECALL}.

Weak label distribution (train): {", ".join(f"{c} {train_dist[c]} ({train_dist[c] / len(weak_texts):.0%})" for c in CLASSES)}.
Human tickets: {", ".join(f"{c} {n}" for c, n in Counter(h_labels).items())}.

## Human-label cross-validation ({N_FOLDS}-fold)

Each human ticket is predicted by a model that never saw it. Human weight 0 = weak labels
only (the v3 recipe, on the v4 corpus and rules).

{md_summary(cv_results)}

Context on the same {len(human)} tickets (**not** a fair test: v3 was tuned on 170 of them and
chosen on the other 64):

{md_summary({k: {"human": v} for k, v in context.items()})}

**Caveats:** the rules were revised while reading these tickets, and the class weights
were tuned on the same out-of-fold predictions, so the CV numbers are somewhat optimistic.
The real number comes from a new fresh set scored once with `scripts/evaluate_model.py`.

## Shipped recipe — cross-validated per class

{md_per_class(best)}

{md_confusion(best, CLASSES)}

### Tickets it got wrong (out-of-fold)

{md_errors(h_texts, h_labels, cv_pred, cv_conf, limit=40)}

## Confidence vs. the 0.6 escalation threshold

{md_confidence({"human CV": best, **{k: v for k, v in weak_eval.items() if k.startswith("test")}})}

## Final model vs weak labels (held-out corpus splits)

{md_summary({"final model": weak_eval})}

## Labeling functions

`calm_language` cancels `time_pressure` and sentiment votes. Then: HIGH if any strong
HIGH rule fires, two weak HIGH rules fire, or a weak HIGH rule fires together with a
MEDIUM rule; MEDIUM if one weak HIGH or any MEDIUM rule fires; otherwise LOW.

{md_lf_coverage(weak_texts)}

## Features pushing hardest towards each class

{chr(10).join(f"- **{c}**: " + ", ".join(f"`{f}`" for f in feats) for c, feats in top_coefficients(final, CLASSES).items())}
"""
    metrics = {
        "model": str(MODEL),
        "version": args.version,
        "classes": CLASSES,
        "C": C,
        "human_weight": best_w,
        "class_weights": dict(zip(CLASSES, class_weights, strict=True)),
        "min_high_recall": MIN_HIGH_RECALL,
        "cv_results": cv_results,
        "context_on_human_tickets": context,
        "weak_eval": weak_eval,
        "weak_label_distribution_train": dict(train_dist),
        "metadata": metadata(
            args.dataset,
            {
                "n_weak_train": len(weak_texts),
                "n_human": len(human),
                "holdout_sha256": file_sha256(URGENCY_HOLDOUT_PATH),
                "fresh_v3_sha256": file_sha256(URGENCY_FRESH_PATH),
                # Reviewer corrections are part of `human` (source "feedback")
                "feedback": feedback_metadata("urgency"),
            },
        ),
    }
    save_outputs(out_dir, MODEL, bundle, metrics, report)

    print(md_summary(cv_results))
    print(md_summary({k: {"human": v} for k, v in context.items()}))
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
