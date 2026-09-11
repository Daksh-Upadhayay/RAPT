"""Phase 6 feedback pipeline: corrections in the database -> training rows."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, ModelPrediction, Ticket
from scripts import export_feedback
from scripts.ml_training import feedback_metadata, load_feedback

NOW = datetime(2026, 9, 11, 12, tzinfo=UTC)


async def add_ticket(session: AsyncSession, customer: Customer, body: str, **fields) -> Ticket:
    ticket = Ticket(
        customer_id=customer.id,
        subject="Help",
        body=body,
        status="resolved",
        category="order_status",
        urgency="low",
        **fields,
    )
    session.add(ticket)
    await session.commit()
    return ticket


async def test_collect_exports_only_corrected_labels(session: AsyncSession, customer: Customer) -> None:
    both = await add_ticket(
        session,
        customer,
        "Parcel is two weeks late",
        corrected_category="delivery_delay",
        corrected_urgency="medium",
        corrected_by="r1",
        corrected_at=NOW,
    )
    urgency_only = await add_ticket(
        session, customer, "Charged twice, I need it today", corrected_urgency="high", corrected_by="r2", corrected_at=NOW + timedelta(hours=1)
    )
    await add_ticket(session, customer, "Where is my order?")  # not corrected: not exported
    # A rerun: the newest prediction is the one behind the current label
    for version in ("v1", "v2"):
        session.add(ModelPrediction(ticket_id=both.id, model_name="category_classifier", model_version=version, prediction="order_status", confidence=0.5))
        await session.commit()

    df, skipped = await export_feedback.collect(session)

    assert skipped == 0
    assert df["ticket_id"].tolist() == [str(both.id), str(urgency_only.id)]  # oldest correction first
    first, second = df.to_dict("records")
    assert first["text"] == "Help\nParcel is two weeks late"  # same format the classifiers read
    assert (first["category"], first["urgency"]) == ("delivery_delay", "medium")
    assert (first["predicted_category"], first["predicted_urgency"]) == ("order_status", "low")
    assert first["category_model_version"] == "v2"
    assert (second["category"], second["urgency"]) == ("", "high")  # model's category not treated as confirmed


async def test_collect_leaves_out_evaluation_tickets(session: AsyncSession, customer: Customer) -> None:
    await add_ticket(session, customer, "My  mirror arrived SHATTERED.", corrected_category="damaged_item", corrected_at=NOW)

    df, skipped = await export_feedback.collect(session, excluded={"my mirror arrived shattered."})

    assert (len(df), skipped) == (0, 1)


def test_eval_texts_reads_every_evaluation_set() -> None:
    texts = export_feedback.eval_texts()
    assert len(texts) > 200  # hand-written + urgency sets


async def test_written_file_feeds_the_training_loaders(session: AsyncSession, customer: Customer, tmp_path) -> None:
    await add_ticket(session, customer, "Two weeks late", corrected_category="delivery_delay", corrected_at=NOW)
    await add_ticket(session, customer, "Need it today!!", corrected_urgency="high", corrected_at=NOW)
    df, _ = await export_feedback.collect(session)
    path = tmp_path / "corrections.csv"

    export_feedback.write(df, path)

    category = load_feedback("category", path)
    assert category.to_dict("records") == [{"text": "Help\nTwo weeks late", "category": "delivery_delay"}]
    assert load_feedback("urgency", path)["urgency"].tolist() == ["high"]
    manifest = json.loads((tmp_path / "corrections.manifest.json").read_text())
    assert (manifest["rows"], manifest["category_labels"], manifest["urgency_labels"]) == (2, 1, 1)
    assert feedback_metadata("category", path)["rows"] == 1
    status = export_feedback.served_model_status(path)
    assert "1 exported now" in status[0] and "1 not yet in training" in status[0]


def test_missing_export_means_no_feedback(tmp_path) -> None:
    missing = tmp_path / "none.csv"
    assert load_feedback("category", missing).empty
    assert feedback_metadata("urgency", missing) == {"path": str(missing), "sha256": None, "rows": 0}
