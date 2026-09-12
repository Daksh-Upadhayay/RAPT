"""The tenant's own settings (Phase 10b): for now, the public contact form switch."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import AdminDep, SessionDep
from app.models import Tenant
from app.schemas.public import TenantSettings, TenantSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


async def _tenant(session, tenant_id) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)  # RLS: only the caller's own tenant is visible
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return tenant


def _settings(tenant: Tenant) -> TenantSettings:
    return TenantSettings(name=tenant.name, slug=tenant.slug, contact_form_enabled=tenant.contact_form_enabled)


@router.get("")
async def get_settings(admin: AdminDep, session: SessionDep) -> TenantSettings:
    return _settings(await _tenant(session, admin.tenant_id))


@router.patch("")
async def update_settings(data: TenantSettingsUpdate, admin: AdminDep, session: SessionDep) -> TenantSettings:
    tenant = await _tenant(session, admin.tenant_id)
    tenant.contact_form_enabled = data.contact_form_enabled
    await session.commit()
    await session.refresh(tenant)
    return _settings(tenant)
