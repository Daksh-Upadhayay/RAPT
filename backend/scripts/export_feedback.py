"""Export reviewers' triage corrections as training data (Phase 6 feedback loop).

Reads every ticket with a `corrected_category` or `corrected_urgency` and writes
data/feedback/corrections.csv, one row per ticket:

    ticket_id, text, category, urgency, predicted_category, predicted_urgency,
    category_model_version, urgency_model_version, corrected_by, corrected_at

`text` is subject + body exactly as the classifiers read it. `category` / `urgency` hold
the reviewer's label, or are empty where that field wasn't corrected (the model's label
is not treated as confirmed). The training scripts add these rows to their training data
(scripts.ml_training.load_feedback).

Each run rewrites the file from the database, so a correction that is changed or cleared
is changed or dropped here too, and reruns never duplicate rows. Tickets whose text
matches an evaluation set are left out, so those sets stay clean tests. The file holds
real customer messages, so it is not committed to git.

Safe to run on a schedule (e.g. nightly). It prints how many corrections each served
model has not been trained on yet: the signal to retrain (see DECISIONS.md, Phase 6).

One tenant per export (--tenant): a business's corrections are its data, and pooling
them into a shared model needs that business's agreement (DECISIONS.md, Phase 7).

Usage (from backend/):
    uv run python -m scripts.export_feedback --tenant acme
    uv run python -m scripts.export_feedback --tenant acme --output /tmp/corrections.csv
"""

import argparse
import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import ticket_text
from app.core.config import settings
from app.core.admin_db import UnknownTenant, admin_tenant_session
from app.core.tenancy import tenant_of
from app.core.enums import ModelName
from app.ml.store import ARTIFACTS_DIR
from app.models import ModelPrediction, Ticket
from scripts.ml_training import DATA_DIR, FEEDBACK_PATH, file_sha256, load_feedback

COLUMNS = [
    "ticket_id",
    "text",
    "category",
    "urgency",
    "predicted_category",
    "predicted_urgency",
    "category_model_version",
    "urgency_model_version",
    "corrected_by",
    "corrected_at",
]
EVAL_DIR = DATA_DIR / "eval"


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def eval_texts(eval_dir: Path = EVAL_DIR) -> set[str]:
    """Every ticket text in the evaluation sets, normalised for comparison."""
    return {_key(t) for path in sorted(eval_dir.glob("*.csv")) for t in pd.read_csv(path)["text"]}


async def collect(session: AsyncSession, excluded: set[str] = frozenset()) -> tuple[pd.DataFrame, int]:
    """Corrected tickets as training rows, oldest correction first, and how many were
    left out because their text (or body) is in `excluded`."""
    tickets = (
        await session.scalars(
            select(Ticket)
            .where(
                Ticket.tenant_id == tenant_of(session),
                or_(Ticket.corrected_category.is_not(None), Ticket.corrected_urgency.is_not(None)),
            )
            .order_by(Ticket.corrected_at, Ticket.id)
        )
    ).all()

    # The model version behind each ticket's current label is its newest prediction
    versions: dict[tuple, str] = {}
    if tickets:
        predictions = await session.scalars(
            select(ModelPrediction)
            .where(ModelPrediction.tenant_id == tenant_of(session), ModelPrediction.ticket_id.in_([t.id for t in tickets]))
            .order_by(ModelPrediction.created_at)
        )
        versions = {(p.ticket_id, p.model_name): p.model_version for p in predictions}

    rows, skipped = [], 0
    for t in tickets:
        text = ticket_text(t.subject, t.body)
        if _key(text) in excluded or _key(t.body) in excluded:
            skipped += 1
            continue
        rows.append(
            {
                "ticket_id": str(t.id),
                "text": text,
                "category": t.corrected_category or "",
                "urgency": t.corrected_urgency or "",
                "predicted_category": t.category or "",
                "predicted_urgency": t.urgency or "",
                "category_model_version": versions.get((t.id, ModelName.CATEGORY_CLASSIFIER), ""),
                "urgency_model_version": versions.get((t.id, ModelName.URGENCY_CLASSIFIER), ""),
                "corrected_by": t.corrected_by or "",
                "corrected_at": t.corrected_at.isoformat() if t.corrected_at else "",
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS), skipped


def write(df: pd.DataFrame, path: Path, tenant: str | None = None) -> None:
    """Replace the file in one step, so a training run never reads a half-written export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    manifest = {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tenant": tenant,
        "rows": len(df),
        "category_labels": int((df["category"] != "").sum()),
        "urgency_labels": int((df["urgency"] != "").sum()),
        "sha256": file_sha256(path),
    }
    path.with_name(f"{path.stem}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def served_model_status(path: Path) -> list[str]:
    """For each served model: feedback labels it was trained on vs labels exported now."""
    lines = []
    for model, label, version in (
        (ModelName.CATEGORY_CLASSIFIER, "category", settings.category_model_version),
        (ModelName.URGENCY_CLASSIFIER, "urgency", settings.urgency_model_version),
    ):
        metrics_path = ARTIFACTS_DIR / model / version / "metrics.json"
        trained = json.loads(metrics_path.read_text())["metadata"].get("feedback") if metrics_path.exists() else None
        trained_rows = trained["rows"] if trained else 0
        available = len(load_feedback(label, path))
        new = max(available - trained_rows, 0)
        lines.append(
            f"{model} {version} (served): trained on {trained_rows} corrections; {available} exported now"
            + (f" -> {new} not yet in training" if new else "")
        )
    return lines


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=FEEDBACK_PATH)
    parser.add_argument("--tenant", required=True, help="tenant slug whose corrections to export")
    args = parser.parse_args()

    try:
        async with admin_tenant_session(args.tenant) as session:
            df, skipped = await collect(session, eval_texts())
    except UnknownTenant as exc:
        raise SystemExit(f"Error: {exc}") from exc
    write(df, args.output, args.tenant)

    print(
        f"Exported {len(df)} corrected tickets ({(df['category'] != '').sum()} category, "
        f"{(df['urgency'] != '').sum()} urgency labels) to {args.output}"
    )
    if skipped:
        print(f"Left out {skipped} tickets whose text is in an evaluation set")
    print("\n".join(served_model_status(args.output)))


if __name__ == "__main__":
    asyncio.run(main())
