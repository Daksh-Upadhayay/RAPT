# RAPT Backend

FastAPI + async SQLAlchemy backend. Dependencies are managed with [uv](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync                          # create .venv and install locked dependencies
createdb rapt && createdb rapt_test
cp .env.example .env             # optional: defaults target localhost
uv run alembic upgrade head      # apply migrations to the dev database
```

## Run

```bash
uv run uvicorn app.main:app --reload    # API docs at http://localhost:8000/docs
uv run pytest                           # uses the rapt_test database (reset on every run)
```

## Seed data + ML models

```bash
uv run python -m scripts.seed_orders                           # fake customers + orders (--reset to redo)
uv run python -m scripts.build_dataset                         # data/processed/tickets.csv (downloads Bitext once)
uv run python -m scripts.build_urgency_dataset                 # data/processed/urgency_tickets.csv
uv run python -m scripts.train_category_model --version v2     # -> app/ml/artifacts/category_classifier/v2/
uv run python -m scripts.train_urgency_model --version v3      # -> app/ml/artifacts/urgency_classifier/v3/
uv run python -m scripts.evaluate_model --model urgency_classifier --versions v1 v2 --eval-set ../data/eval/urgency_holdout_test.csv
```

Each training run writes `model.joblib`, `metrics.json` and `report.md` (evaluation). To serve
a new version, set `CATEGORY_MODEL_VERSION` / `URGENCY_MODEL_VERSION` (defaults `v1` / `v4`).
Inference: `app.ml.category_model.predict_category(text)` and `app.ml.urgency_model.predict_urgency(text)`.

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"   # then review the generated file
uv run alembic upgrade head
```
