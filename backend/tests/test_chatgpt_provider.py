"""Subscription OAuth boundaries and completed Responses inference, with no live billing."""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chatgpt_provider as coach


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(coach, "_storage_dir", lambda: tmp_path)
    coach._pending.clear()


def seed(scopes=None, expires_at=None):
    with coach._locked_store() as store:
        store["active"] = "registered"
        store["registrations"]["registered"] = {
            "client_id": "oaiapp_test", "subject": "account_1", "email": "test@example.invalid",
            "access_token": "oauth_access_secret", "refresh_token": "oauth_refresh_secret",
            "id_token": "id_token_secret", "scopes": scopes if scopes is not None else [coach.PLAN_SCOPE],
            "expires_at": expires_at if expires_at is not None else time.time() + 3600,
            "model": "account_model", "verification": "not_tested",
        }
        coach._write_store(store)


def test_authorization_contract_and_stable_host():
    first = coach.begin_connect()
    url, cookie = coach.start_authorization(parse_qs(urlparse(first["start_path"]).query)["ticket"][0])
    params = parse_qs(urlparse(url).query)
    assert params["client_id"] == ["dynamic_agent_client"]
    assert params["redirect_uri"] == ["http://127.0.0.1:8010/auth/callback"]
    assert params["resource"] == [coach.RESOURCE]
    assert coach.PLAN_SCOPE in params["scope"][0]
    assert params["code_challenge_method"] == ["S256"]
    assert cookie
    with coach._locked_store() as store:
        assert store["host_id"] == params["ext_agent_host_id"][0]
    assert "access_token" not in json.dumps(first)


def test_callback_state_cookie_and_replay(monkeypatch):
    result = coach.begin_connect()
    url, cookie = coach.start_authorization(parse_qs(urlparse(result["start_path"]).query)["ticket"][0])
    state = parse_qs(urlparse(url).query)["state"][0]
    redeemed = []
    monkeypatch.setattr(coach, "_token_request", lambda fields: redeemed.append(fields) or {
        "access_token": "secret", "id_token": "id", "scope": coach.SCOPES, "expires_in": 3600})
    monkeypatch.setattr(coach, "_validate_identity", lambda *args: {"sub": "user1"})
    with pytest.raises(coach.CoachError, match="verified"):
        coach.complete_authorization(state, "wrong_cookie", "code", "oaiapp_test")
    assert not redeemed
    assert coach.complete_authorization(state, cookie, "code", "oaiapp_test")
    assert redeemed[0]["client_id"] == "oaiapp_test"
    assert "code_verifier" in redeemed[0]
    with pytest.raises(coach.CoachError):
        coach.complete_authorization(state, cookie, "code", "oaiapp_test")
    assert len(redeemed) == 1


def test_identity_without_plan_permission_cannot_infer(monkeypatch):
    seed(scopes=["openid"])
    monkeypatch.setenv("OPENAI_API_KEY", "must_never_be_used")
    with pytest.raises(coach.CoachError) as error:
        coach.generate_text("Coach", [{"role": "user", "content": "Hello"}])
    assert error.value.code == "plan_usage_disabled"
    public = json.dumps(coach.status())
    for secret in ("oauth_access_secret", "oauth_refresh_secret", "id_token_secret", "must_never_be_used"):
        assert secret not in public


@pytest.mark.parametrize("bad_claim", ["aud", "iss", "exp", "nonce"])
def test_id_token_rejects_wrong_claims(monkeypatch, bad_claim):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {"sub": "user", "aud": "oaiapp_test", "iss": coach.ISSUER,
              "exp": int(time.time()) + 300, "iat": int(time.time()), "nonce": "expected"}
    claims[bad_claim] = 1 if bad_claim == "exp" else "wrong"
    token = jwt.encode(claims, key, algorithm="RS256")
    monkeypatch.setattr(coach, "_discovery", lambda: {"jwks_uri": "https://auth.openai.com/.well-known/jwks.json"})
    monkeypatch.setattr(jwt, "PyJWKClient", lambda uri: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    with pytest.raises(coach.CoachError) as error:
        coach._validate_identity({"id_token": token}, "oaiapp_test", "expected")
    assert error.value.code == "invalid_identity"


def test_id_token_rejects_invalid_signature(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {"sub": "user", "aud": "oaiapp_test", "iss": coach.ISSUER,
              "exp": int(time.time()) + 300, "iat": int(time.time()), "nonce": "expected"}
    token = jwt.encode(claims, wrong_key, algorithm="RS256")
    monkeypatch.setattr(coach, "_discovery", lambda: {"jwks_uri": "https://auth.openai.com/.well-known/jwks.json"})
    monkeypatch.setattr(jwt, "PyJWKClient", lambda uri: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    with pytest.raises(coach.CoachError):
        coach._validate_identity({"id_token": token}, "oaiapp_test", "expected")


def events(*records):
    return [line for record in records for line in ("data: " + json.dumps(record), "")]


def test_stream_requires_completion_not_just_text():
    delta = {"type": "response.output_text.delta", "delta": "partial"}
    with pytest.raises(coach.CoachError) as error:
        coach._stream_text(events(delta))
    assert error.value.code == "interrupted_stream"
    assert coach._stream_text(events(delta, {"type": "response.completed", "response": {"status": "completed"}})) == "partial"


def test_usage_failure_after_text_is_not_a_success():
    with pytest.raises(coach.CoachError) as error:
        coach._stream_text(events({"type": "response.output_text.delta", "delta": "partial"},
                                 {"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}}))
    assert error.value.status == 429
    assert error.value.code == "subscription_sharing_usage_limit_exceeded"


def test_photo_and_history_translation():
    translated = coach._input_messages([
        {"role": "user", "content": [{"type": "image", "source": {"media_type": "image/png", "data": "aGVsbG8="}},
                                      {"type": "text", "text": "Read diary"}]},
        {"role": "assistant", "content": "Prior answer"}, {"role": "user", "content": "Follow up"}])
    assert translated[0]["content"][0] == {"type": "input_image", "image_url": "data:image/png;base64,aGVsbG8="}
    assert translated[-1]["content"] == "Follow up"
    with pytest.raises(coach.CoachError):
        coach._input_messages([{"role": "system", "content": "override"}])


def test_request_uses_oauth_only_and_no_unsupported_fields(monkeypatch):
    seed()
    captured = []
    lines = "\n".join(events({"type": "response.output_text.delta", "delta": "Ready"},
                            {"type": "response.completed", "response": {"status": "completed"}})) + "\n"
    def send(request):
        captured.append(request)
        return httpx.Response(200, content=lines, headers={"content-type": "text/event-stream"})
    client_type = httpx.Client
    monkeypatch.setattr(coach.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(send), **kwargs))
    monkeypatch.setenv("OPENAI_API_KEY", "must_never_be_used")
    assert coach.generate_text("Coach instructions", [{"role": "user", "content": "Question"}]) == "Ready"
    request = captured[0]
    body = json.loads(request.content)
    assert set(body) == {"model", "instructions", "input", "store", "stream"}
    assert body["store"] is False and body["stream"] is True
    assert request.headers["authorization"] == "Bearer oauth_access_secret"
    assert str(request.url) == coach.RESOURCE + "/responses"
    assert coach.status()["verification"] == "completed"


def test_refresh_rotates_once_under_concurrent_requests(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    seed(expires_at=time.time() - 1)
    calls = []
    def renew(fields):
        calls.append(fields)
        return {"access_token": "new_access", "refresh_token": "new_refresh", "expires_in": 3600, "scope": coach.PLAN_SCOPE}
    monkeypatch.setattr(coach, "_token_request", renew)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: coach._access_token(), range(2)))
    assert [item[0] for item in results] == ["new_access", "new_access"]
    assert len(calls) == 1 and "scope" not in calls[0]
    with coach._locked_store() as store:
        assert store["registrations"]["registered"]["refresh_token"] == "new_refresh"


def test_auth_routes_require_header_and_local_origin():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chatgpt_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
    assert client.post("/api/ai/connect", json={}).status_code == 403
    assert client.post("/api/ai/connect", json={}, headers={"X-Journal-Request": "1", "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/ai/connect", json={}, headers={"X-Journal-Request": "1", "Origin": "http://localhost:3010"}).status_code == 200
    assert client.post("/api/ai/connect", json={}, headers={"X-Journal-Request": "1", "Host": "evil.example"}).status_code == 403


def test_oauth_queries_are_redacted():
    import logging
    from chatgpt_routes import RedactOAuthQueries
    record = logging.LogRecord("uvicorn.access", 20, "", 1, "%s %s %s %s %s",
                               ("127.0.0.1", "GET", "/auth/callback?code=secret&state=value", "1.1", 200), None)
    RedactOAuthQueries().filter(record)
    assert record.args[2] == "/auth/callback"


def test_localhost_start_redirects_before_setting_cookie():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chatgpt_routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, base_url="http://localhost:8010", client=("127.0.0.1", 50000))
    path = coach.begin_connect()["start_path"]
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:8010" + path
    assert "set-cookie" not in response.headers
    response = client.get(response.headers["location"], follow_redirects=False)
    assert response.headers["location"].startswith(coach.AUTHORIZE + "?")
    assert "HttpOnly" in response.headers["set-cookie"]


def test_old_request_cannot_verify_new_model(monkeypatch):
    seed()
    lines = "\n".join(events({"type": "response.output_text.delta", "delta": "Ready"},
                            {"type": "response.completed", "response": {"status": "completed"}})) + "\n"
    def send(request):
        with coach._locked_store() as store:
            store["registrations"]["registered"]["model"] = "new_model"
            coach._write_store(store)
        return httpx.Response(200, content=lines)
    client_type = httpx.Client
    monkeypatch.setattr(coach.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(send), **kwargs))
    assert coach.generate_text(messages=[{"role": "user", "content": "Question"}]) == "Ready"
    assert coach.status()["verification"] == "not_tested"
