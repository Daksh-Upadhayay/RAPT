"""Phase 9: tenant admins manage their team."""

from app.core.enums import UserRole
from tests.conftest import make_user


async def test_admin_invites_a_reviewer_who_can_sign_in(client, anon_client) -> None:
    resp = await client.post("/team", json={"email": "Rev@Acme.example", "name": "Rev", "role": "reviewer"})

    assert resp.status_code == 201
    issued = resp.json()
    assert issued["member"]["email"] == "rev@acme.example" and issued["member"]["role"] == "reviewer"
    login = await anon_client.post("/auth/login", json={"email": "rev@acme.example", "password": issued["one_time_password"]})
    assert login.status_code == 200 and login.json()["tenant_name"] == "Acme Homewares"
    assert {m["email"] for m in (await client.get("/team")).json()} == {"ada@acme.example", "rev@acme.example"}


async def test_email_already_used_anywhere_is_refused(client, admin_factory, other_tenant) -> None:
    await make_user(admin_factory, other_tenant, "taken@example.com")

    resp = await client.post("/team", json={"email": "taken@example.com", "name": "Someone"})

    assert resp.status_code == 409


async def test_deactivate_reactivate_and_role_changes(client, api, admin_factory, tenant) -> None:
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)

    off = await client.patch(f"/team/{reviewer.id}", json={"is_active": False})
    assert off.json()["is_active"] is False
    async with api(reviewer) as rc:
        assert (await rc.get("/auth/me")).status_code == 401
    assert (await client.patch(f"/team/{reviewer.id}", json={"is_active": True, "role": "admin"})).json()["role"] == "admin"


async def test_reset_password_signs_the_member_out(client, api, admin_factory, anon_client, tenant) -> None:
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)
    async with api(reviewer) as rc:  # signed in before the reset
        assert (await rc.get("/auth/me")).status_code == 200

        issued = (await client.post(f"/team/{reviewer.id}/reset-password")).json()

        assert (await rc.get("/auth/me")).status_code == 401
    assert (await anon_client.post("/auth/login", json={"email": reviewer.email, "password": issued["one_time_password"]})).status_code == 200


async def test_admin_cannot_lock_themselves_out(client, user) -> None:
    assert (await client.patch(f"/team/{user.id}", json={"is_active": False})).status_code == 409
    assert (await client.patch(f"/team/{user.id}", json={"role": "reviewer"})).status_code == 409


async def test_team_is_admin_only_and_tenant_scoped(api, admin_factory, tenant, other_tenant, client) -> None:
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)
    outsider = await make_user(admin_factory, other_tenant, "boss@globex.example")

    async with api(reviewer) as rc:
        assert (await rc.get("/team")).status_code == 403
        assert (await rc.post("/team", json={"email": "x@acme.example", "name": "X"})).status_code == 403
    async with api(outsider) as oc:
        assert [m["email"] for m in (await oc.get("/team")).json()] == ["boss@globex.example"]
        assert (await oc.patch(f"/team/{reviewer.id}", json={"is_active": False})).status_code == 404
        assert (await oc.post(f"/team/{reviewer.id}/reset-password")).status_code == 404
