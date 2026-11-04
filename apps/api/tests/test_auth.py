"""Tests for Clerk authentication (CITY-644).

JWTs are signed with a locally generated RSA key and served through a real
PyJWKClient whose network fetch is replaced with an in-memory JWKS, so the
signature/kid/issuer/expiry checks run exactly as in production. The Clerk
Backend API lookup (primary email + verification status) is stubbed.
"""

import json
import time
from uuid import UUID

import httpx
import jwt
import pytest
from city_api import clerk_auth
from city_api.clerk_auth import ClerkEmail, primary_email_from_clerk_user, verify_clerk_token
from city_api.config import Settings, settings
from city_api.models import User
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from httpx import AsyncClient
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm
from pydantic import ValidationError
from sqlalchemy import select

from tests.conftest import TEST_USER_ID, TEST_WORLD_ID, get_test_engine

CLERK_DOMAIN = "test-instance.clerk.accounts.dev"
ISSUER = f"https://{CLERK_DOMAIN}"
KID = "test-kid-1"
APP_ORIGIN = "http://localhost:5173"


def _new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _new_key()
OTHER_KEY = _new_key()


def make_token(
    sub: str = "user_abc123",
    *,
    key: rsa.RSAPrivateKey = SIGNING_KEY,
    kid: str = KID,
    iss: str = ISSUER,
    exp_offset: int = 60,
    azp: str | None = APP_ORIGIN,
    sid: str | None = "sess_test123",
) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": iss, "iat": now, "nbf": now, "exp": now + exp_offset}
    if azp is not None:
        claims["azp"] = azp
    if sid is not None:
        claims["sid"] = sid
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clerk(monkeypatch):
    """Production auth mode against a fake Clerk instance.

    Returns a dict mapping Clerk user id -> ClerkEmail (or None) that the
    stubbed Backend API answers from, plus a list recording lookups.
    """
    monkeypatch.setattr(settings, "auth_mode", "production")
    monkeypatch.setattr(settings, "clerk_domain", CLERK_DOMAIN)
    monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_dummy")
    monkeypatch.setattr(settings, "clerk_authorized_parties", [APP_ORIGIN])

    jwk = json.loads(RSAAlgorithm.to_jwk(SIGNING_KEY.public_key()))
    jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
    client = PyJWKClient(f"{ISSUER}/.well-known/jwks.json", cache_keys=True)
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [jwk]})
    monkeypatch.setattr(clerk_auth, "_jwks_client", client)
    monkeypatch.setattr(clerk_auth, "_jwks_client_domain", CLERK_DOMAIN)

    directory: dict[str, ClerkEmail | None] = {}
    lookups: list[str] = []

    async def fake_fetch(clerk_user_id: str) -> ClerkEmail | None:
        lookups.append(clerk_user_id)
        return directory.get(clerk_user_id)

    monkeypatch.setattr(clerk_auth, "fetch_clerk_primary_email", fake_fetch)
    return {"directory": directory, "lookups": lookups}


async def _user_by_clerk_id(clerk_user_id: str) -> User | None:
    _, session_factory = get_test_engine()
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
        return result.scalar_one_or_none()


async def _user_by_id(user_id: UUID) -> User:
    _, session_factory = get_test_engine()
    async with session_factory() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


class TestVerifyClerkToken:
    """JWT verification against the (stubbed) JWKS."""

    def test_valid_token(self, clerk):
        claims = verify_clerk_token(make_token())
        assert claims["sub"] == "user_abc123"
        assert claims["iss"] == ISSUER

    def test_expired_token(self, clerk):
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_clerk_token(make_token(exp_offset=-60))

    def test_wrong_issuer(self, clerk):
        with pytest.raises(jwt.InvalidIssuerError):
            verify_clerk_token(make_token(iss="https://evil.clerk.accounts.dev"))

    def test_bad_signature(self, clerk):
        # Same kid as the published key, but signed by a different private key.
        with pytest.raises(jwt.InvalidSignatureError):
            verify_clerk_token(make_token(key=OTHER_KEY))

    def test_unknown_kid(self, clerk):
        with pytest.raises(jwt.PyJWTError):
            verify_clerk_token(make_token(kid="not-published"))

    def test_disallowed_authorized_party(self, clerk):
        with pytest.raises(jwt.InvalidTokenError, match="authorized party"):
            verify_clerk_token(make_token(azp="https://attacker.example"))

    def test_vercel_preview_authorized_party(self, clerk):
        azp = "https://city-doodle-web-abc123-kds.vercel.app"
        assert verify_clerk_token(make_token(azp=azp))["azp"] == azp

    def test_missing_azp_rejected_when_parties_configured(self, clerk):
        with pytest.raises(jwt.MissingRequiredClaimError):
            verify_clerk_token(make_token(azp=None))

    def test_missing_azp_accepted_without_configured_parties(self, clerk, monkeypatch):
        monkeypatch.setattr(settings, "clerk_authorized_parties", [])
        assert verify_clerk_token(make_token(azp=None))["sub"] == "user_abc123"

    def test_azp_checked_against_cors_when_parties_unset(self, clerk, monkeypatch):
        monkeypatch.setattr(settings, "clerk_authorized_parties", [])
        monkeypatch.setattr(settings, "cors_origins", ["https://city-doodle-web.vercel.app"])
        monkeypatch.setattr(settings, "frontend_url", "")
        assert verify_clerk_token(make_token(azp="https://city-doodle-web.vercel.app"))
        with pytest.raises(jwt.InvalidTokenError):
            verify_clerk_token(make_token(azp="https://attacker.example"))

    def test_missing_sid_rejected(self, clerk):
        # JWT-template tokens share the instance keys and issuer but carry no sid.
        with pytest.raises(jwt.MissingRequiredClaimError):
            verify_clerk_token(make_token(sid=None))

    def test_jwks_client_uses_short_timeout(self, clerk, monkeypatch):
        monkeypatch.setattr(clerk_auth, "_jwks_client", None)
        client = clerk_auth.get_jwks_client()
        assert client.timeout == 5.0
        assert client.uri == f"{ISSUER}/.well-known/jwks.json"

    def test_hs256_token_rejected(self, clerk):
        token = jwt.encode(
            {"sub": "user_x", "iss": ISSUER, "iat": int(time.time()), "exp": int(time.time()) + 60},
            "secret",
            algorithm="HS256",
            headers={"kid": KID},
        )
        with pytest.raises(jwt.PyJWTError):
            verify_clerk_token(token)


class TestAuthEndpoints:
    """Request-level behavior of /auth and protected routes in production mode."""

    @pytest.mark.parametrize("path", ["/auth/register", "/auth/login", "/auth/logout"])
    async def test_password_endpoints_removed(self, client: AsyncClient, path: str):
        response = await client.post(path, json={"email": "a@example.com", "password": "x"})
        assert response.status_code in (404, 405)

    async def test_missing_token_returns_401(self, client: AsyncClient, clerk):
        response = await client.get("/auth/me")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_protected_route_without_token_returns_401(self, client: AsyncClient, clerk):
        assert (await client.get("/worlds")).status_code == 401

    async def test_malformed_header_returns_401(self, client: AsyncClient, clerk):
        response = await client.get("/auth/me", headers={"Authorization": "Token abc"})
        assert response.status_code == 401

    async def test_garbage_token_returns_401(self, client: AsyncClient, clerk):
        response = await client.get("/auth/me", headers=auth_header("not.a.jwt"))
        assert response.status_code == 401

    async def test_expired_token_returns_401(self, client: AsyncClient, clerk):
        response = await client.get("/auth/me", headers=auth_header(make_token(exp_offset=-60)))
        assert response.status_code == 401

    async def test_wrong_issuer_returns_401(self, client: AsyncClient, clerk):
        token = make_token(iss="https://evil.clerk.accounts.dev")
        assert (await client.get("/auth/me", headers=auth_header(token))).status_code == 401

    async def test_bad_signature_returns_401(self, client: AsyncClient, clerk):
        token = make_token(key=OTHER_KEY)
        assert (await client.get("/auth/me", headers=auth_header(token))).status_code == 401

    async def test_x_user_id_ignored_in_production(self, client: AsyncClient, clerk):
        response = await client.get("/worlds", headers={"X-User-Id": str(TEST_USER_ID)})
        assert response.status_code == 401

    async def test_unconfigured_clerk_fails_closed(self, client: AsyncClient, clerk, monkeypatch):
        monkeypatch.setattr(settings, "clerk_domain", "")
        monkeypatch.setattr(clerk_auth, "_jwks_client", None)
        response = await client.get("/auth/me", headers=auth_header(make_token()))
        assert response.status_code == 503


class TestUserResolution:
    """Linking Clerk users to local users."""

    async def test_existing_user_linked_by_verified_email(self, client: AsyncClient, clerk):
        """AC2: an existing user signing in with the same verified email keeps their worlds."""
        clerk["directory"]["user_existing"] = ClerkEmail("test@example.com", verified=True)
        headers = auth_header(make_token("user_existing"))

        me = await client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["id"] == str(TEST_USER_ID)
        assert me.json()["email"] == "test@example.com"

        worlds = await client.get("/worlds", headers=headers)
        assert worlds.status_code == 200
        assert str(TEST_WORLD_ID) in [w["id"] for w in worlds.json()]

        linked = await _user_by_clerk_id("user_existing")
        assert linked is not None and linked.id == TEST_USER_ID

        # Later requests resolve by clerk_user_id without asking Clerk again.
        assert (await client.get("/auth/me", headers=headers)).status_code == 200
        assert clerk["lookups"] == ["user_existing"]

    async def test_email_match_is_case_insensitive(self, client: AsyncClient, clerk):
        clerk["directory"]["user_case"] = ClerkEmail("Test@Example.com", verified=True)
        me = await client.get("/auth/me", headers=auth_header(make_token("user_case")))
        assert me.status_code == 200
        assert me.json()["id"] == str(TEST_USER_ID)

    async def test_unverified_email_not_linked(self, client: AsyncClient, clerk):
        """AC4: an unverified Clerk email is never linked to an existing user."""
        clerk["directory"]["user_unverified"] = ClerkEmail("test@example.com", verified=False)
        headers = auth_header(make_token("user_unverified"))

        me = await client.get("/auth/me", headers=headers)
        assert me.status_code == 403
        assert (await client.get("/worlds", headers=headers)).status_code == 403

        assert await _user_by_clerk_id("user_unverified") is None
        assert (await _user_by_id(TEST_USER_ID)).clerk_user_id is None

    async def test_no_primary_email_rejected(self, client: AsyncClient, clerk):
        clerk["directory"]["user_noemail"] = None
        me = await client.get("/auth/me", headers=auth_header(make_token("user_noemail")))
        assert me.status_code == 403
        assert await _user_by_clerk_id("user_noemail") is None

    async def test_new_user_created_and_can_create_world(self, client: AsyncClient, clerk):
        """AC1: a new Clerk user gets an account and can create a world."""
        clerk["directory"]["user_new"] = ClerkEmail("newbie@example.com", verified=True)
        headers = auth_header(make_token("user_new"))

        me = await client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == "newbie@example.com"
        assert me.json()["id"] != str(TEST_USER_ID)

        created = await client.post("/worlds", json={"name": "Fresh", "seed": 1}, headers=headers)
        assert created.status_code == 201

        worlds = (await client.get("/worlds", headers=headers)).json()
        assert [w["name"] for w in worlds] == ["Fresh"]

        user = await _user_by_clerk_id("user_new")
        assert user is not None
        assert user.password_hash is None
        assert str(user.id) == me.json()["id"]

    async def test_email_linked_to_other_clerk_user_conflicts(self, client: AsyncClient, clerk):
        clerk["directory"]["user_first"] = ClerkEmail("test@example.com", verified=True)
        clerk["directory"]["user_second"] = ClerkEmail("test@example.com", verified=True)
        assert (await client.get("/auth/me", headers=auth_header(make_token("user_first")))).status_code == 200

        second = await client.get("/auth/me", headers=auth_header(make_token("user_second")))
        assert second.status_code == 409
        assert (await _user_by_id(TEST_USER_ID)).clerk_user_id == "user_first"

    async def test_create_race_recovers_from_integrity_error(
        self, client: AsyncClient, clerk, monkeypatch
    ):
        """A concurrent request that created the user first makes our INSERT fail; we re-read."""
        clerk["directory"]["user_race"] = ClerkEmail("racer@example.com", verified=True)
        _, session_factory = get_test_engine()
        real_get_by_email = clerk_auth._get_by_email
        calls = {"n": 0}

        async def stale_get_by_email(db, email):
            calls["n"] += 1
            if calls["n"] == 1:
                # The "other request" wins between our lookups and our INSERT.
                async with session_factory() as other:
                    other.add(User(email="racer@example.com", clerk_user_id="user_race"))
                    await other.commit()
                return None
            return await real_get_by_email(db, email)

        monkeypatch.setattr(clerk_auth, "_get_by_email", stale_get_by_email)

        me = await client.get("/auth/me", headers=auth_header(make_token("user_race")))
        assert me.status_code == 200
        winner = await _user_by_clerk_id("user_race")
        assert winner is not None and me.json()["id"] == str(winner.id)

    async def test_link_race_does_not_steal_linked_row(
        self, client: AsyncClient, clerk, monkeypatch
    ):
        """If another Clerk user links the row between our read and UPDATE, we must not overwrite it."""
        clerk["directory"]["user_late"] = ClerkEmail("test@example.com", verified=True)
        _, session_factory = get_test_engine()
        real_get_by_email = clerk_auth._get_by_email
        calls = {"n": 0}

        async def racing_get_by_email(db, email):
            user = await real_get_by_email(db, email)
            calls["n"] += 1
            if calls["n"] == 1:
                async with session_factory() as other:
                    row = (await other.execute(select(User).where(User.id == TEST_USER_ID))).scalar_one()
                    row.clerk_user_id = "user_winner"
                    await other.commit()
            return user

        monkeypatch.setattr(clerk_auth, "_get_by_email", racing_get_by_email)

        me = await client.get("/auth/me", headers=auth_header(make_token("user_late")))
        assert me.status_code == 409
        assert (await _user_by_id(TEST_USER_ID)).clerk_user_id == "user_winner"
        assert await _user_by_clerk_id("user_late") is None


class TestClerkPayloadParsing:
    def test_verified_primary_email(self):
        payload = {
            "primary_email_address_id": "idn_2",
            "email_addresses": [
                {"id": "idn_1", "email_address": "old@x.com", "verification": {"status": "verified"}},
                {"id": "idn_2", "email_address": "main@x.com", "verification": {"status": "verified"}},
            ],
        }
        assert primary_email_from_clerk_user(payload) == ClerkEmail("main@x.com", True)

    def test_unverified_primary_email(self):
        payload = {
            "primary_email_address_id": "idn_1",
            "email_addresses": [
                {"id": "idn_1", "email_address": "a@x.com", "verification": {"status": "unverified"}}
            ],
        }
        assert primary_email_from_clerk_user(payload) == ClerkEmail("a@x.com", False)

    def test_missing_verification_is_unverified(self):
        payload = {
            "primary_email_address_id": "idn_1",
            "email_addresses": [{"id": "idn_1", "email_address": "a@x.com", "verification": None}],
        }
        assert primary_email_from_clerk_user(payload) == ClerkEmail("a@x.com", False)

    def test_no_primary_email(self):
        payload = {
            "primary_email_address_id": None,
            "email_addresses": [
                {"id": "idn_1", "email_address": "a@x.com", "verification": {"status": "verified"}}
            ],
        }
        assert primary_email_from_clerk_user(payload) is None

    async def test_missing_secret_key_fails_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "clerk_secret_key", "")
        with pytest.raises(HTTPException) as exc:
            await clerk_auth.fetch_clerk_primary_email("user_x")
        assert exc.value.status_code == 503

    @pytest.mark.parametrize(
        ("status", "expected"),
        [(404, 401), (500, 503)],
    )
    async def test_clerk_api_errors(self, monkeypatch, status, expected):
        """A user deleted in Clerk is unauthorized (401); a Clerk outage is 503."""
        monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_dummy")
        real_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/users/user_gone"
            assert request.headers["Authorization"] == "Bearer sk_test_dummy"
            return httpx.Response(status, json={"errors": []})

        monkeypatch.setattr(
            clerk_auth.httpx,
            "AsyncClient",
            lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
        )
        with pytest.raises(HTTPException) as exc:
            await clerk_auth.fetch_clerk_primary_email("user_gone")
        assert exc.value.status_code == expected

    async def test_clerk_api_success_parses_email(self, monkeypatch):
        monkeypatch.setattr(settings, "clerk_secret_key", "sk_test_dummy")
        real_client = httpx.AsyncClient
        payload = {
            "primary_email_address_id": "idn_1",
            "email_addresses": [
                {"id": "idn_1", "email_address": "a@x.com", "verification": {"status": "verified"}}
            ],
        }
        monkeypatch.setattr(
            clerk_auth.httpx,
            "AsyncClient",
            lambda **kw: real_client(
                transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)), **kw
            ),
        )
        assert await clerk_auth.fetch_clerk_primary_email("user_ok") == ClerkEmail("a@x.com", True)


class TestAuthModeConfig:
    """AUTH_MODE must fail closed (reviewer-f, #477)."""

    def test_unset_auth_mode_defaults_to_production(self, monkeypatch):
        monkeypatch.delenv("AUTH_MODE", raising=False)
        monkeypatch.delenv("FLY_APP_NAME", raising=False)
        assert Settings(_env_file=None).auth_mode == "production"

    def test_unknown_auth_mode_rejected(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "prod")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_dev_auth_mode_refused_on_fly(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "dev")
        monkeypatch.setenv("FLY_APP_NAME", "city-doodle-api")
        with pytest.raises(ValidationError, match="not allowed on Fly"):
            Settings(_env_file=None)

    def test_production_auth_mode_allowed_on_fly(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "production")
        monkeypatch.setenv("FLY_APP_NAME", "city-doodle-api")
        assert Settings(_env_file=None).auth_mode == "production"

    def test_dev_auth_mode_allowed_off_fly(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "dev")
        monkeypatch.delenv("FLY_APP_NAME", raising=False)
        assert Settings(_env_file=None).auth_mode == "dev"


class TestDevMode:
    """Dev mode (X-User-Id) still requires the user to exist."""

    async def test_unknown_x_user_id_rejected(self, client: AsyncClient):
        assert settings.auth_mode == "dev"
        response = await client.get(
            "/worlds", headers={"X-User-Id": "00000000-0000-0000-0000-0000000000ff"}
        )
        assert response.status_code == 401

    async def test_known_x_user_id_accepted(self, client: AsyncClient):
        response = await client.get("/worlds", headers={"X-User-Id": str(TEST_USER_ID)})
        assert response.status_code == 200
