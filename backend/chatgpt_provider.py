"""ChatGPT plan OAuth and Responses transport. No API-key billing path.

Contract: https://developers.openai.com/siwc/token-sharing-open-source
Credentials belong to this installation, never to the trading database or browser.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from filelock import FileLock

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN_ENDPOINT = ISSUER + "/api/accounts/oauth/token"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
USAGE_URL = "https://chatgpt.com/settings/usage"
REDIRECT_URI = "http://127.0.0.1:8010/auth/callback"
_thread_lock = threading.RLock()
_pending = {}
_pending_lock = threading.Lock()


class CoachError(Exception):
    def __init__(self, message, code="chatgpt_error", status=502, request_id=None):
        super().__init__(message)
        self.code, self.status, self.request_id = code, status, request_id

    def detail(self):
        return {"message": str(self), "code": self.code, "request_id": self.request_id,
                "usage_url": USAGE_URL}


def _storage_dir():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "TradingJournalAI" / "chatgpt"
    return Path.home() / ".config" / "TradingJournalAI" / "chatgpt"


def _protect(data):
    if os.name == "nt":
        import win32crypt
        return win32crypt.CryptProtectData(data, "Trading Journal AI", None, None, None, 1)
    return data


def _unprotect(data):
    if os.name == "nt":
        import win32crypt
        return win32crypt.CryptUnprotectData(data, None, None, None, 1)[1]
    return data


def _read_store():
    path = _storage_dir() / "connection.bin"
    if not path.exists():
        return {"host_id": "urn:uuid:" + str(uuid.uuid4()), "registrations": {}, "active": None}
    try:
        return json.loads(_unprotect(path.read_bytes()))
    except Exception:
        raise CoachError("ChatGPT credentials could not be opened. Reconnect from Settings.",
                         "credential_storage_error", 503) from None


def _write_store(store):
    folder = _storage_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    blob = _protect(json.dumps(store).encode("utf-8"))
    fd, temp_path = tempfile.mkstemp(dir=folder, prefix="connection-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(blob)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, folder / "connection.bin")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@contextmanager
def _locked_store():
    folder = _storage_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _thread_lock, FileLock(str(folder / "connection.lock"), timeout=30):
        yield _read_store()


def _registration(store):
    return store.get("registrations", {}).get(store.get("active"))


def status():
    with _locked_store() as store:
        reg = _registration(store) or {}
        connected = bool(reg.get("access_token"))
        return {
            "provider": "chatgpt", "connected": connected,
            "plan_usage_enabled": connected and PLAN_SCOPE in reg.get("scopes", []),
            "model": reg.get("model"), "verification": reg.get("verification", "not_tested"),
            "active_registration": store.get("active"),
            "registrations": [{"id": key, "label": item.get("email") or "ChatGPT account",
                               "connected": bool(item.get("access_token"))}
                              for key, item in store.get("registrations", {}).items()],
            "message": reg.get("message"), "error_code": reg.get("error_code"),
            "usage_url": USAGE_URL,
        }


def begin_connect(registration_id=None):
    """Return a short-lived local ticket; never put tokens into frontend JSON."""
    with _locked_store() as store:
        reg = store["registrations"].get(registration_id) if registration_id else None
        if registration_id and not reg:
            raise CoachError("Saved ChatGPT connection not found.", "unknown_connection", 400)
        _write_store(store)  # Persist the host ID before first registration.
        ticket = secrets.token_urlsafe(32)
        attempt = {
            "expires_at": time.time() + 600, "state": secrets.token_urlsafe(32),
            "nonce": secrets.token_urlsafe(32), "verifier": secrets.token_urlsafe(64),
            "browser_id": secrets.token_urlsafe(32), "host_id": store["host_id"],
            "registration_id": registration_id, "registration": dict(reg) if reg else None,
            "redirect_uri": REDIRECT_URI,
        }
    with _pending_lock:
        now = time.time()
        for key in list(_pending):
            if _pending[key]["expires_at"] <= now:
                del _pending[key]
        if len(_pending) >= 20:
            raise CoachError("Too many sign-in attempts. Wait before trying again.", "sign_in_busy", 429)
        _pending[ticket] = attempt
    return {"start_path": "/auth/start?ticket=" + ticket}


def start_authorization(ticket):
    with _pending_lock:
        attempt = _pending.pop(ticket, None)
        if not attempt or attempt["expires_at"] <= time.time():
            raise CoachError("Sign-in link expired. Start again from Settings.", "invalid_state", 400)
        _pending[attempt["state"]] = attempt
    challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt["verifier"].encode()).digest()).decode().rstrip("=")
    reg = attempt["registration"]
    params = {
        "client_id": reg["client_id"] if reg else "dynamic_agent_client",
        "ext_agent_host_id": attempt["host_id"], "response_type": "code",
        "redirect_uri": attempt["redirect_uri"], "scope": SCOPES, "resource": RESOURCE,
        "state": attempt["state"], "nonce": attempt["nonce"],
        "code_challenge_method": "S256", "code_challenge": challenge,
    }
    if reg:
        if reg.get("id_token"):
            params["id_token_hint"] = reg["id_token"]
        if PLAN_SCOPE not in reg.get("scopes", []):
            params["prompt"] = "consent"
    else:
        params["agent_name_hint"] = "Trading Journal AI"
    return AUTHORIZE + "?" + urlencode(params), attempt["browser_id"]


def _discovery():
    try:
        response = httpx.get(ISSUER + "/.well-known/openid-configuration", timeout=20)
        response.raise_for_status()
        data = response.json()
        if data.get("issuer") != ISSUER:
            raise ValueError("issuer")
        for field in ("jwks_uri", "revocation_endpoint"):
            parsed = urlparse(data[field])
            if parsed.scheme != "https" or parsed.netloc != "auth.openai.com":
                raise ValueError("endpoint")
        return data
    except (httpx.HTTPError, ValueError, KeyError):
        raise CoachError("OpenAI sign-in is temporarily unavailable. Try again later.",
                         "discovery_unavailable", 503) from None


def _validate_identity(tokens, client_id, nonce):
    try:
        config = _discovery()
        key = jwt.PyJWKClient(config["jwks_uri"]).get_signing_key_from_jwt(tokens["id_token"]).key
        identity = jwt.decode(tokens["id_token"], key, algorithms=["RS256"],
                              audience=client_id, issuer=ISSUER, leeway=5,
                              options={"require": ["sub", "exp", "iat", "nonce", "iss", "aud"]})
        if not identity.get("sub") or not secrets.compare_digest(str(identity["nonce"]), nonce):
            raise ValueError("identity")
        return identity
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise CoachError("ChatGPT sign-in could not be verified. Start sign-in again.",
                         "invalid_identity", 400) from None


def _token_request(fields):
    try:
        response = httpx.post(TOKEN_ENDPOINT, data=fields, timeout=30)
    except httpx.HTTPError:
        raise CoachError("ChatGPT sign-in could not reach OpenAI. Try again later.", "auth_unavailable", 503) from None
    if response.is_error:
        try:
            code = response.json().get("error", "auth_error")
            if isinstance(code, dict):
                code = code.get("code", "auth_error")
        except ValueError:
            code = "auth_error"
        if code not in {"invalid_grant", "invalid_client", "invalid_refresh_token", "token_expired",
                        "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"}:
            code = "auth_error"
        raise CoachError("ChatGPT authentication failed. Reconnect from Settings.", code, 401)
    tokens = response.json()
    if not tokens.get("access_token") or tokens.get("token_type", "").lower() != "bearer":
        raise CoachError("ChatGPT did not return a valid connection.", "invalid_token_response", 401)
    return tokens


def complete_authorization(state, browser_id, code=None, client_id=None, error=None):
    with _pending_lock:
        attempt = _pending.get(state)
        if (not attempt or attempt["expires_at"] <= time.time() or not browser_id
                or not secrets.compare_digest(attempt["browser_id"], browser_id)):
            raise CoachError("Sign-in expired or could not be verified. Start again from Settings.", "invalid_state", 400)
        del _pending[state]  # Consume before redeeming; replay is impossible.
    if error:
        raise CoachError("ChatGPT connection was not approved. You can try again from Settings.", "access_denied", 400)
    reg = attempt["registration"]
    issued_id = reg["client_id"] if reg else client_id
    if (not code or not issued_id or issued_id == "dynamic_agent_client"
            or (reg and client_id and client_id != issued_id)):
        raise CoachError("ChatGPT registration was incomplete. Start again from Settings.", "invalid_registration", 400)
    tokens = _token_request({"grant_type": "authorization_code", "client_id": issued_id,
                             "code": code, "code_verifier": attempt["verifier"],
                             "redirect_uri": attempt["redirect_uri"], "resource": RESOURCE})
    identity = _validate_identity(tokens, issued_id, attempt["nonce"])
    if reg and identity["sub"] != reg["subject"]:
        raise CoachError("This sign-in belongs to a different ChatGPT account. Add it as a new account.", "account_mismatch", 400)
    scopes = tokens.get("scope", "").split()
    key = hashlib.sha256((ISSUER + "|" + issued_id + "|" + identity["sub"]).encode()).hexdigest()[:24]
    with _locked_store() as store:
        previous = store["registrations"].get(key, {})
        store["registrations"][key] = {
            "issuer": ISSUER, "client_id": issued_id, "subject": identity["sub"],
            "email": identity.get("email"), "scopes": scopes,
            "access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token"),
            "id_token": tokens["id_token"], "expires_at": time.time() + int(tokens["expires_in"]),
            "model": previous.get("model"), "verification": "not_tested",
            "session_id": str(uuid.uuid4()),
        }
        store["active"] = key
        _write_store(store)
    return PLAN_SCOPE in scopes


def _access_token(registration_id=None, include_context=False):
    with _locked_store() as store:
        registration_id = registration_id or store.get("active")
        reg = store["registrations"].get(registration_id)
        if not reg or not reg.get("access_token"):
            raise CoachError("Connect ChatGPT in Settings to use the AI coach.", "not_connected", 401)
        if PLAN_SCOPE not in reg.get("scopes", []):
            raise CoachError("Enable use of your ChatGPT plan by reconnecting in Settings.", "plan_usage_disabled", 403)
        if reg.get("expires_at", 0) <= time.time() + 60:
            if not reg.get("refresh_token"):
                raise CoachError("Your ChatGPT connection expired. Reconnect in Settings.", "session_expired", 401)
            try:
                tokens = _token_request({"grant_type": "refresh_token", "client_id": reg["client_id"],
                                         "refresh_token": reg["refresh_token"], "resource": RESOURCE})
            except CoachError as exc:
                if exc.code in {"invalid_grant", "invalid_refresh_token", "token_expired",
                                "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"}:
                    for name in ("access_token", "refresh_token", "id_token"):
                        reg.pop(name, None)
                    _write_store(store)
                raise
            reg.update(access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token", reg["refresh_token"]),
                       expires_at=time.time() + int(tokens["expires_in"]),
                       scopes=tokens.get("scope", " ".join(reg["scopes"])).split())
            if tokens.get("id_token"):
                reg["id_token"] = tokens["id_token"]
            _write_store(store)
            if PLAN_SCOPE not in reg["scopes"]:
                raise CoachError("ChatGPT plan permission is no longer enabled. Reconnect in Settings.", "plan_usage_disabled", 403)
        if include_context:
            return reg["access_token"], registration_id, reg.get("model"), reg.get("session_id")
        return reg["access_token"], registration_id


def _upstream_error(status_code, payload, request_id=None):
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code", "chatgpt_request_failed") if isinstance(error, dict) else "chatgpt_request_failed"
    messages = {
        "subscription_sharing_user_not_eligible": "Your account or workspace is not eligible for ChatGPT plan usage in this app.",
        "subscription_sharing_usage_limit_exceeded": "Your ChatGPT plan or app limit has been reached. Review ChatGPT Usage settings; no API-key fallback was used.",
        "subscription_sharing_usage_unavailable": "ChatGPT usage availability could not be checked. Try again later.",
        "subscription_sharing_unsupported_capability": "The selected model cannot perform this coaching request. Choose another model in Settings.",
    }
    code = code if isinstance(code, str) and re.fullmatch(r"[a-zA-Z0-9_]{1,100}", code) else "chatgpt_request_failed"
    message = messages.get(code, "ChatGPT could not complete this request. Check the connection in Settings and try again.")
    request_id = request_id if isinstance(request_id, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,150}", request_id) else None
    return CoachError(message, code, status_code if 400 <= status_code < 600 else 502, request_id)


def _fetch_models(token, registration_id):
    try:
        response = httpx.get(RESOURCE + "/models", headers={"Authorization": "Bearer " + token}, timeout=30)
    except httpx.HTTPError:
        raise CoachError("ChatGPT models are temporarily unavailable. Try again later.", "models_unavailable", 503) from None
    if response.is_error:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise _upstream_error(response.status_code, payload, response.headers.get("x-request-id"))
    models = [{"slug": item["slug"], "display_name": item.get("display_name", item["slug"])}
              for item in response.json().get("models", [])
              if item.get("visibility") == "list" and item.get("slug")]
    if not models:
        raise CoachError("No ChatGPT models are available for this connection.", "models_unavailable", 403)
    with _locked_store() as store:
        reg = store["registrations"].get(registration_id)
        if reg:
            reg["models"] = models
            if reg.get("model") not in {item["slug"] for item in models}:
                reg["model"] = models[0]["slug"]
                reg["verification"] = "not_tested"
            _write_store(store)
    return models


def list_models():
    token, registration_id = _access_token()
    return _fetch_models(token, registration_id)


def select_model(slug):
    token, registration_id = _access_token()
    models = _fetch_models(token, registration_id)
    if slug not in {item["slug"] for item in models}:
        raise CoachError("Choose a model available to your ChatGPT account.", "invalid_model", 400)
    with _locked_store() as store:
        if store.get("active") != registration_id:
            raise CoachError("The ChatGPT account changed. Select the model again.", "connection_changed", 409)
        reg = store["registrations"][registration_id]
        reg["model"], reg["verification"] = slug, "not_tested"
        _write_store(store)
    return status()


def _input_messages(messages):
    result = []
    for message in messages:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            raise CoachError("Chat history must contain user and assistant messages.", "invalid_history", 400)
        content = message.get("content", "")
        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue
        blocks = []
        for block in content:
            if block.get("type") == "text":
                blocks.append({"type": "input_text", "text": block["text"]})
            elif block.get("type") == "image" and role == "user":
                source = block["source"]
                if source.get("media_type") not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                    raise CoachError("This diary image format is not supported.", "unsupported_image", 400)
                blocks.append({"type": "input_image", "image_url": "data:" + source["media_type"] + ";base64," + source["data"]})
            else:
                raise CoachError("This coaching input is not supported.", "unsupported_input", 400)
        result.append({"role": role, "content": blocks})
    return result


def _stream_text(lines, request_id=None):
    """SSE records can span multiple data lines. A text delta alone is not success."""
    chunks, data = [], []
    for line in lines:
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            continue
        if line != "" or not data:
            continue
        raw, data = "\n".join(data), []
        if raw == "[DONE]":
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            raise CoachError("ChatGPT returned an unreadable stream. Please retry.", "invalid_stream", 502) from None
        kind = event.get("type")
        if kind == "response.output_text.delta":
            chunks.append(event.get("delta", ""))
        elif kind in {"response.failed", "error"}:
            response = event.get("response", event)
            error = response.get("error", event)
            code = error.get("code") if isinstance(error, dict) else None
            status_code = 429 if code == "subscription_sharing_usage_limit_exceeded" else 502
            raise _upstream_error(status_code, {"error": error}, request_id)
        elif kind == "response.incomplete":
            raise CoachError("ChatGPT stopped before completing the response. Try a smaller request.", "incomplete_response", 502)
        elif kind == "response.completed":
            response = event.get("response", {})
            if response.get("status", "completed") != "completed" or response.get("error"):
                raise _upstream_error(502, response, request_id)
            text = "".join(chunks).strip()
            if not text:
                text = "".join(block.get("text", "") for item in response.get("output", [])
                               for block in item.get("content", []) if block.get("type") == "output_text").strip()
            if not text:
                raise CoachError("ChatGPT completed without a coaching answer. Please retry.", "empty_response", 502)
            return text
    raise CoachError("The ChatGPT connection ended before completion. Please retry.", "interrupted_stream", 502)


def generate_text(system="", messages=None):
    token, registration_id, model, session_id = _access_token(include_context=True)
    if not model:
        _fetch_models(token, registration_id)
        with _locked_store() as store:
            model = store["registrations"][registration_id].get("model")
    payload = {"model": model, "instructions": system, "input": _input_messages(messages),
               "store": False, "stream": True}
    try:
        with httpx.Client(timeout=httpx.Timeout(180, connect=20)) as client:
            with client.stream("POST", RESOURCE + "/responses", headers={"Authorization": "Bearer " + token}, json=payload) as response:
                request_id = response.headers.get("x-request-id") or response.headers.get("openai-request-id")
                if response.is_error:
                    response.read()
                    try:
                        body = response.json()
                    except ValueError:
                        body = {}
                    raise _upstream_error(response.status_code, body, request_id)
                text = _stream_text(response.iter_lines(), request_id)
    except httpx.HTTPError:
        raise CoachError("ChatGPT could not be reached or the connection timed out. Please retry.", "connection_unavailable", 503) from None
    with _locked_store() as store:
        reg = store["registrations"].get(registration_id)
        if reg and reg.get("access_token") and reg.get("model") == model and reg.get("session_id") == session_id:
            reg.update(verification="completed", message=None, error_code=None)
            _write_store(store)
    return text


def disconnect():
    confirmed = True
    with _locked_store() as store:
        reg = _registration(store)
        if reg:
            if reg.get("refresh_token"):
                try:
                    response = httpx.post(_discovery()["revocation_endpoint"], timeout=20,
                                          data={"token": reg["refresh_token"], "token_type_hint": "refresh_token", "client_id": reg["client_id"]})
                    confirmed = response.status_code == 200
                except (CoachError, httpx.HTTPError):
                    confirmed = False
            for name in ("access_token", "refresh_token", "id_token"):
                reg.pop(name, None)
            reg["verification"] = "not_tested"
            reg["session_id"] = str(uuid.uuid4())
            _write_store(store)
    return {"disconnected": True, "remote_revocation_confirmed": confirmed,
            "message": "Disconnected." if confirmed else "Disconnected locally. Remote revocation was not confirmed; disconnect this app in ChatGPT settings too."}
