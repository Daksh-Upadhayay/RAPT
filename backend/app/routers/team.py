"""Team page: a tenant admin manages who can sign in (Phase 9). Admin-only."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import AdminDep, SessionDep
from app.schemas.team import InviteRequest, MemberUpdate, PasswordIssued, TeamMember
from app.services import team as team_service

router = APIRouter(prefix="/team", tags=["team"])


@router.get("")
async def list_members(admin: AdminDep, session: SessionDep) -> list[TeamMember]:
    return [TeamMember.model_validate(u) for u in await team_service.list_members(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def invite(data: InviteRequest, admin: AdminDep, session: SessionDep) -> PasswordIssued:
    """Create an account in this tenant; the response carries its one-time password."""
    try:
        user, password = await team_service.invite(session, data.email, data.name, data.role)
    except team_service.EmailTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "That email already has an account.") from exc
    return PasswordIssued(member=TeamMember.model_validate(user), one_time_password=password)


@router.patch("/{member_id}")
async def update_member(member_id: UUID, data: MemberUpdate, admin: AdminDep, session: SessionDep) -> TeamMember:
    try:
        user = await team_service.update_member(session, member_id, admin.id, data.role, data.is_active)
    except team_service.MemberNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team member not found") from exc
    except team_service.SelfChange as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't remove your own admin access or deactivate yourself.") from exc
    return TeamMember.model_validate(user)


@router.post("/{member_id}/reset-password")
async def reset_password(member_id: UUID, admin: AdminDep, session: SessionDep) -> PasswordIssued:
    """A new one-time password; the member is signed out everywhere."""
    try:
        user, password = await team_service.reset_password(session, member_id)
    except team_service.MemberNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team member not found") from exc
    return PasswordIssued(member=TeamMember.model_validate(user), one_time_password=password)
