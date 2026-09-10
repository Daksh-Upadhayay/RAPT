# ML Models

This project trains real models rather than relying purely on LLM prompting for
classification. Both models below are used as **tools** the Triage Agent calls —
the LLM does not guess category/urgency itself.

## Model 1: Category Classifier
- **Task:** multi-class classification of ticket text into one of:
  `order_status`, `refund_request`, `damaged_item`, `delivery_delay`,
  `product_question`, `cancellation`
- **Data:** start from a public support-ticket dataset, relabel/filter down to these
  6 categories. If the public dataset's categories don't map cleanly, supplement with
  a small hand-labeled set (50-100 examples) written to match the e-commerce wedge.
  - **As built (Phase 2):** the Kaggle "Customer Support Ticket Dataset" was dropped
    because its labels turned out to be random. The data is Bitext (3 categories) plus
    templates (all 6), with a separate 120-ticket hand-written test set. See
    `DECISIONS.md` (Phase 2) and `data/README.md`.
- **Baseline approach:** TF-IDF vectorization + XGBoost (or Logistic Regression)
  — fast to train, easy to explain, easy to iterate on.
- **Stretch approach (optional, only if time allows):** fine-tune DistilBERT —
  stronger resume line, but budget extra time for setup (tokenization, training
  loop, GPU/Colab if no local GPU).
- **Evaluation:** train/val/test split (70/15/15), report precision/recall/F1
  per class (not just overall accuracy — class imbalance is likely), confusion
  matrix.
- **Output:** saved model artifact (`.pkl` for sklearn/XGBoost, or HF model dir
  if fine-tuned) + a small inference wrapper function `predict_category(text) ->
  (label, confidence)`.

## Model 2: Urgency / Escalation-Risk Classifier
- **Task:** classify urgency as `low`, `medium`, `high`
- **Data:** same dataset if it has priority/urgency labels; otherwise derive
  weak labels heuristically first (e.g., keyword rules: "urgent", "refund now",
  "terrible", ALL CAPS, exclamation density) to bootstrap a training set, then
  train a proper classifier on top of that. This bootstrapping approach is worth
  documenting — it's a realistic real-world ML workflow (weak supervision).
- **Features:** ticket text (TF-IDF or embeddings) + optionally sentiment score
  as an extra feature (use a pretrained sentiment model like VADER or a small
  HF sentiment pipeline to generate this feature, not as the final urgency call).
- **Baseline approach:** same as category — TF-IDF/embeddings + XGBoost or
  Logistic Regression.
- **Evaluation:** same as category classifier.

## Embeddings (for RAG, not classification)
- **Purpose:** embed `knowledge_base.content` for semantic search, and embed
  incoming ticket text for retrieval matching.
- **Model choice:** use a sentence-transformers model (e.g.
  `all-MiniLM-L6-v2`, 384 dimensions) for a fast, free, local option — OR an
  OpenAI/Anthropic embedding endpoint if API-based embeddings are preferred.
  **Decide this before creating the Postgres `vector` column dimension** (see
  `01-database-schema.md`).
- **Note:** embeddings are a separate concern from the two classifiers above —
  don't conflate "the model that classifies tickets" with "the model that
  embeds text for search." They're different models doing different jobs.

## Model versioning
- Track model version strings (`v1`, `v2`, ...) and store them alongside
  predictions in `model_predictions.model_version`.
- Optional but a nice resume line: log training runs with MLflow (params,
  metrics, artifact path) so there's a real "experiment tracking" story to tell.

## Feedback loop (build this in Phase 6, but design for it now)
- When a human reviewer edits/rejects an AI draft, that signal should
  eventually be usable to improve the classifiers (e.g., if a ticket was
  mis-categorized and the reviewer corrects it, that correction is a new
  labeled example for retraining). Don't over-build this — a documented plan
  and a basic "corrected_category" field is enough for a resume project; a full
  automated retraining pipeline is not required.

## What NOT to do
- Don't let the LLM itself decide category/urgency by "just asking it nicely" —
  the entire point of this project is showing you trained and evaluated real
  models. The LLM's job is knowledge retrieval and drafting, not classification.
- Don't skip the evaluation step — a model without train/test metrics is not
  credible in an interview.
