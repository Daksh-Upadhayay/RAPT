# RAPT Backend

FastAPI + async SQLAlchemy backend. Dependencies are managed with [uv](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync                          # create .venv and install locked dependencies
brew install pgvector             # Postgres extension for the knowledge base
createdb rapt && createdb rapt_test
cp .env.example .env             # optional: defaults target localhost; add a free GEMINI_API_KEY for real drafts
uv run alembic upgrade head      # apply migrations to the dev database
```

## Run

```bash
uv run uvicorn app.main:app --reload    # API docs at http://localhost:8000/docs
uv run pytest                           # uses the rapt_test database (reset on every run)
```

The reviewer UI is in `../frontend` (`npm run dev`, http://localhost:5173); it proxies
`/api` to this server on port 8000.

## Seed data + ML models

```bash
uv run python -m scripts.seed_orders                           # fake customers + orders (--reset to redo)
uv run python -m scripts.build_dataset                         # data/processed/tickets.csv (downloads Bitext once)
uv run python -m scripts.build_urgency_dataset                 # data/processed/urgency_tickets.csv
uv run python -m scripts.train_category_model --version v2     # -> app/ml/artifacts/category_classifier/v2/
uv run python -m scripts.train_urgency_model --version v3      # -> app/ml/artifacts/urgency_classifier/v3/
uv run python -m scripts.evaluate_model --model urgency_classifier --versions v1 v2 --eval-set ../data/eval/urgency_holdout_test.csv
uv run python -m scripts.seed_knowledge_base                  # embed data/knowledge_base.json into pgvector (--reset to redo)
uv run python -m scripts.search_knowledge_base "my parcel is late"   # top-3 matching entries
uv run python -m scripts.evaluate_retrieval                    # hit@1/hit@3 on the hand-written tickets
```

Each training run writes `model.joblib`, `metrics.json` and `report.md` (evaluation). To serve
a new version, set `CATEGORY_MODEL_VERSION` / `URGENCY_MODEL_VERSION` (defaults `v1` / `v4`).
Inference: `app.ml.category_model.predict_category(text)` and `app.ml.urgency_model.predict_urgency(text)`.

## Feedback loop (Phase 6)

```bash
uv run python -m scripts.export_feedback    # reviewer corrections -> ../data/feedback/corrections.csv
uv run python -m scripts.train_category_model --version v2   # picks the corrections up
```

See DECISIONS.md (Phase 6) for the retraining cycle.

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"   # then review the generated file
uv run alembic upgrade head
```
