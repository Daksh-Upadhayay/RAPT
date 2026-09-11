"""Dashboard aggregates (05-frontend.md, Metrics Dashboard).

Definitions:
- Escalation rate: tickets flagged `needs_escalation` / tickets the Escalation Agent has
  decided on (tickets still running, or whose run failed before it, don't count).
- Reviewed draft: the draft a reviewer approved, one per resolved ticket. "Edited" means
  the reviewer changed the text before approving; approval rate is the as-is share.
- Resolution time: ticket created -> its draft approved.
- Days are UTC.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TicketCategory, TicketStatus
from app.core.tenancy import tenant_of
from app.models import DraftResponse, Ticket
from app.schemas.metrics import (
    CategoryCount,
    CategoryResolution,
    DailyEscalation,
    MetricsSummary,
    ReviewOutcome,
)


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


async def summary(session: AsyncSession, days: int, today: date | None = None) -> MetricsSummary:
    today = today or datetime.now(UTC).date()
    # Every figure is the session tenant's own (explicit filter; RLS also applies in the API)
    mine = Ticket.tenant_id == tenant_of(session)

    by_status = dict((await session.execute(select(Ticket.status, func.count()).where(mine).group_by(Ticket.status))).all())
    by_category = dict(
        (
            await session.execute(
                select(Ticket.category, func.count()).where(mine, Ticket.category.is_not(None)).group_by(Ticket.category)
            )
        ).all()
    )

    decided, escalated = (
        await session.execute(
            select(
                func.count(Ticket.needs_escalation),
                func.count().filter(Ticket.needs_escalation.is_(True)),
            ).where(mine)
        )
    ).one()

    start = today - timedelta(days=days - 1)
    day = cast(func.timezone("UTC", Ticket.created_at), Date)
    daily = {
        d: (n, e)
        for d, n, e in await session.execute(
            select(day, func.count(Ticket.needs_escalation), func.count().filter(Ticket.needs_escalation.is_(True)))
            .where(mine, day >= start)
            .group_by(day)
        )
    }
    escalation_by_day = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        n, e = daily.get(d, (0, 0))
        escalation_by_day.append(DailyEscalation(date=d, processed=n, escalated=e, rate=_ratio(e, n)))

    approved = DraftResponse.approved.is_(True)
    edited = DraftResponse.edited_text.is_not(None)
    flagged = func.coalesce(Ticket.needs_escalation, False)
    rows = await session.execute(
        select(edited, flagged, func.count())
        .join(Ticket, Ticket.id == DraftResponse.ticket_id)
        .where(mine, approved)
        .group_by(edited, flagged)
    )
    outcome_counts = {(was_edited, was_flagged): n for was_edited, was_flagged, n in rows}
    review_outcomes = [
        ReviewOutcome(
            outcome=name,
            escalated=outcome_counts.get((was_edited, True), 0),
            not_escalated=outcome_counts.get((was_edited, False), 0),
        )
        for name, was_edited in (("approved_as_is", False), ("edited", True))
    ]
    reviewed = sum(outcome_counts.values())
    as_is = review_outcomes[0].escalated + review_outcomes[0].not_escalated

    seconds = func.extract("epoch", DraftResponse.reviewed_at - Ticket.created_at)
    resolution = {
        category: (n, float(avg))
        for category, n, avg in await session.execute(
            select(Ticket.category, func.count(), func.avg(seconds))
            .join(DraftResponse, DraftResponse.ticket_id == Ticket.id)
            .where(mine, approved, Ticket.category.is_not(None))
            .group_by(Ticket.category)
        )
    }
    resolved_total = sum(n for n, _ in resolution.values())

    return MetricsSummary(
        total_tickets=sum(by_status.values()),
        tickets_by_status={s: by_status.get(s, 0) for s in TicketStatus},
        tickets_by_category=[CategoryCount(category=c, count=by_category.get(c, 0)) for c in TicketCategory],
        escalation_rate=_ratio(escalated, decided),
        escalation_by_day=escalation_by_day,
        drafts_reviewed=reviewed,
        approval_rate=_ratio(as_is, reviewed),
        review_outcomes=review_outcomes,
        avg_resolution_seconds=(
            sum(n * avg for n, avg in resolution.values()) / resolved_total if resolved_total else None
        ),
        resolution_by_category=[
            CategoryResolution(
                category=c,
                resolved=resolution.get(c, (0, None))[0],
                avg_resolution_seconds=resolution.get(c, (0, None))[1],
            )
            for c in TicketCategory
        ],
    )
