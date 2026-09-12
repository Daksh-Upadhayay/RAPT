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

### Urgency v4: calm high-stakes data + human labels in training (pending fresh test)
- **Problem:** all 9 high tickets v3 missed on the fresh set were written calmly. Their
  urgency came from the situation: fraud, subtle safety risks, a calm deadline plus a
  problem, lost money, a medical need. v3 gave them only a 3–19% chance of being high,
  because every high training example got its urgency from tone. It had learned
  "angry means high".
- **Data:** a new "stakes" level in `scripts/urgency_phrases.py` (12% of tickets) states
  one serious situation in a neutral voice, with no anger and no "!". There are six
  kinds: calm deadline, fraud/privacy, subtle safety, money lost, essential need, blocked
  access.
- **Rules:** new strong rules `fraud_or_privacy` and `money_lost`. `safety` now covers
  subtle hazards (warm to the touch, allergens, frayed, recall, latches), `time_pressure`
  covers an event on a near date ("flight tomorrow"), and `hardship` covers hearing aids.
  About 90% of stakes phrases are caught; the rest are deliberate label noise.
- **Human labels in training:** all 234 human-labelled tickets (dev 170 + fresh 64) are
  added to the weak-labelled corpus. Their weight is chosen by 5-fold cross-validation
  over the human tickets: each ticket is predicted by a model that never saw it. The
  features are the v3 winners (TF-IDF + tone + MiniLM embeddings → LogReg, C=2).
- **Class weights with a high-recall floor:** tuning purely for macro-F1 set high to
  ×0.6 and cut high recall to 0.76. Now the weights must keep cross-validated high
  recall ≥ 0.85, and macro-F1 is maximised within that (`MIN_HIGH_RECALL`), because a
  missed high ticket costs more than a false alarm.
- **Cross-validated result:**
  - **Chosen setting:** human weight ×100 (at that weight the human labels dominate),
    class weights low 1.0 / medium 0.8 / high 1.0.
  - **Scores:** macro-F1 **0.80**; high recall **0.88** (59/67, only 3 high → low) at
    precision 0.76. Weak labels alone: 0.73 with high recall 0.90 but precision 0.63.
  - **Confidence:** 84% accurate at ≥ 0.6 vs 56% below.
- **Caveats:**
  - **Optimistic numbers.** The rules were revised while reading these tickets, and the
    class weights were tuned on the same out-of-fold predictions.
  - **Weight at the edge.** Human weight ×100 was the top of the tested grid and the
    trend was still rising, but the 0.80 vs 0.78 gap is within CV noise (±~0.05 on 234
    tickets).
  - **Unfair context numbers.** v3 (0.76) and the rules (0.86) on the same tickets are
    not fair comparisons.
- **Status:** v4 is frozen and **served** (`URGENCY_MODEL_VERSION=v4`). The project owner
  chose to switch before a fresh test, on the strength of the cross-validated results.
  The planned fresh high-heavy set is still the confirmation step: score v3 and v4 on it
  once, and roll back to v3 if v4 does worse, above all on high recall.

### Urgency v4 confirmed on a blind high-heavy set
- **Eval set:** `data/eval/urgency_blind_eval_v2.csv`, 55 tickets (15 low / 15 medium /
  25 high) written by the project owner after v4 was frozen, avoiding the situations
  seen in earlier sets. There is no overlap with any training data. Scored once:
  `app/ml/artifacts/urgency_classifier/eval_urgency_blind_eval_v2.md`.
- **Result (macro-F1 / accuracy):** v3 0.63 / 0.64, **v4 0.76 / 0.80**, rules alone
  0.53 / 0.56. The switch to v4 holds.
- **High tickets, the goal of v4:** recall **0.92** (23/25, one called low) vs v3's 0.52
  (13/25), with precision still 0.85. Calm but serious tickets are now caught.
- **Confidence is now a strong signal:** 88% accurate at ≥ 0.6 vs 29% below, with 13% of
  tickets below. The Escalation Agent's < 0.6 rule will catch most remaining errors.
- **New weak spot: medium** (recall 0.47): 5 of 15 medium tickets were called low and 3
  high. This matters less than missed highs (every draft is human-reviewed anyway), but
  it is the next thing to improve, with reviewer corrections from Phase 6.
- **Caveat:** 55 tickets → each score is roughly ±0.12; the v3 → v4 gain on high recall
  (0.52 → 0.92) is far outside that. This set is now spent for decisions.

---

## Phase 3 — Knowledge base + pgvector search

### Embedding model: all-MiniLM-L6-v2, 384 dimensions
- **Decision:** `sentence-transformers/all-MiniLM-L6-v2` (`settings.embedding_model`),
  so `knowledge_base.embedding` is `VECTOR(384)`. `EMBEDDING_DIM` in `app/core/config.py`
  and the migration pin the size, and `embed_texts` raises if a configured model
  produces a different size.
- **Why:** it's free, runs locally, and needs no API key (Anthropic has no embeddings
  endpoint). It is already loaded for urgency v4's features, so one copy serves both, and
  it's plenty for a few dozen short policy entries. An API model (e.g. Voyage) would
  need a new migration and a re-embed.
- **Superseded in Phase 4:** knowledge search now uses `BAAI/bge-small-en-v1.5` (also
  384-d); see "Knowledge search: bge-small replaces MiniLM" under Phase 4.

### Entries must fit in the model's 256-token window
- **Decision:** `embed_document` rejects entries longer than the model reads: the API
  returns 422 and the seed script refuses to run. Queries (ticket text) are truncated
  instead.
- **Why:** MiniLM silently ignores everything after 256 tokens, so a long entry's
  later paragraphs would be unsearchable without anyone noticing. Entries are short
  single-topic policies instead of chunked documents; if long documents are ever
  needed, chunking belongs in the seed step.
- **Since Phase 4:** the limit is 512 tokens, bge-small's window. The rule is unchanged.

### Cosine distance with an HNSW index, vectors stored normalised
- **Decision:** search orders by pgvector's cosine distance (`<=>`) and returns
  `similarity = 1 - distance`. There is an HNSW index with `vector_cosine_ops`.
- **Why:** for unit-length vectors cosine is the standard sentence-transformers metric.
  At 27 rows Postgres scans anyway; the index is there so search stays fast as the
  knowledge base grows. HNSW is approximate, which is irrelevant at this size.

### No codec registration for asyncpg
- **Finding:** pgvector's SQLAlchemy type sends and receives vectors as text, so asyncpg
  needs no `register_vector` hook. Vectors go in as numpy arrays and come back as
  `list[float]` (pgvector 0.5).

### Knowledge-base content
- **Decision:** 27 entries in `data/knowledge_base.json` (written in Phase 3), each
  tagged with the ticket categories it answers. They cover order statuses, dispatch and
  shipping times, tracking, delays, lost and customs parcels, address changes, damaged,
  wrong and missing items, safety and recalls, warranty, returns, refund timing, the
  $100 refund review (matching the Escalation Agent's threshold), duplicate charges,
  price drops and promo codes, cancellation (full, partial, pre-order), unauthorised
  charges, account access, product information, stock, setup/manuals/spare parts, and
  support response times.
- **Consistency:** the numbers match the rest of the system: order statuses as seeded,
  1-2 day dispatch, the 7-business-day lost-parcel rule, the $100 review.

### Only the two endpoints in 04-backend-api.md
- **Decision:** `GET /knowledge-base` and `POST /knowledge-base` (embeds on create). Search
  is a service function (`app.services.knowledge_base.search`) for the Knowledge Agent,
  plus a CLI (`scripts/search_knowledge_base.py`). There is no search endpoint, since the
  spec lists none.

### Retrieval check
- **Method:** `scripts/evaluate_retrieval.py` runs the 120 hand-written tickets as queries.
  A hit means an entry tagged with the ticket's category comes back.
- **Result:** hit@3 **0.97**, hit@1 0.82, MRR 0.89. Weakest are product questions (hit@1
  0.65) and delivery delays (hit@3 0.90).
- **Caveat:** the setup/manuals/spare-parts entry was added after the first run
  showed product-specific questions had no matching entry (hit@3 went 0.93 → 0.97), and
  the same author wrote the tickets and the entries. It's a sanity check, not a
  benchmark.
- **Known weakness:** strongly worded tickets ("10 days late, I want this escalated")
  can pull up general support entries ahead of the delay policy.
- **Revisited in Phase 4:** the category-level hit hid a weak delay-policy entry. The
  model change and a reworded entry fixed it (hit@3 1.00, no misses); see Phase 4.

### Open question from Phase 1, resolved: `OrderLookupResult.amount` is a float
- **Decision:** the tool schema follows the spec (`float`); the database and `GET /orders`
  keep exact `Decimal`. The only calculation is a comparison with the $100 refund
  threshold, where float precision doesn't matter.

---

## Phase 4 — LangGraph agent pipeline

### Graph exactly as specified, dependencies via LangGraph's runtime context
- **Decision:** `app/agents/graph.py` wires triage → knowledge → [order linked?] →
  order_lookup → draft → escalation. Nodes get the DB session and the drafter through
  LangGraph's `context_schema` (`AgentContext`), not globals, so tests inject a test
  database and a fake LLM.
- **Logging:** the `@logged` wrapper writes one `agent_logs` row per node: input (the
  state fields it reads, or the full prompt for the draft), output, tool calls, and
  duration. A failing node still logs, with an `error` output.
- **Commit per node:** each node's writes land together with its log, and the trace
  fills in live. It also keeps `created_at` (Postgres `now()` is per transaction)
  distinct per step, so trace order is reliable.
- **Pitfall found:** `functools.wraps` on the node wrapper made LangGraph read the inner
  function's signature and stop passing `runtime`, so every node crashed. The wrapper
  copies only `__name__`/`__doc__`.

### Background runs; failures still reach a human
- **Decision:** `POST /tickets` saves the ticket (`new`) and returns 201; the graph
  runs as a FastAPI `BackgroundTask` with its own session (the request's session is
  closed by then). Status goes `new` → `in_progress` → `awaiting_review`.
- **Failure path:** if any node fails, the ticket still moves to `awaiting_review` with
  `needs_escalation = true` and the error as the reason, so it can't stall in
  `in_progress` unseen. There's no draft, so approve returns 409 until someone reruns.
- **Rerun:** `POST /tickets/{id}/rerun` sets `in_progress` before scheduling, so a second
  rerun while one is running gets 409. Reruns append predictions, trace rows and a
  draft; approval acts on the newest draft.

### Draft Agent LLM: Gemini free tier by default, Claude optional
- **Superseded in Phase 8:** a free provider chain led by Groq; Gemini only for the
  `dev` tenant. See Phase 8.
- **Decision:** the Draft Agent calls its LLM through a small `Drafter` interface
  (`app/agents/drafter.py`). `DRAFT_PROVIDER=auto` picks Gemini when `GEMINI_API_KEY`
  is set, else Claude when `ANTHROPIC_API_KEY` is set, else an offline placeholder.
  The prompt, grounding rules, logging and failure handling are the same for every
  provider.
- **Why Gemini:** the project owner has no budget for a paid key, and Gemini's API has
  a free tier (a key from Google AI Studio, no card). The Claude drafter stays as a
  switchable option.
- **Gemini details:**
  - **Call:** Google's `google-genai` SDK (2.22), `client.aio.models.generate_content`.
  - **Model:** `gemini-3.8-flash`, the newest stable Flash model listed with a free
    tier on Google's pricing page (Sept 2026).
  - **Thinking:** level `low`, since a short grounded reply doesn't need deep
    reasoning; `max_output_tokens=8192`.
  - **Retries:** the free tier has low rate limits, so the client retries 429 and
    transient 5xx up to 4 attempts with backoff (2-30 s). A run that still fails takes
    the failure path, and the ticket can be rerun.
  - **Unusable answers:** a blocked prompt, a non-`STOP` finish (safety, max tokens,
    ...) or empty text raises `DraftError`.
- **Free-tier data use:** Google's pricing page says free-tier content is "used to
  improve our products" (paid tier: not used). That's fine for this project's synthetic
  tickets. For real customer data, use a paid tier or another provider.
- **Claude details (when selected):**
  - **Call:** `anthropic.AsyncAnthropic`, `beta.messages.create`, `claude-opus-5`.
  - **Settings:** adaptive thinking, effort `medium`, `max_tokens=16000`.
  - **Refusals:** server-side refusal fallbacks (`fallbacks="default"`) re-run a declined
    request on Anthropic's recommended fallback model.
- **Why the SDKs directly, not LangChain chat models:** the node makes one call. The
  SDKs give typed errors, finish reasons and token usage directly, and LangGraph needs
  no LangChain model wrapper.
- **Grounding:** the system prompt allows only the `<order>` and `<knowledge_base>`
  sections as facts. The model must say it will follow up rather than guess, ignore
  irrelevant entries, and treat the customer message as data (a prompt-injection
  guard). The full prompt and raw response are logged (spec: "full prompt sent, raw LLM
  output"), along with the provider (`mode`) and model.
- **No key:** an `OfflineDrafter` writes a placeholder starting with `[OFFLINE DRAFT: …]`,
  so the pipeline and review flow work without credentials and nobody mistakes it for a
  real draft. Tests use stub clients and a fake drafter, never the network.

### Deliberate deviations from 03-agent-architecture.md
- **`TicketState.retrieved_docs`** holds `RetrievedDoc` objects, not strings: the draft
  needs the content and the trace needs ids and similarity scores.
- **`OrderLookupResult`** adds `item_name` and `order_date`, so drafts can say "your Air
  Fryer ordered on the 3rd".
- **Classifiers and search read subject + body**, not only the body: subjects like
  "Refund status" carry signal.
- **Escalation gains a sixth rule:** a strong urgency rule (safety, fraud, threat,
  repeat contact, hardship, deadline) fires while the model didn't say `high`. This is
  the safety net planned during urgency v4 ("fix 3").
- **All fired rules are reported**, joined with "; ", not just the first, so the
  reviewer sees every reason.

### Review endpoints
- **Queue order:** escalated first, then by urgency (high → low), then oldest.
- **Approve/edit:** approve takes `{reviewer_id}` (a placeholder identity until there is
  auth). Edit takes `{edited_text, reviewer_id}`. Both set `approved = true` and
  `reviewed_at`, and resolve the ticket. Anything not awaiting review, or without a
  pending draft, gets 409. There is no reject endpoint, since the spec lists none;
  "reject" is an edit or a rerun.

### Knowledge search: bge-small replaces MiniLM, delay entry reworded
- **Problem:** the first live Gemini run was a desk lamp ticket: "ordered over a week
  ago and it still has not arrived. The tracking has not updated in days." Search
  returned "Tracking your order", "Wrong or missing items" and "Marked as delivered but
  not received". The delay policy ranked 7th, so the draft could not quote its trace
  and lost-parcel rules. The ticket never says "late" or "delayed".
- **Hidden by the Phase 3 check:** a hit there means any entry tagged with the ticket's
  category. Several entries are tagged `delivery_delay`, so this counted as a hit.
  Measured for the delay policy itself, it reached the top 3 for only 8 of the 20
  hand-written `delivery_delay` tickets.
- **What was tried** (all 384-d, so no migration):
  - Adding the linked order's status to the query ("Order status: delayed"): no change
    in ranking. One short line barely moves the embedding of a whole ticket. The spec
    also runs Knowledge before Order Lookup.
  - Other models: `multi-qa-MiniLM-L6-cos-v1` and `paraphrase-MiniLM-L6-v2` were worse,
    and `e5-small-v2` had lower hit@3. `all-MiniLM-L12-v2` and `bge-small-en-v1.5` were
    better.
  - Rewording the entry in customers' words ("still hasn't arrived", "past its expected
    delivery date"). This helped every model.
- **Decision:** `BAAI/bge-small-en-v1.5`, with its query instruction on queries only
  (`EMBEDDING_QUERY_PREFIX`). The delay entry is now "Late or delayed orders that
  haven't arrived" and opens with one sentence in customers' words. The policy is
  unchanged.
- **Result** on the 120 hand-written tickets: hit@1 0.82 → 0.88, hit@3 0.97 → 1.00,
  MRR 0.89 → 0.94, and no misses. The delay entry is in the top 3 for 19 of 20
  `delivery_delay` tickets (was 8). For the lamp ticket it ranks 1st, and a rerun's
  draft now quotes the trace, the 2-day update and the 7-day lost-parcel rule.
- **Alternatives' numbers** (reworded entry): MiniLM-L12 hit@1 0.84, delay entry 19/20.
  bge without the query instruction: hit@1 0.84, delay entry 20/20.
- **Costs:** a second sentence model (~130 MB) is loaded, because urgency v4 keeps its
  MiniLM features. Changing the model means re-embedding: `seed_knowledge_base --reset`.
- **Caveat:** the model and wording were picked on the same 120 tickets reported here,
  so these numbers are optimistic. The lamp ticket is the only query outside that set.
  `test_late_order_ticket_retrieves_the_delay_policy` guards it.

### Known limitations
- **Cold start:** the first ticket after startup waits several seconds while the
  classifiers and both sentence models load. Later runs take milliseconds per node, plus
  the LLM call.
- **In-process background tasks:** a run in progress is lost if the server restarts
  mid-run, leaving the ticket `in_progress` and rerun returning 409. That's acceptable
  at this scale (the spec says no queue); a stale-run sweeper or a real queue would fix
  it.

---

## Phase 5 — React frontend

### Stack: Vite + React 19 + TypeScript, Tailwind, TanStack Query, Recharts
- **Decision:** `frontend/` scaffolded with create-vite (`react-ts`), React Router for
  the five pages, TanStack Query for fetching, caching and polling, Tailwind v4 for
  styling, Recharts for the dashboard (as the spec says). No component library:
  a handful of shared classes (`btn-*`, `badge`, `input`) in `index.css`.
- **Why TanStack Query:** the spec relies on polling (ticket status, the live trace,
  the queue). `refetchInterval` as a function of the data stops polling once a run ends,
  and one cache means approving a draft updates the queue count and the dashboard.

### No CORS: the Vite server proxies `/api` to FastAPI
- **Decision:** the app calls `/api/...`; `vite.config.ts` forwards it to
  `http://localhost:8000` (or `API_URL`) for both `dev` and `preview`.
- **Why:** same-origin requests, so the backend needs no CORS middleware and no
  allowed-origins setting. A real deployment would serve both behind one reverse proxy.

### Types mirror the Pydantic schemas by hand, checked by a backend test
- **Decision:** `frontend/src/types/index.ts` has one interface per schema, as the spec
  asks. `backend/tests/test_frontend_types.py` compares it with FastAPI's OpenAPI schema:
  field names for 15 schemas, optional request fields, and the enum values.
- **Why:** hand-written types read better than generated ones, and the test catches
  drift, so a backend change can't silently break the UI.
- **Agent logs** are `dict[str, Any]` in the API. `src/lib/trace.ts` reads them with
  typed, defensive views of what `app/agents/nodes.py` writes.

### Backend additions the frontend needed
- **Customers:** the Submit Ticket form needs a `customer_id` and offers "search by order
  ID or customer email", but the API had only `GET /orders/{id}`. Added
  `GET /customers?search=` (name or email, case-insensitive, LIKE wildcards escaped),
  `GET /customers/{id}` and `GET /customers/{id}/orders`. Pasting an order ID into the
  customer field selects that order's customer and links the order.
- **Metrics:** `GET /metrics/summary` (listed in the spec, not built in Phase 4). Definitions:
  - escalation rate = flagged / tickets the Escalation Agent decided on (running or
    failed-early tickets don't count), overall and per UTC day for the last `days` days;
  - a reviewed draft is the approved one (one per resolved ticket, so reruns don't
    double count); approval rate = approved without edits / reviewed;
  - resolution time = ticket created → draft approved.
- **Knowledge snippets:** the Knowledge Agent's log now includes each entry's content,
  not only title and score. The review screen shows exactly what the draft was grounded
  in, even after the knowledge base is edited or re-seeded (Phase 4 re-seeding changed
  every entry id). Older runs show titles only.

### Review flow
- **Draft editor:** the draft is editable inline. "Approve" is enabled only while the
  text is unchanged; once edited, "Edit & approve" sends the new text, and "Revert"
  restores the AI draft. So a reviewer can't approve the original by mistake after
  editing.
- **Reviewer identity:** a "Reviewing as" field in the header, stored in localStorage,
  sent as `reviewer_id`. A placeholder until there is auth.
- **Failed runs:** a ticket awaiting review with no draft shows the error path (link to
  the trace, "Rerun agents") instead of an editor.
- **Runs:** reruns append logs; a run starts at each Triage log. The detail page and
  trace show the latest run; the trace can switch to earlier runs.

### Dashboard
- **Charts:** tickets by category (bars in the category colours), escalation rate per day
  (line, 7/30/90-day range on that chart only, since the other metrics are all-time),
  draft approval (as-is vs edited, stacked by escalation), average resolution time by
  category.
- **Colour:** six fixed category colours, used on every badge and chart, validated for
  colour-blind separation. Three of them are below 3:1 contrast on white, so every chart
  has direct value labels and a table view. Urgency uses status colours (grey, amber,
  red) with a level icon and a label, never colour alone.

### Checked end to end
- In headless Chrome against the real backend and Gemini: submit a ticket with a linked
  order, watch the five steps finish live, open the trace, edit and approve the draft,
  see the queue and dashboard update. No console errors; no horizontal scroll at 390 px.
- **Finding:** the category model (v1) labelled "ordered over a week ago, still hasn't
  arrived, tracking hasn't moved" as `damaged_item` (0.59). The low-confidence rule
  escalated it, as designed. The category model is weak on this phrasing and could be
  revisited in Phase 6 with reviewer corrections.

---

## Phase 6 — Feedback loop

### Corrections live next to the model's labels
- **Decision:** `tickets.corrected_category` and `corrected_urgency` (nullable, same CHECK
  values as `category`/`urgency`), plus `corrected_by` and `corrected_at`. The model's
  `category`/`urgency` are never overwritten.
- **Why:** keeping both makes the disagreement itself the data: it is what becomes a
  training row, and it lets model accuracy on reviewed tickets be measured later.
  `corrected_by`/`corrected_at` are beyond the spec's two fields: an audit trail, and the
  export orders by them.
- **Only disagreements count:** a value equal to the model's label is stored as null, so
  "no correction" has one meaning. Not correcting is *not* treated as confirming the
  model's label: reviewers mostly look at the draft, so silence is weak evidence.

### Endpoint and UI
- **Decision:** `PUT /reviews/{ticket_id}/triage` with the full correction (replace
  semantics, so a correction can be changed or cleared). Allowed on any triaged ticket,
  before or after approval; 409 before triage.
- **UI:** "Correct the triage" in the ticket's Triage card: two dropdowns marked with the
  model's choice. Corrected labels show everywhere with a pencil mark, and the card keeps
  "model: X" next to each correction.
- **Queue order uses the corrected urgency.** A reviewer who raises a ticket to high
  sees it move up. The escalation flag is not recomputed: it records what the agents
  decided, and a rerun would recompute it from fresh predictions anyway.

### The pipeline: export, then train
- **Export:** `scripts/export_feedback.py` rebuilds `data/feedback/corrections.csv` from
  the database on every run (a full snapshot, written atomically, with a manifest).
  A snapshot rather than an append-only log, because corrections can be changed or
  cleared, and reruns must not duplicate rows. Rows use the same `subject\nbody` text the
  classifiers read at inference (`app.agents.state.ticket_text`), and carry the model
  version that made the corrected prediction.
- **Evaluation sets stay clean:** tickets whose text (or body) matches any file in
  `data/eval/` are dropped, so a reviewer pasting a test ticket can't leak it into training.
- **Not in git:** the file holds real customer messages. Each trained model's
  `metrics.json` records the export's sha256 and row count, which is enough to reproduce
  or audit a run on the machine that has the data.
- **Category training:** `train_category_model.py` adds the category corrections to the
  train split only (val/test/hand-written unchanged), weighted by `--feedback-weight`
  (default 10). Corrections are real tickets the model got wrong, and few next to 3,773
  synthetic rows, so they need weight to matter. 10 is a starting point, not a measured
  value; once there are ~50 corrections, pick it by cross-validation over them, as urgency
  v4 does for `human_weight`.
- **Urgency training:** urgency corrections join `load_urgency_human()` as source
  `feedback`, so the existing v4 procedure (5-fold CV over human tickets, choosing
  `human_weight` and class weights) uses them without new code.
- **Checked:** a throwaway category run with a one-row corrections file trained, recorded
  the feedback metadata, and was deleted. Tests cover the endpoint, the export (labels only
  where corrected, eval overlap, model versions, reruns) and the loaders.

### How this feeds a retraining cycle (not automated)
1. **Nightly:** run `export_feedback`. It prints, for each served model, how many
   exported corrections that model was not trained on.
2. **Trigger:** retrain when a model has enough new corrections to move the numbers:
   about 50 for category (a few per class), or when a reviewer-visible error pattern
   repeats. Retraining on every correction would mostly add noise and churn versions.
3. **Train a new version:** `train_category_model --version v2` /
   `train_urgency_model --version v5`. Artifacts are new directories; nothing served
   changes.
4. **Gate:** the candidate must beat the served version on data it has not seen: a fresh
   hand-written set (as urgency v2-v4 were chosen), and the cross-validated scores on the
   corrections. It must not regress on the existing sets. Corrections used in training
   can't also be the test, so hold some back, or wait for new ones.
5. **Promote:** set `CATEGORY_MODEL_VERSION` / `URGENCY_MODEL_VERSION` and restart. New
   predictions record the new version in `model_predictions`, so before/after correction
   rates can be compared per version.
6. **Roll back:** point the setting back at the old version; artifacts are never deleted.

- **Out of scope, on purpose:** a scheduler, automatic promotion, and drift monitoring.
  Step 4 needs a human judgement on small data; automating promotion on a handful of
  corrections would ship regressions.
- **Known bias:** corrections only come from tickets someone looked at closely, and
  reviewers fix what they notice, so the rows lean towards obvious mistakes. Weighting
  them up amplifies that. The gate in step 4 is the guard.
- **First real signal:** during testing the category model twice labelled "it still
  hasn't arrived, tracking hasn't moved" as `damaged_item`. That's exactly the kind of
  correction this loop is for.

---

## Frontend redesign and modular structure

### Structure: a UI kit, feature modules, thin pages
- **Decision:** `src/ui/` holds presentational primitives (Button, Tag, Sheet, Field,
  Segmented, Meter, PageHeader, feedback states). `src/features/<area>/` owns each
  area's data hooks and components (tickets, review, trace, intake, metrics, reviewer)
  and exposes them through `index.ts`. Pages only compose features and read the URL.
- **Why:** pages had grown their own queries, mutations and styling. Hooks such as
  `useApproveDraft` and `useCorrectTriage` now live next to the components that use
  them, cache updates happen in one place (`useApplyTicketUpdate`), and a restyle
  touches the kit, not every page.
- `types/index.ts` stays where it is: `backend/tests/test_frontend_types.py` reads it.

### Visual direction: "dispatch desk"
- **Decision:** design tokens in `index.css` (`@theme`): paper, ground, ink (three
  steps), line, postal-yellow accent, stop-red danger, ok green; a Bringhurst type scale;
  3 px label corners; no shadows. One typeface, Archivo (self-hosted variable font),
  with heavy expanded width for ticket subjects and titles.
- **Why:** the subject is e-commerce order support, so the vocabulary comes from parcel
  logistics: shipping labels, packing slips, tracking histories. The earlier look (slate,
  indigo, rounded cards with shadows) was a generic SaaS kit.
- **Restraint:** the bold element is the ticket label (expanded subject on a 2 px
  black rule). Everything else stays quiet. Yellow is only for the primary action, the
  queue count and the active nav item; red only for escalation and errors. Chart
  category colours are unchanged (still the validated palette).
- **Copy:** buttons say what happens ("Approve draft", "Approve my edits", "Save
  correction", "Run the agents again"). A resolved ticket shows "Approved reply", not
  "Reply sent", since nothing is emailed to the customer.
- **Checked:** every page at 1280 px and 390 px in headless Chrome, with real tickets
  (created for the check and deleted afterwards), including the failed-draft state from
  a real Gemini 504. No console errors, no horizontal scroll.

---

## Phase 7 — Tenancy and auth foundation

Roadmap context: RAPT becomes a multi-tenant product for small businesses, pilot first.
Phases 7-10 (tenancy and auth, a paid and resilient LLM, knowledge onboarding,
deployment) come before a pilot with 2-3 design partners (Phase 11); per-tenant config,
a helpdesk connector, an audit log and per-tenant metrics (Phases 12-15) follow what
the partners ask for.

### Invite-only accounts, one tenant per user
- **Decision:** `tenants` and `users` tables. Users sign in with email and password
  (argon2id); each belongs to exactly one tenant, as `admin` or `reviewer`. There is no
  public signup: the operator creates tenants and users with `scripts/tenants.py`, which
  prints a one-time password.
- **Why:** a pilot needs a handful of accounts and no third-party auth vendor. One
  tenant per user keeps isolation simple; an operator who needs to look inside a tenant
  does it through the CLI, not a cross-tenant login.
- **Email is unique across tenants** because the login form has no tenant field.

### Session: a signed JWT in an httpOnly cookie
- **Decision:** `POST /auth/login` sets an HS256 JWT (`sub`, `tenant_id`, `role`, 12 h) in
  an httpOnly, Secure, SameSite=Lax cookie. Each request re-reads the user: a
  deactivated user, or a token issued before `password_changed_at` (set by
  `reset-password`), is rejected.
- **CSRF:** a cookie is sent automatically, so every non-GET request must carry
  `X-RAPT-CSRF: 1`. Another site can't add a custom header to a cross-site request
  without a CORS preflight, and the API allows no cross-origin requests.
- **Brute force:** login attempts are limited per email and per client IP (in memory;
  enough for one API instance, a shared store for several).
- **Timing:** an unknown email still verifies a dummy hash, so it takes as long as a wrong
  password, and both get the same 401 message.
- **JWT_SECRET** must be set outside development; without it each process uses a random
  secret, which signs everyone out on restart.

### The tenant comes only from the token
- **Decision:** `app.core.deps` resolves the user from the cookie and opens the request's
  database session scoped to their tenant (`SessionDep`), so every route that touches the
  database is authenticated and tenant-scoped by construction. Request schemas forbid
  unknown fields: a `tenant_id` in a body is a 422, never used. `reviewer_id` left the
  request bodies; approvals and corrections record the signed-in user's email.

### Isolation in two layers
1. **Application:** services filter by `tenant_of(session)` and look rows up with
   `get_scoped`, so another tenant's record reads as 404. New rows get `tenant_id` from
   the column default (below), never from input.
2. **Database:** row-level security on every tenant table:
   `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`, for both reads
   and writes. The API connects as `rapt_app`, a role without superuser or BYPASSRLS, so
   the policy always applies. With no tenant in scope a query matches nothing and an
   insert fails.
- **Setting the tenant per transaction:** a SQLAlchemy `after_begin` listener runs
  `set_config('app.tenant_id', ..., true)` for sessions that carry a tenant. It has to be
  per transaction: the agent pipeline commits after every node, and a transaction-local
  setting resets on commit.
- **Default from the session:** `tenant_id` defaults to that same setting, so an insert
  lands in the caller's tenant without the code passing it.
- **Same-tenant foreign keys:** references are composite,
  `(tenant_id, customer_id) -> customers(tenant_id, id)` and so on, so even the owner
  connection can't link a ticket to another tenant's customer or order.
- **Login is the one cross-tenant lookup:** `auth_find_user(email)`, a SECURITY DEFINER
  function returning only what login needs; `rapt_app` can execute it but can't read
  `users` outside its tenant.
- **Least privilege:** `rapt_app` gets DML on business tables, SELECT on `tenants`, and
  SELECT plus UPDATE of `last_login_at` only on `users`. Tenants and users are created
  through the CLI.

### Deviation from the approved design: RLS is not FORCEd
- **Design said:** `FORCE ROW LEVEL SECURITY` so the table owner is bound too.
- **Built:** RLS is enabled but not forced. The owner connection is the deliberate admin
  path (migrations, operator CLI, seed and ML scripts), and on a managed Postgres where
  the owner isn't a superuser, FORCE would lock those tools out. Those tools always work
  inside an explicit `--tenant`, and the services' own filters apply to them.

### Existing data: a `dev` tenant that is never deployed
- The migration creates tenant `dev` and moves every existing row into it (the seeded
  customers and orders, the knowledge base, dev tickets). Seed and evaluation scripts
  now take `--tenant`, and `--reset` deletes only that tenant's rows (it used to
  TRUNCATE whole tables). A deployed database starts empty; pilot tenants hold only real
  data.

### Vector search stays inside the tenant
- `search()` filters by tenant and sets `hnsw.iterative_scan = strict_order` (pgvector
  0.8), so the HNSW index keeps scanning past other tenants' nearest neighbours until it
  has k rows of this tenant.

### Training data per tenant
- `export_feedback` requires `--tenant`: a business's corrections are its data. Pooling
  several tenants' corrections into the shared models needs each tenant's agreement,
  which belongs in the pilot agreement.

### Found on the way: XGBoost + torch crash on macOS
- Loading the embedding model (torch) before unpickling the XGBoost category model
  segfaulted the process: two OpenMP runtimes. It would have hit any server that
  embedded a knowledge-base entry before triaging its first ticket. `app/ml/__init__.py`
  now imports xgboost first.

### Tests
- The suite runs as `rapt_app` against the test database, so RLS is exercised on every
  test; clients sign in with a real session cookie. New: `test_auth.py` (cookie flags,
  wrong password and unknown email look the same, deactivation, rate limit, logout,
  tampered, expired and foreign-tenant tokens, password reset, CSRF) and `test_tenancy.py`
  (another tenant's records are 404 for reads and changes, lists and metrics are scoped,
  cross-tenant references are rejected, a body `tenant_id` is a 422, vector search stays
  in the tenant, raw SQL sees only the tenant, no tenant sees nothing, RLS blocks writing
  into another tenant, composite foreign keys hold for the owner, background runs write
  into the ticket's tenant, the operator CLI).

### Frontend sign-in
- **Decision:** a `/login` page; every other route sits behind `RequireSession`, which
  reads `GET /auth/me`. A 401 from any request clears the cached session and redirects to
  sign-in with `?next=` (only same-app paths are followed, so a crafted link can't bounce
  a user to another site). Signing in or out clears all cached data, since the next user
  may belong to another tenant. The header shows the user and tenant with "Sign out"; the
  "Reviewing as" box is gone.

---

## Phase 8 — Free, private and resilient drafting

### Constraint: no paid LLM
- The project owner can't pay for an API key. The Phase 7 roadmap assumed a paid tier
  so real customers' messages wouldn't be used for training; this phase finds free
  options that don't train on prompts instead.

### Providers checked (September 2026)
- **Gemini free tier:** Google may use prompts and responses to improve its products,
  and human reviewers may read them. Unsuitable for real customer data.
- **Groq free tier:** no retention of inference data by default (up to 30 days only for
  abuse or reliability investigations), a Zero Data Retention switch for every account,
  and its terms don't allow training on customer inputs or outputs. Confirm the current
  terms before the pilot.
- **Cerebras free tier:** says it doesn't store or reuse data. Our account currently gets
  `402 Payment required` for every model, so it can't be relied on.
- **Local model (Ollama):** free and fully private, but an 8 GB laptop can't run a useful
  model next to the embedding and classifier models. Worth revisiting with a server in
  Phase 10.

### Decision: a fallback chain of free providers
- `ChainDrafter` tries, in order: Groq `openai/gpt-oss-120b` (reasoning effort low),
  Groq `qwen/qwen3.8-27b` (its own rate-limit bucket, reasoning off), Cerebras
  `gpt-oss-120b`, Gemini (tenants in `GEMINI_ALLOWED_TENANTS` only, default `dev`),
  Claude (paid, optional). Only providers with keys join the chain; no key at all gives
  the offline placeholder.
- **One class for Groq and Cerebras:** both speak the OpenAI chat-completions API, so
  `OpenAICompatibleDrafter` calls them with `httpx` (no new SDK).
- **Retries:** 429, 5xx and timeouts are retried once (`LLM_ATTEMPTS_PER_PROVIDER=2`),
  honouring `Retry-After` up to 10 s; a longer wait, a bad key, no quota (402) or an
  invalid request moves straight to the next provider.
- **Unusable answers fail over too:** cut off at the token limit, stopped early, or empty.
- **Every attempt is recorded** in the draft step's log (`attempts`), and the trace view
  lists them when a fallback happened.
- **If every provider fails**, the existing failure path applies: the ticket goes to
  review escalated, with each provider's error in the reason.

### Tenant-aware routing
- The Draft Agent passes the ticket's tenant slug to the drafter. A provider that may
  train on prompts is skipped for any tenant not on its allow-list, so a real business's
  tickets can't reach it even if every other provider is down.

### Less data leaves the system
- **Contact details masked:** emails and phone numbers in the customer's message become
  `[email]` / `[phone]` before any LLM call; the reviewer still sees the original. Phone
  numbers need a `+` or separators: unbroken digit runs stay, because those are usually
  order or tracking numbers the reply needs.
- **No internal ids:** the order's internal UUID is no longer in the prompt (a live draft
  quoted it); the tracking number, item and dates remain.

### Interrupted runs resume at startup
- Background runs live in the API process, so a restart mid-run left tickets `new` or
  `in_progress` forever (a known limitation since Phase 4). On startup the API now reruns
  them one at a time. Finding them crosses tenants, so it goes through a narrow SECURITY
  DEFINER function, `unfinished_agent_runs()`, returning only ticket and tenant ids
  (migration `f2c5a8d1e7b3`). Correct for one API instance; several would need a lease
  first.

### Checked live
- A real ticket through the API: Groq `gpt-oss-120b` drafted in 1.2 s on the first try,
  with the phone and email masked in the prompt.
- With the primary model broken on purpose, the chain fell back to Groq's Qwen model and
  recorded the 404.
- Tests fake the providers with `httpx.MockTransport`: request shape, retries, giving up
  on long waits, non-retryable errors, fallback order, the tenant allow-list, masking,
  chain construction from keys, the tenant reaching the drafter, and resuming runs.

---

## Phase 9 — Knowledge onboarding, team, first tickets

### Why this phase has no real data yet
- There are no clients or real documents yet. The pipeline doesn't depend on any
  particular business: it's built and tested with documents that exist only inside the
  tests, and checked by hand in a throwaway tenant that was deleted afterwards. The
  first real content will be a prospect's own FAQ, which doubles as the demo.

### Help documents become sections
- **Formats:** Markdown, text, HTML (Python's `html.parser`: headings kept; nav, header,
  footer, scripts and styles dropped) and PDF (`pypdf`; no OCR, so scanned PDFs fail
  with a clear message). Pasted text is treated as Markdown.
- **One shape:** every format is converted to paragraphs with Markdown `#` headings,
  stored on `kb_documents.content`, so the chunker only understands one thing and a
  document can be reprocessed later without the original file.
- **Sections follow headings:** one section per heading, paragraphs packed up to 300
  tokens (the embedding model reads 512); an oversized paragraph is split at sentences,
  then words. Titles are "Document: Heading / Subheading" (the document's own top
  heading isn't repeated); a heading split in several sections gets "(part n)".
- **Background processing:** upload returns at once with status `processing`; sections
  are embedded in a background task, and the page polls until `ready` or `failed` (with
  the reason). Documents a restart left `processing` are finished at startup through
  `unfinished_kb_documents()` (SECURITY DEFINER, like the agent-run recovery).
- **Guards:** 5 MB per file, 20 files per upload, at most 400 sections per document; the
  same text twice in a tenant is refused (sha256); each file is reported separately so
  one bad file doesn't stop the rest.
- **Editing:** a section can be edited (re-embedded) or removed; removing a document
  removes its sections (ON DELETE CASCADE on a same-tenant foreign key).
- **Search preview:** `POST /knowledge-base/search` powers "Test a question", so an admin
  sees which sections a draft would be based on before any ticket arrives.
- **Not done:** importing from a URL. Fetching arbitrary URLs from the server needs SSRF
  protection (private addresses, redirects, size limits); it's worth its own step.

### First tickets without seeded customers
- A new tenant has no customers or orders, and a ticket needs a customer. The Submit
  page can add a new customer (name and email; `POST /customers`, unique per tenant)
  while filing the ticket. Linking an order stays optional until there's an order source.

### Team management
- Admins list, invite (reviewer or admin), deactivate, reactivate, change roles and reset
  passwords. With no free email service, a new or reset password is shown once as a
  one-time password for the admin to pass on.
- An admin can't demote or deactivate themselves, so a tenant can't lose its last admin
  by accident.
- Emails are unique across tenants, so inviting an email that exists elsewhere is a 409.
  That reveals an account exists somewhere; acceptable for invite-only accounts.
- The API role got INSERT on `users` and UPDATE on exactly the columns these actions
  change; RLS still limits it to the tenant.

### Roles in the UI and API
- Knowledge-base changes and the Team page are admin-only (403 for reviewers); reading
  the knowledge base and the search preview stay open, since reviewers check grounding.
  The nav shows Team to admins only.

### Found on the way
- A token issued in the same second as a password reset stayed valid (`iat` was whole
  seconds). `iat` now keeps sub-second precision, which JWT allows.
- Operator CLI: `delete-tenant --slug x --yes` removes a tenant and everything it owns
  (e.g. a prospect's trial); it refuses without `--yes`.

### Checked end to end
- In a throwaway tenant: upload a policy file (3 sections, ready in seconds), "Test a
  question" found the late-delivery section, invite a reviewer (one-time password
  shown), file a ticket for a new customer, and Groq's draft quoted the uploaded policy
  (carrier trace, update within 24 hours). The tenant was deleted afterwards.

---

## Phase 10 — Deployment

### Where: one server, paid for by Azure for Students credit
- **Constraint:** no paid services (the owner can't pay), and the app needs about 3 GB of
  RAM (torch with two embedding models, the classifiers, Postgres).
- **Options checked (September 2026):** Hugging Face Docker Spaces now need a paid plan;
  Render and Koyeb free tiers are 512 MB with 0.1 CPU and sleep when idle; Vercel's free
  plan is non-commercial only, times out at 10 s and can't hold torch; Oracle Always Free
  (2 CPU / 12 GB ARM) is free but needs a card for a $1 identity hold and may reclaim idle
  servers; Neon's free Postgres (pgvector, 0.5 GB) would suit a split setup.
- **Decision:** Azure for Students ($100 credit, no card) paying for a 4 GB VM, preferably
  Arm (`B2pls_v2`), roughly 3 months of credit. The free `B1s` (1 GB) is too small until
  the models move to ONNX Runtime; that's the way to stay free for 12 months.
- The design doesn't depend on Azure: any Linux server with ~4 GB and a public IP works.

### How: Docker Compose on one host
- `db` (pgvector/pgvector:pg17, no public port), `migrate` (creates `rapt_app`, runs
  Alembic, exits), `api` (one uvicorn process), `web` (Caddy: static app + `/api` proxy +
  automatic Let's Encrypt HTTPS), `backup` (nightly `pg_dump`, 14 days), `ops` (operator
  CLI on demand).
- **Same origin:** Caddy serves the app and proxies `/api`, so the session cookie is
  first-party and no CORS is needed, like in development.
- **Two database identities in production:** the owner (created by the Postgres image)
  is only given to `migrate`, `ops` and `backup`; the API only ever gets `rapt_app`, so
  RLS applies to it. `scripts/prod_setup.py` creates the role with its password.
- **One API process** because the login rate limiter and run recovery are per process.
- **Real client IPs:** uvicorn trusts `X-Forwarded-For` (`--proxy-headers`); without it
  every request would come from Caddy and the per-IP login limit would lock everyone out
  at once. The API port is only reachable on the compose network.
- **Models baked into the image** and Hugging Face set offline: no downloads at startup.
- **CPU-only torch and XGBoost on Linux:** PyPI's Linux torch wheels pull in several GB
  of CUDA libraries on both x86 and Arm (the first guess, that Arm wheels were CPU-only,
  was wrong: a local image build on Apple silicon filled the disk). `pyproject.toml` takes
  torch from PyTorch's CPU index on every Linux, and uses `xgboost-cpu` there (the same
  library without CUDA and NCCL). macOS keeps the PyPI wheels, which are CPU-only.
- **Image size:** uv's download cache sits in a BuildKit cache mount and the app files stay
  root-owned (the app only reads them; a `chown -R` layer stored a second copy of every
  file). The API image went from 6.6 GB to 2.7 GB.
- **Blank keys are no keys:** Compose passes an unset variable through as `""`, which
  crashed startup (the Gemini client refused an empty key). API keys and the JWT secret
  now treat a blank value as unset; other settings keep `""` (an empty
  `GEMINI_ALLOWED_TENANTS` still means no tenant may use Gemini).
- **Checked locally before the first deploy** (the full stack on Apple silicon, HTTPS on
  `localhost`): migrations and the API role, the security headers and the HTTP-to-HTTPS
  redirect, the session cookie's flags, an admin created with the ops command, a help
  document uploaded and embedded, a contact-form message triaged and drafted from that
  document, and a backup restored after deleting the business.
- **Secrets** live in `deploy/.env` on the server (gitignored, and `.dockerignore`
  keeps every `.env` out of images).
- **Headers:** HSTS, a strict Content-Security-Policy, `X-Frame-Options: DENY`, no
  `Server` header. `GET /health` (database ping) serves Docker's healthcheck and any
  uptime monitor.
- **Server hardening** (`setup-server.sh`): ufw with 22/80/443 only, key-only SSH,
  unattended security upgrades, a 2 GB swap file.
- **Hostname:** a free DuckDNS subdomain unless the owner has a domain.

### Customer intake: a hosted contact form (added before deploying)
- **Why now:** only a business's staff can sign in, so until now a customer's message
  could only reach RAPT by staff typing it in. A public form lets a design partner's real
  customers write in from a link on the business's website.
- **Decision:** `/contact/<slug>`, a public page with name, email, subject and message,
  no account. Off by default; an admin switches it on in Settings, which shows the link
  to share. Tickets carry `channel = contact_form` and a "From contact form" tag.
- **Tenant lookup without a session:** `contact_form_tenant(slug)`, a SECURITY DEFINER
  function returning only the id and name, and only when the form is on, so an unknown
  business and a switched-off form look the same. Everything after runs in that tenant's
  scope, like a signed-in request.
- **Spam and abuse:** a honeypot field (a filled one gets a normal-looking receipt and
  nothing is stored), 5 messages per visitor and 100 per business per hour (protecting
  the queue and the free LLM quota), strict field limits, and request bodies that forbid
  unknown fields.
- **Returning customers** are matched by email within the business. Anyone can type any
  email, so a message can land on an existing customer's record; staff see it as a new
  ticket. Verifying the email would need an email service (the next step).
- **The receipt** shows a short reference (the first 8 characters of the ticket id), the
  same one the ticket page shows, so staff and customer can talk about it.
- **Not yet:** the approved reply isn't emailed to the customer; staff send it themselves
  for now. Emailing it from a free sending service comes next, then an embeddable widget
  that reuses this endpoint.
- **Seen in the live check:** with an empty knowledge base, a draft promised a
  replacement no policy states. The Draft Agent's prompt forbids that; it's a reason to
  load a business's policies before switching its form on, and worth a stricter prompt
  check later.
