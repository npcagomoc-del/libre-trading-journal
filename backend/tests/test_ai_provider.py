"""Provider isolation, transport contracts, credential secrecy; no live inference or stores."""
import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_credentials as storage
import ai_provider as ai
import chatgpt_provider as chatgpt
from ai_provider_routes import router

SECRET = "sk-synthetic-test-secret-not-a-real-key"
MESSAGES = [{"role": "user", "content": [{"type": "text", "text": "Read this diary"}, {
    "type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aW1hZ2U="}}]}]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "storage_dir", lambda: tmp_path / "providers")
    monkeypatch.setattr(chatgpt, "_storage_dir", lambda: tmp_path / "chatgpt")
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network access")
    monkeypatch.setattr(ai.httpx, "Client", forbidden)


def configure(provider="openai", model=None):
    ai.configure(provider, model or ai.DEFAULT_MODELS[provider], SECRET)
    ai.select_provider(provider)


def mock_transport(monkeypatch, body, status=200):
    seen = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].connect == 15
            assert kwargs["timeout"].read == 120
            assert kwargs["follow_redirects"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def request(self, method, url, **kwargs):
            seen.append((method, url, kwargs))
            return httpx.Response(status, json=body, request=httpx.Request(method, url))
    monkeypatch.setattr(ai.httpx, "Client", Client)
    return seen


def complete(provider):
    if provider == "openai":
        return {"status": "completed", "output": [{"type": "message", "status": "completed",
                 "content": [{"type": "output_text", "text": "Coaching complete"}]}]}
    if provider == "anthropic":
        return {"type": "message", "stop_reason": "end_turn", "content": [{"type": "text", "text": "Coaching complete"}]}
    return {"choices": [{"finish_reason": "stop", "message": {"content": "Coaching complete"}}]}


def test_default_delegates_chatgpt_and_preserves_oauth(monkeypatch):
    calls = []
    monkeypatch.setattr(chatgpt, "generate_text", lambda **kwargs: calls.append(kwargs) or "existing flow")
    monkeypatch.setenv("OPENAI_API_KEY", "ignored-environment-key")
    assert ai.generate_text("Coach", MESSAGES) == "existing flow"
    assert calls == [{"system": "Coach", "messages": MESSAGES}]
    assert ai.status()["active_provider"] == "chatgpt"
    configure()
    ai.select_provider("chatgpt")
    assert ai.generate_text("Coach", MESSAGES) == "existing flow"
    assert len(calls) == 2


def test_selection_and_secrets_persist_separately(tmp_path):
    configure()
    ai.configure("openai", "gpt-4.1", "   ")
    assert ai._config("openai")["api_key"] == SECRET
    summary = ai.status()
    assert summary["active_provider"] == "openai"
    item = next(p for p in summary["providers"] if p["id"] == "openai")
    assert item["key_present"] and item["configured"] and item["model"] == "gpt-4.1"
    assert SECRET not in json.dumps(summary)
    assert "api_key" not in json.dumps(summary)
    raw = (tmp_path / "providers" / "providers.bin").read_bytes()
    if os.name == "nt":
        assert SECRET.encode() not in raw
    else:
        assert (tmp_path / "providers" / "providers.bin").stat().st_mode & 0o777 == 0o600
    ai.remove_key("openai")
    assert not ai.provider_status("openai")["configured"]
    assert ai.status()["active_provider"] == "openai"
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text("Coach", MESSAGES)
    assert error.value.code == "provider_not_configured"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openrouter"])
def test_text_image_transports(provider, monkeypatch):
    configure(provider)
    seen = mock_transport(monkeypatch, complete(provider))
    assert ai.generate_text("Trading coach", MESSAGES) == "Coaching complete"
    method, url, options = seen[0]
    assert method == "POST" and url.startswith(ai.BASE_URLS[provider])
    payload = options["json"]
    assert payload["model"] == ai.DEFAULT_MODELS[provider]
    if provider == "anthropic":
        assert options["headers"]["x-api-key"] == SECRET
        assert options["headers"]["anthropic-version"] == "2023-06-01"
        assert payload["system"] == "Trading coach"
        assert payload["messages"] == MESSAGES
    else:
        assert options["headers"]["Authorization"] == "Bearer " + SECRET
        if provider == "openai":
            assert payload["store"] is False
            assert payload["instructions"] == "Trading coach"
            assert payload["input"][0]["content"][1] == {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}
        else:
            assert payload["provider"]["allow_fallbacks"] is False
            assert payload["messages"][0] == {"role": "system", "content": "Trading coach"}
            assert payload["messages"][1]["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U="}}


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openrouter"])
def test_incomplete_responses_never_accepted(provider, monkeypatch):
    configure(provider)
    body = complete(provider)
    if provider == "openai":
        body["status"] = "incomplete"
    elif provider == "anthropic":
        body["stop_reason"] = "max_tokens"
    else:
        body["choices"][0]["finish_reason"] = "length"
    mock_transport(monkeypatch, body)
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=[{"role": "user", "content": "Hello"}])
    assert error.value.code == "incomplete_provider_response"


@pytest.mark.parametrize("status,code", [(401, "provider_auth_error"), (403, "provider_auth_error"),
    (402, "provider_usage_limit"), (429, "provider_usage_limit"), (500, "provider_request_failed"), (302, "provider_request_failed")])
def test_upstream_errors_are_sanitized_without_fallback(status, code, monkeypatch):
    configure()
    called = []
    monkeypatch.setattr(chatgpt, "generate_text", lambda **kwargs: called.append(kwargs))
    seen = mock_transport(monkeypatch, {"error": {"message": SECRET}}, status)
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=[{"role": "user", "content": "Hello"}])
    assert error.value.code == code and SECRET not in str(error.value.detail())
    assert "usage_url" not in error.value.detail()
    assert len(seen) == 1 and not called


def test_unknown_image_model_fails_before_request():
    configure("openrouter", "vendor/new-text-model")
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=MESSAGES)
    assert error.value.code == "unsupported_image_model"


def test_timeout_is_sanitized(monkeypatch):
    configure()
    class TimeoutClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            raise httpx.ReadTimeout(SECRET)
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(ai.httpx, "Client", TimeoutClient)
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=[{"role": "user", "content": "Hello"}])
    assert error.value.code == "provider_timeout" and SECRET not in str(error.value)


@pytest.mark.parametrize("provider,body", [("openai", {"status": "completed", "output": []}),
    ("anthropic", {"type": "message", "stop_reason": "end_turn", "content": []}),
    ("openrouter", {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]}),
    ("openai", {"error": {"message": SECRET}})])
def test_empty_or_error_responses_fail(provider, body, monkeypatch):
    configure(provider)
    mock_transport(monkeypatch, body)
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=[{"role": "user", "content": "Hello"}])
    assert SECRET not in str(error.value.detail())


def test_anthropic_model_pagination(monkeypatch):
    configure("anthropic")
    calls = []
    def request(provider, key, path, **kwargs):
        calls.append(kwargs["params"])
        if len(calls) == 1:
            return {"data": [{"id": "claude-sonnet-4-5"}], "has_more": True, "last_id": "claude-sonnet-4-5"}
        return {"data": [{"id": "claude-opus-4-1"}], "has_more": False}
    monkeypatch.setattr(ai, "_request", request)
    assert len(ai.list_models("anthropic")["models"]) == 2
    assert calls[1]["after_id"] == "claude-sonnet-4-5"


def test_assistant_block_history_uses_response_output_type(monkeypatch):
    configure()
    seen = mock_transport(monkeypatch, complete("openai"))
    ai.generate_text(messages=[{"role": "assistant", "content": [{"type": "text", "text": "Prior answer"}]},
                               {"role": "user", "content": "Follow up"}])
    assert seen[0][2]["json"]["input"][0]["content"] == [{"type": "output_text", "text": "Prior answer"}]


def test_openrouter_discovery_enables_vision(monkeypatch):
    configure("openrouter", "vendor/new-model")
    mock_transport(monkeypatch, {"data": [{"id": "vendor/new-model", "name": "New model", "architecture": {
        "input_modalities": ["text", "image"], "output_modalities": ["text"]}},
        {"id": "vendor/image-generator", "architecture": {"output_modalities": ["image"]}}]})
    result = ai.list_models("openrouter")
    assert result["models"] == [{"slug": "vendor/new-model", "display_name": "New model", "supports_images": True}]
    assert result["source"] == "live" and ai.provider_status("openrouter")["supports_images"]
    mock_transport(monkeypatch, complete("openrouter"))
    assert ai.generate_text(messages=MESSAGES) == "Coaching complete"


def test_default_models_offline_and_openai_filter(monkeypatch):
    assert ai.list_models("openai")["source"] == "defaults"
    configure()
    mock_transport(monkeypatch, {"data": [{"id": item} for item in ["gpt-4.1", "tts-1", "gpt-4o-audio-preview", "text-embedding-3-small", "o3"]]})
    assert [m["slug"] for m in ai.list_models("openai")["models"]] == ["gpt-4.1", "o3"]


def test_invalid_key_is_rejected_without_exposing_it():
    with pytest.raises(ai.CoachError) as error:
        ai.configure("openai", "gpt-4.1", SECRET + "\nHeader: bad")
    assert error.value.code == "invalid_api_key" and SECRET not in str(error.value)


def test_corrupt_store_fails_closed(tmp_path):
    folder = tmp_path / "providers"
    folder.mkdir()
    (folder / "providers.bin").write_bytes(b"not valid")
    with pytest.raises(ai.CoachError) as error:
        ai.generate_text(messages=MESSAGES)
    assert error.value.code == "credential_storage_error"


def test_verify_metadata_avoids_echo_and_does_not_switch(monkeypatch):
    ai.configure("openai", "gpt-4.1", SECRET)
    body = complete("openai")
    body["output"][0]["content"][0]["text"] = SECRET
    mock_transport(monkeypatch, body)
    result = ai.verify("openai")
    assert SECRET not in json.dumps(result)
    assert result["status"]["verification"] == "verified"
    assert ai.status()["active_provider"] == "chatgpt"
    mock_transport(monkeypatch, {"error": SECRET}, 401)
    with pytest.raises(ai.CoachError):
        ai.verify("openai")
    assert ai.provider_status("openai")["verification"] == "failed"
    assert SECRET not in json.dumps(ai.provider_status("openai"))


def test_unreadable_oauth_store_does_not_hide_api_settings(monkeypatch):
    configure()
    def unavailable():
        raise ai.CoachError("Unavailable OAuth store", "credential_storage_error", 503)
    monkeypatch.setattr(chatgpt, "status", unavailable)
    result = ai.status()
    assert result["active_provider"] == "openai"
    assert result["providers"][0]["configured"] is False


def client():
    app = FastAPI()
    app.include_router(router)
    @app.exception_handler(ai.CoachError)
    async def errors(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail()})
    return TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))


def test_routes_local_mutation_guards_and_key_secrecy():
    with client() as api:
        assert api.get("/api/ai/providers").status_code == 200
        payload = {"model": "gpt-4.1", "api_key": SECRET}
        url = "/api/ai/providers/openai/config"
        assert api.put(url, json=payload).status_code == 403
        headers = {"X-Journal-Request": "1"}
        response = api.put(url, json=payload, headers=headers)
        assert response.status_code == 200 and SECRET not in response.text
        assert api.get("/api/ai/providers", headers={"Origin": "https://evil.example"}).status_code == 403
        assert api.put(url, json={"api_key": SECRET}, headers=headers).status_code == 422
        assert SECRET not in api.put(url, json={"api_key": SECRET}, headers=headers).text
        assert api.put("/api/ai/provider", json={"provider": "anthropic"}, headers=headers).json()["active_provider"] == "anthropic"
        assert api.delete(url, headers=headers).json()["key_present"] is False
