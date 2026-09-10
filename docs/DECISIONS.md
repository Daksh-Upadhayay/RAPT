# Decisions Log

Deliberate choices made while building, especially where the build deviates
from or fills gaps in the spec docs. Newest phase at the bottom.

---

## Phase 0 — Environment

### uv for Python dependency management
- **Decision:** `uv` manages the backend (`backend/pyproject.toml` + `backend/uv.lock`),
  not pip/venv/poetry. There is no `requirements.txt` (04-backend-api.md updated).
- **Why:** one tool for Python version, venv, and locking; fast, reproducible
  installs via the committed lockfile.

### Python 3.12
- **Decision:** pinned in `backend/.python-version`.
- **Why:** the most dependable wheel coverage across the ML/async stack
  (xgboost, scikit-learn, asyncpg, pandas) at the time of setup; 3.14 was
  available but newer than needed.

### Monorepo layout
- **Decision:** `backend/` (uv project) and, later, `frontend/` side by side, with
  `docs/` and `data/` at the root and a single root `.gitignore`.

---

## Phase 1 — Schema + FastAPI skeleton

### Escalation is a flag, not a status
- **Decision:** added `tickets.needs_escalation` (BOOLEAN) and
  `tickets.escalation_reason` (TEXT); removed `escalated` from `tickets.status`.
  Allowed statuses: `new`, `in_progress`, `awaiting_review`, `resolved`.
- **Why:** 03-agent-architecture.md says human review is always on and
  "escalation" only means higher-priority attention. With `escalated` as a
  status, escalated tickets would have dropped out of the review queue
  (`status = awaiting_review`), and the original schema had no column to
  persist the escalation decision the review queue and metrics need.
  Escalated tickets stay `awaiting_review` and are distinguished by the flag.
- **Nullability:** `needs_escalation` is null until the Escalation Agent runs,
  consistent with `category`/`urgency` being null until triage.

### `knowledge_base` deferred to Phase 3
- **Decision:** the Phase 1 migration does not create `knowledge_base` or the
  `vector` extension; both come in a Phase 3 migration.
- **Why:** the vector column's dimension depends on the embedding model
  (01 says 1536, which is OpenAI-sized; 02 suggests `all-MiniLM-L6-v2` at 384).
  Creating it now would mean guessing and migrating again later.
- **Note for Phase 3:** Anthropic has no embeddings endpoint (it points to
  Voyage AI); a local model means adding `sentence-transformers` (pulls in
  PyTorch). The Homebrew Postgres also needs `brew install pgvector`.

### Only the endpoints in 04-backend-api.md
- **Decision:** Phase 1 implements exactly `POST /tickets`, `GET /tickets`
  (filters: `status`, `category`, `urgency`), `GET /tickets/{id}`, and
  `GET /orders/{id}`. No update/delete endpoints; orders are read-only seeded
  data. The hello-world route used to verify the environment was removed.

### Enum-like columns: TEXT + CHECK constraints
- **Decision:** status/category/urgency/agent_name/model_name are `TEXT` columns
  with named CHECK constraints (e.g. `ck_tickets_status_valid`), not native
  Postgres ENUM types. Allowed values live once in `app/core/enums.py`
  (`StrEnum`s) and are used for both the CHECK constraints and the Pydantic
  schemas, so the API rejects bad values with a 422 before they reach the DB.
- **Why:** adding/removing a value on a native ENUM is awkward in Alembic
  (`ALTER TYPE`, can't remove values); a CHECK constraint is a simple
  drop/recreate. Validation still happens at both layers.

### UUIDs generated in the database
- **Decision:** primary keys use `server_default=gen_random_uuid()` (built into
  Postgres 13+, no extension needed).
- **Why:** every insert path (API, seed scripts, raw SQL) gets a valid id without
  relying on app code.

### Constraint naming convention
- **Decision:** SQLAlchemy `MetaData(naming_convention=...)` gives every PK, FK,
  unique, index, and CHECK constraint a deterministic name.
- **Why:** Alembic can only reliably drop/alter constraints it can name;
  unnamed ones get Postgres-generated names that differ between databases.

### Indexes on foreign keys and `tickets.status`
- **Decision:** indexed every FK column plus `tickets.status`.
- **Why:** Postgres doesn't index FK columns automatically; ticket detail and
  agent trace look up children by `ticket_id`, and the review queue filters by
  status.

### `updated_at` maintained by the ORM
- **Decision:** `server_default=now()` on insert, `onupdate=now()` on ORM updates.
- **Trade-off:** raw SQL updates won't bump it (no DB trigger). Fine while all
  writes go through the app; revisit if seed/admin scripts start updating rows.

### Money is `Decimal` end to end
- **Decision:** `orders.amount` is `NUMERIC(10,2)` → `Decimal` in Python → a JSON
  string in API responses (e.g. `"149.99"`), which is Pydantic's default for
  `Decimal`.
- **Why:** avoids float rounding on money. The frontend types `amount` as a
  string and formats it for display.
- **Open question for Phase 4:** 03-agent-architecture.md types
  `OrderLookupResult.amount` as `float`; decide whether to keep `Decimal` there
  for the refund-threshold comparison.

### Ticket creation validates references
- **Decision:** `POST /tickets` returns 422 if the customer or order doesn't
  exist, or if the order belongs to a different customer.
- **Why:** surfaces a clear error instead of a raw FK violation (500), and
  prevents a ticket from being linked to another customer's order — which
  would leak that order's data into the Order Lookup step and the draft.

### Service layer between routers and models
- **Decision:** DB logic lives in `app/services/` (`tickets.py`, `orders.py`);
  routers only translate HTTP ↔ service calls.
- **Why:** per 04-backend-api.md; Phase 4's "create ticket → trigger agent
  graph" wiring belongs in the service, not the router.

### Relationships use `lazy="raise"`
- **Decision:** ORM relationships raise if accessed without being loaded;
  queries load them explicitly (`selectinload`).
- **Why:** implicit lazy loading doesn't work under async SQLAlchemy — it fails
  with an obscure `MissingGreenlet` error. `lazy="raise"` fails immediately with
  a clear message instead.

### `sqlalchemy[asyncio]` extra
- **Decision:** the dependency is `sqlalchemy[asyncio]`, not plain `sqlalchemy`.
- **Why:** the async engine requires `greenlet`, which is only pulled in via
  that extra.

### Tests run against real Postgres
- **Decision:** pytest uses a separate `rapt_test` database. Each test session
  drops the schema and rebuilds it with `alembic upgrade head`; tables are
  truncated between tests. `pytest-asyncio` (dev dependency) drives async tests
  with `httpx.AsyncClient` + `ASGITransport`.
- **Why:** SQLite can't stand in for JSONB, UUID, CHECK behaviour, or (later)
  pgvector. Building the test schema from the real migrations also verifies
  that migrations run cleanly from scratch, and a dedicated test checks the
  downgrade → upgrade round trip.

---

## Phase 2 — Seed data + ML models

### Seed data is internally consistent
- **Decision:** `scripts/seed_orders.py` generates dates relative to today and keeps each
  order's status consistent with them: `processing` has no tracking number and a future
  delivery date, `delayed` is past its expected date, `cancelled` has no delivery date.
  About 38% of orders are over $100, so the refund escalation rule gets exercised.
  The script refuses to run on a non-empty database unless given `--reset`.
- **Why:** the Order Lookup and Draft agents quote this data back to customers. An order
  marked `delayed` with a future delivery date would produce nonsense drafts.

### Kaggle dataset dropped: its labels are random
- **Finding:** on the Kaggle "Customer Support Ticket Dataset", TF-IDF + logistic
  regression scored 33.7% accuracy on its 3 usable ticket types (chance is 33.4%), and
  worse than chance on its priority labels. The texts are templated
  ("I'm having an issue with the {product_purchased}") and the labels were assigned
  independently of them. A classifier trained on it can't learn anything.
- **Decision:** category data = Bitext customer-support dataset (real-ish phrasing, typos,
  slang; CDLA-Sharing-1.0) for `order_status`, `refund_request`, `cancellation`, plus
  templates for all six categories (`scripts/ticket_templates.py`). Bitext has nothing for
  `damaged_item`, `delivery_delay` or `product_question`, so those are 100% templates.
- **Style shortcut guard:** templates are also mixed into the Bitext classes, and some
  templates get typo/lowercase noise. Otherwise "short, messy text" would itself predict
  the three Bitext classes.
- **Grouped split:** all variants of one template sentence or Bitext skeleton stay in one
  split, so the test split measures unseen phrasings, not near-copies of training rows.

### A hand-written test set is the headline metric
- **Decision:** `data/eval/handwritten_test_set.csv` has 120 realistic tickets (20 per
  category) with human category and urgency labels. It is never used for training, model
  selection or rule tuning. Labelling guidelines are in `data/README.md`.
- **Why:** template data scores ~98% whatever the model does, because the test split
  shares its vocabulary with training. Only independently written text shows what to
  expect on real tickets.
- **Caveat:** the same person (Claude) wrote the templates and the test set, so the two
  are not fully independent. Tickets from real users (Phase 6 corrections) are the real test.
- **Rule:** don't edit templates, rules or model settings because of specific hand-written
  errors. That turns the test set into a training set and the headline number stops
  meaning anything. Fixes should come from training data analysis, or from a separate
  dev set.

### Urgency: weak supervision with labelling functions
- **Decision:** `app/ml/weak_labels.py` has 13 keyword/heuristic rules. Each votes `high` or
  `medium` when it fires, and a fixed priority scheme combines the votes (see the module
  docstring). Every training row is labelled by the rules, then XGBoost trains on
  TF-IDF + tone features.
- **Tone features:** VADER sentiment (as a feature, not the decision, per
  02-ml-models.md), ALL-CAPS ratio, `!`/`?` counts and length. TF-IDF lowercases and drops
  punctuation, so without these the model can't see shouting.
- **Tone sentences:** Bitext and template text barely varies in urgency, so a
  category-agnostic tone sentence (calm → angry) is appended to some tickets. Some tone
  sentences deliberately avoid the rules' keywords, so the weak labels are noisy the way
  they would be on real text.

### Model artifacts are versioned directories committed to git
- **Decision:** `app/ml/artifacts/<model_name>/<version>/` holds `model.joblib` (pipeline +
  class labels), `metrics.json` (all numbers, params, dataset hash, library versions)
  and `report.md`. `settings.category_model_version` / `urgency_model_version` choose the
  one to serve. Training refuses to overwrite an existing version without `--force`.
- **Why:** `model_predictions.model_version` must point at an artifact that still exists.
  At 1-2 MB each the artifacts are small enough to commit, so the app runs without a
  training step. Joblib files are pickles tied to the sklearn/xgboost versions in
  `uv.lock`, so retrain after upgrading either.
- **MLflow:** skipped for now (optional in 02-ml-models.md). `metrics.json` holds what a
  run log would.

### Inference returns the agent tool schemas
- **Decision:** `predict_category(text)` / `predict_urgency(text)` return
  `CategoryPrediction` / `UrgencyPrediction` (`label`, `confidence`, `model_version`) from
  `app/schemas/prediction.py`. These match 03-agent-architecture.md and carry the
  `(label, confidence)` pair from 02-ml-models.md. Confidence is the top class probability.
  Models load once per process (cached, ~1 s cold, ~8 ms per prediction after that).

### Urgency v1 → v2: the model was worse than its own rules
- **Finding (v1):** on the hand-written set, the rules alone scored macro-F1 0.68 and the
  XGBoost model trained on their labels scored 0.52. The training text's urgency came
  from ~45 fixed tone sentences and the `safety` rule fired on 0% of it, so the model
  memorised those sentences instead of learning urgency.
- **Change (v2), data only, rules untouched:** `scripts/urgency_phrases.py` builds urgency
  phrasing from slot-filled pieces across 11 kinds (deadline, repeat contact, threat,
  safety, anger, money, impact, frustration, inconvenience, action request, calm).
  Urgent tickets carry 2-3 signals, mixing phrasings the rules catch with ones they
  don't, so the model can learn from what appears next to a rule-caught phrase.
  Corpus: `data/processed/urgency_tickets.csv` (10,273 rows, `scripts/build_urgency_dataset.py`).
  The category dataset is unchanged and still reproduces byte-for-byte.
- **Model family is chosen on val:** on v2, XGBoost matched the rules' labels worse than
  logistic regression on the val split (macro-F1 0.82 vs 0.88). The script now trains both
  and ships the val winner, and for v2 that is **logistic regression** (C=32). Linear
  models fit "add up the evidence" keyword signals better than trees on sparse TF-IDF.
  Category v1 stays XGBoost, which won its val comparison. Switching it needs a separate
  dev set.
- **Result:** hand-written set macro-F1 is v1 0.52, v2 0.63, rules 0.68. That set informed
  the redesign, so this number is not clean.
- **Clean check:** the owner's holdout set (now `data/eval/urgency_holdout_test.csv`), never seen
  during development, scored once with `scripts/evaluate_model.py` against v1, v2 and the
  rules. v2 is frozen and served now (`urgency_model_version = "v2"`). If the rules
  still beat it on the fresh set, the next step is a hybrid (rules for `high`, model
  otherwise), not more tuning against that set.

### Urgency v2 confirmed on the owner's holdout set
- **Eval set:** `urgency_holdout_test.csv`, 50 tickets (16 low / 17 medium / 17 high)
  written by the project owner. It was not opened before scoring, and v1, v2 and the rules
  were scored once (`app/ml/artifacts/urgency_classifier/eval_urgency_holdout_test.md`).
- **Result (macro-F1 / accuracy):** v1 0.47 / 0.50, **v2 0.61 / 0.62**, rules alone 0.52 / 0.54.
  On clean data the weak-supervised model beats the rules it was trained on, which is
  the point of weak supervision. Under the rule agreed before scoring, v2 stays served
  and no hybrid is needed.
- **Where v2 is weak:**
  - **Medium tickets look low to it** (recall 0.35; 11 of 17 predicted low).
  - **High tickets are sometimes missed** (recall 0.59), although every ticket it
    predicts high really is high (precision 1.00).
  - **Confidence is a useful signal.** The 12% of tickets below 0.6 confidence are
    right only 17% of the time, so the Escalation Agent's low-confidence rule catches
    some of the misses.
- **Caveat:** with 50 tickets each score is roughly ±0.13, so "v2 beats rules" is likely
  but not proven.
- **This set is now used up for decisions:** it chose v2 over the rules. Future urgency
  versions need a new unseen set (e.g. reviewer-corrected tickets from Phase 6).

### Urgency v3: revised rules, embeddings, dev-set selection (pending fresh test)
- **Dev set:** the 120 hand-written + 50 holdout tickets (170, human-labelled) became
  the urgency dev set. Both were already spent as tests, and 170 tickets are much
  steadier than 50 (about ±0.07 vs ±0.13). All v3 choices were made on it.
- **Rules revised on the dev set:**
  - **Medium coverage.** New MEDIUM rules: `stalled`, `billing_issue`, `action_request`,
    and wider problem wording.
  - **High coverage.** New strong `hardship` rule (rent, medication, disability…) and
    weak `patience_lost` rule. Manager/escalation requests now count as a threat, and
    "need … today/tomorrow" as time pressure.
  - **False highs.** A LOW `calm_language` rule cancels the false `time_pressure` and
    sentiment votes on hedged wording ("nothing urgent", "no big deal").
  - **Effect.** Rules went from ~0.60 to 0.91 macro-F1 on dev. That number is inflated,
    because the rules were written while reading these tickets. v1 and v2 were trained on
    the earlier rules.
- **Sentence embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-d, local, free)
  embeddings are added as features next to TF-IDF + tone. This also settles the Phase 3
  RAG embedding model unless Phase 3 finds a reason to change it, so the
  `knowledge_base.embedding` column would be `VECTOR(384)`. It adds PyTorch to the
  backend. Weights load from the local Hugging Face cache (first run downloads them).
  Cold start is ~7 s (importing torch) and a prediction takes ~150 ms, which is fine
  for the background agent run.
- **Candidates:**
  - Four were trained: {TF-IDF + tone, + embeddings} × {LogReg, XGBoost}, with each
    family's hyperparameters tuned on the weak val split and the winner picked on dev.
  - Dev macro-F1: LogReg 0.71, XGBoost 0.60, LogReg + embeddings 0.75, XGBoost +
    embeddings 0.61. XGBoost lost on human labels in every comparison. It fits the
    rules' labels better (weak val 0.92), but generalises worse.
- **Class weights:** the probabilities are multiplied by low ×1.0, medium ×1.25,
  high ×3.0 before the label is picked, tuned on dev for macro-F1 with ties going to
  higher `high` recall. This reaches 0.78 dev macro-F1. Confidence is still the model's
  own probability for the chosen label, so a label that wins only because of its weight
  reports low confidence, and the Escalation Agent's < 0.6 rule sees it.
- **Status:** v3 was frozen before the fresh set was opened. The agreed rule: switch
  from v2 only if v3 beats it on a fresh owner-written set scored once.

### Urgency v3 confirmed on a fresh set, now served
- **Eval set:** `data/eval/urgency_fresh_test.csv`, 64 tickets (17 low / 30 medium /
  17 high) written by the project owner after v3 was frozen. There is no overlap with the
  dev set or the training corpus. The first version had no low tickets, which would have
  favoured v3's weights; 17 lows were added before any scoring. Scored once:
  `app/ml/artifacts/urgency_classifier/eval_urgency_fresh_test.md`.
- **Result (macro-F1 / accuracy):** v2 0.41 / 0.47, **v3 0.68 / 0.70**, rules alone
  (v3 rules) 0.61 / 0.62. v3 beats v2 by a wide margin, so it is now served
  (`URGENCY_MODEL_VERSION=v3`). It also beats the rules it learned from, as on the
  earlier holdout.
- **Per class (v3):**
  - **Medium is fixed:** recall 0.73, up from v2's 0.40.
  - **The weights don't cause false alarms:** 15 of 17 low tickets stay low and none
    become high.
  - **High is still the weak spot:** recall 0.47 (8 of 17), and 4 high tickets are
    predicted low.
  - **Confidence is a weaker signal than hoped:** 22% of tickets are below 0.6, and they
    are 57% accurate vs 74% above it.
- **Caveat:** 64 tickets → each score is roughly ±0.11. The v2 → v3 gap (0.27) is well
  outside that; v3 vs rules (0.07) is not.
- **Next:** missed high tickets are the main risk, since escalation depends on them.
  The next improvement should target high recall, measured on reviewer-corrected
  tickets from Phase 6. This fresh set is now spent for decisions.
