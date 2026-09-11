from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import update

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import SESSION_COOKIE, _secret, create_token
from app.models import User
from tests.conftest import PASSWORD, make_user


async def login(client, email: str, password: str = PASSWORD):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_login_sets_a_hardened_session_cookie(anon_client, user) -> None:
    resp = await login(anon_client, "ADA@acme.example ")  # case and spaces don't matter

    assert resp.status_code == 200
    assert resp.json()["email"] == "ada@acme.example"
    assert resp.json()["tenant_name"] == "Acme Homewares"
    cookie = resp.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in cookie
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    me = await anon_client.get("/auth/me")  # the client now sends the cookie back
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_wrong_password_and_unknown_email_look_the_same(anon_client, user) -> None:
    wrong = await login(anon_client, user.email, "not it")
    unknown = await login(anon_client, "nobody@acme.example")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_deactivated_user_cannot_sign_in_or_keep_using_a_session(api, admin_factory, user) -> None:
    async with admin_factory() as session:
        await session.execute(update(User).where(User.id == user.id).values(is_active=False))
        await session.commit()

    async with api() as anon:
        assert (await login(anon, user.email)).status_code == 401
    async with api(user) as signed_in:
        assert (await signed_in.get("/auth/me")).status_code == 401


async def test_login_is_rate_limited(anon_client, user) -> None:
    for _ in range(settings.login_attempts_per_window):
        await login(anon_client, user.email, "wrong")

    resp = await login(anon_client, user.email)  # right password, but too late

    assert resp.status_code == 429


async def test_logout_clears_the_cookie(anon_client, user) -> None:
    await login(anon_client, user.email)

    resp = await anon_client.post("/auth/logout")

    assert resp.status_code == 204
    assert (await anon_client.get("/auth/me")).status_code == 401


async def test_routes_need_a_session(anon_client) -> None:
    for path in ("/tickets", "/reviews/queue", "/metrics/summary", "/knowledge-base", "/customers", "/auth/me"):
        assert (await anon_client.get(path)).status_code == 401, path


async def test_tampered_and_expired_tokens_are_rejected(api, user) -> None:
    good = create_token(user.id, user.tenant_id, user.role)
    tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
    expired = create_token(user.id, user.tenant_id, user.role, now=datetime.now(UTC) - timedelta(hours=settings.jwt_ttl_hours + 1))
    unsigned = jwt.encode({"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": "admin", "iat": 0, "exp": 9999999999}, "guess", algorithm="HS256")

    async with api() as client:
        for token in (tampered, expired, unsigned, "not-a-jwt"):
            client.cookies.set(SESSION_COOKIE, token)
            assert (await client.get("/auth/me")).status_code == 401, token


async def test_token_claiming_another_tenant_is_rejected(api, user, other_tenant) -> None:
    # Validly signed (e.g. a bug elsewhere), but the user isn't in that tenant: RLS hides them
    token = jwt.encode(
        {"sub": str(user.id), "tenant_id": str(other_tenant.id), "role": "admin", "iat": int(datetime.now(UTC).timestamp()), "exp": 9999999999},
        _secret(),
        algorithm="HS256",
    )
    async with api() as client:
        client.cookies.set(SESSION_COOKIE, token)
        assert (await client.get("/tickets")).status_code == 401


async def test_password_reset_signs_out_existing_sessions(api, admin_factory, user) -> None:
    async with admin_factory() as session:
        later = datetime.now(UTC) + timedelta(seconds=5)
        await session.execute(update(User).where(User.id == user.id).values(password_changed_at=later))
        await session.commit()

    async with api(user) as client:  # token issued before the reset
        assert (await client.get("/auth/me")).status_code == 401


async def test_changes_need_the_csrf_header(api, user, customer) -> None:
    async with api(user, csrf=False) as client:
        resp = await client.post("/tickets", json={"customer_id": str(customer.id), "subject": "Hi", "body": "Hello"})
        login_resp = await login(client, user.email)

    assert resp.status_code == 403
    assert login_resp.status_code == 403


async def test_reviewer_role_signs_in(anon_client, admin_factory, tenant) -> None:
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)

    resp = await login(anon_client, reviewer.email)

    assert resp.json()["role"] == "reviewer"
