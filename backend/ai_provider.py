"""Explicit AI provider dispatch. Never falls back to another provider or credential."""
import base64
import binascii
import re

import httpx

import ai_credentials as credentials
import chatgpt_provider
from chatgpt_provider import CoachError

PROVIDERS = {
    "chatgpt": {"label": "ChatGPT plan", "billing": "Uses your connected ChatGPT plan."},
    "openai": {"label": "OpenAI API", "billing": "Separate OpenAI API billing; not included in ChatGPT."},
    "anthropic": {"label": "Anthropic Claude", "billing": "Separate Anthropic API billing."},
    "openrouter": {"label": "OpenRouter", "billing": "Uses your OpenRouter account and model pricing."},
}
DEFAULT_MODELS = {"openai": "gpt-4.1-mini", "anthropic": "claude-sonnet-4-5",
                  "openrouter": "openai/gpt-4.1-mini"}
BASE_URLS = {"openai": "https://api.openai.com/v1", "anthropic": "https://api.anthropic.com/v1",
             "openrouter": "https://openrouter.ai/api/v1"}
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")


class ProviderError(CoachError):
    """Keep the shared exception handler without a ChatGPT-only usage link."""
    def detail(self):
        return {"message": str(self), "code": self.code, "request_id": self.request_id}


def _provider(provider, api_only=False):
    if provider not in PROVIDERS or (api_only and provider == "chatgpt"):
        raise ProviderError("Choose a supported API provider in Settings." if api_only else
                         "Choose a supported AI provider in Settings.", "invalid_provider", 400)
    return provider


def _model_slug(value):
    if not isinstance(value, str) or not _MODEL_ID.fullmatch(value.strip()):
        raise ProviderError("Enter a valid model ID from the provider.", "invalid_model", 400)
    return value.strip()


def _known_vision(provider, model):
    if provider == "openrouter":
        return model == DEFAULT_MODELS[provider]
    if provider == "anthropic":
        return model.startswith(("claude-3", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4"))
    return (model.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "gpt-6", "o3", "o4"))
            and not any(part in model for part in ("audio", "realtime", "transcribe", "tts", "search", "codex", "deep-research", "o3-mini")))


def _metadata(provider, config):
    model = config.get("model") or DEFAULT_MODELS.get(provider)
    return {"id": provider, **PROVIDERS[provider], "model": model,
            "configured": bool(config.get("api_key") and model), "key_present": bool(config.get("api_key")),
            "supports_images": config.get("capabilities", {}).get(model, _known_vision(provider, model or "")),
            "credential_storage": credentials.storage_description(),
            "verification": config.get("verification", "not_tested"), "message": config.get("message")}


def provider_status(provider):
    _provider(provider)
    if provider == "chatgpt":
        try:
            state = chatgpt_provider.status()
        except CoachError:
            # A moved/unreadable OAuth store must not hide the independent API settings.
            state = {"verification": "unavailable", "message": "The saved ChatGPT connection is unavailable on this computer."}
        return {"id": provider, **PROVIDERS[provider], "model": state.get("model"), "key_present": False,
                "configured": bool(state.get("plan_usage_enabled") and state.get("model")),
                "supports_images": True, "credential_storage": credentials.storage_description(),
                "verification": state.get("verification", "not_tested"), "message": state.get("message")}
    with credentials.locked_store() as store:
        return _metadata(provider, store["providers"].get(provider, {}))


def status():
    with credentials.locked_store() as store:
        active = _provider(store.get("active_provider", "chatgpt"))
        entries = [_metadata(p, store["providers"].get(p, {})) for p in DEFAULT_MODELS]
    return {"active_provider": active, "providers": [provider_status("chatgpt"), *entries]}


def select_provider(provider):
    _provider(provider)
    with credentials.locked_store() as store:
        store["active_provider"] = provider
        credentials.write(store)
    return status()


def configure(provider, model, api_key=None):
    _provider(provider, api_only=True)
    model = _model_slug(model)
    key = api_key.strip() if isinstance(api_key, str) else api_key
    if key and (not isinstance(key, str) or len(key) < 10 or len(key) > 4096 or
                not all(33 <= ord(c) <= 126 for c in key)):
        raise ProviderError("Enter a valid API key without spaces or control characters.", "invalid_api_key", 400)
    with credentials.locked_store() as store:
        config = store["providers"].setdefault(provider, {})
        config["model"] = model
        if key:
            config["api_key"] = key
        config["verification"] = "not_tested"
        config.pop("message", None)
        credentials.write(store)
        return _metadata(provider, config)


def remove_key(provider):
    _provider(provider, api_only=True)
    with credentials.locked_store() as store:
        config = store["providers"].setdefault(provider, {})
        config.pop("api_key", None)
        config["verification"] = "not_tested"
        config.pop("message", None)
        credentials.write(store)
        return _metadata(provider, config)


def _config(provider):
    with credentials.locked_store() as store:
        return dict(store["providers"].get(provider, {}))


def _request(provider, key, path, payload=None, params=None):
    headers = {"Accept": "application/json"}
    if provider == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = "Bearer " + key
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=15), follow_redirects=False) as client:
            response = client.request("POST" if payload is not None else "GET", BASE_URLS[provider] + path,
                                      headers=headers, json=payload, params=params)
    except httpx.TimeoutException:
        raise ProviderError("The AI provider timed out. Try again.", "provider_timeout", 504) from None
    except httpx.HTTPError:
        raise ProviderError("The AI provider could not be reached. Check your connection.", "provider_unavailable", 503) from None
    # Never expose upstream bodies, headers, URLs containing secrets, or exception text.
    if response.status_code in (401, 403):
        raise ProviderError("The provider rejected this API key or model access. Check Settings.", "provider_auth_error", 401)
    if response.status_code in (402, 429):
        raise ProviderError("The provider's credit or usage limit was reached. Check that provider's account.", "provider_usage_limit", 429)
    if not 200 <= response.status_code < 300:
        raise ProviderError("The selected provider could not complete the request. Check the model and try again.",
                         "provider_request_failed", 502)
    try:
        data = response.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("invalid response")
        return data
    except (ValueError, TypeError):
        raise ProviderError("The provider returned an invalid response.", "invalid_provider_response", 502) from None


def list_models(provider):
    _provider(provider, api_only=True)
    config = _config(provider)
    if not config.get("api_key"):
        slug = DEFAULT_MODELS[provider]
        return {"models": [{"slug": slug, "display_name": slug, "supports_images": _known_vision(provider, slug)}],
                "source": "defaults", "manual_entry": True}
    models, after = [], None
    # Anthropic paginates; other providers return their available catalog in one response.
    for _ in range(20):
        params = ({"limit": 100, **({"after_id": after} if after else {})} if provider == "anthropic" else None)
        data = _request(provider, config["api_key"], "/models", params=params)
        rows = data.get("data")
        if not isinstance(rows, list):
            raise ProviderError("The provider returned an invalid model list.", "invalid_provider_response", 502)
        for item in rows:
            if not isinstance(item, dict):
                continue
            slug = item.get("id")
            if not isinstance(slug, str) or not _MODEL_ID.fullmatch(slug):
                continue
            if provider == "openai" and (not slug.startswith(("gpt-", "o1", "o3", "o4")) or
                any(part in slug for part in ("audio", "realtime", "transcribe", "tts", "search", "codex", "deep-research", "image"))):
                continue
            architecture = item.get("architecture") or {}
            if provider == "openrouter" and "text" not in architecture.get("output_modalities", ["text"]):
                continue
            vision = ("image" in architecture.get("input_modalities", []) if provider == "openrouter"
                      else _known_vision(provider, slug))
            models.append({"slug": slug, "display_name": item.get("display_name") or item.get("name") or slug,
                           "supports_images": vision})
        if provider != "anthropic" or not data.get("has_more"):
            break
        next_id = data.get("last_id")
        if not next_id or next_id == after:
            raise ProviderError("The provider returned an incomplete model list.", "invalid_provider_response", 502)
        after = next_id
    with credentials.locked_store() as store:
        current = store["providers"].get(provider, {})
        if current.get("api_key") == config["api_key"]:
            current["capabilities"] = {m["slug"]: m["supports_images"] for m in models}
            credentials.write(store)
    return {"models": sorted(models, key=lambda m: m["slug"]), "source": "live", "manual_entry": True}


def _messages(messages, provider, supports_images):
    normalized = []
    if not isinstance(messages, list) or not messages:
        raise ProviderError("Provide at least one coaching message.", "invalid_history", 400)
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant"}:
            raise ProviderError("Chat history must contain user and assistant messages.", "invalid_history", 400)
        role, content = message["role"], message.get("content", "")
        if isinstance(content, str):
            normalized.append({"role": role, "content": content})
            continue
        if not isinstance(content, list) or not content:
            raise ProviderError("This coaching input is not supported.", "unsupported_input", 400)
        blocks = []
        for block in content:
            if not isinstance(block, dict):
                raise ProviderError("This coaching input is not supported.", "unsupported_input", 400)
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                # Assistant history uses output_text in Responses; user input uses input_text.
                kind = ("output_text" if role == "assistant" else "input_text") if provider == "openai" else "text"
                blocks.append({"type": kind, "text": block["text"]})
            elif block.get("type") == "image" and role == "user":
                if not supports_images:
                    raise ProviderError("This model has no confirmed image support. Choose an image-capable model in Settings and refresh models.",
                                     "unsupported_image_model", 400)
                source = block.get("source") or {}
                if (not isinstance(source, dict) or source.get("type") != "base64" or
                    source.get("media_type") not in {"image/png", "image/jpeg", "image/webp", "image/gif"} or
                    not isinstance(source.get("data"), str)):
                    raise ProviderError("This diary image format is not supported.", "unsupported_image", 400)
                try:
                    if not base64.b64decode(source["data"], validate=True):
                        raise ValueError("empty")
                except (ValueError, binascii.Error):
                    raise ProviderError("The diary image data is invalid.", "unsupported_image", 400) from None
                url = "data:" + source["media_type"] + ";base64," + source["data"]
                if provider == "openai":
                    blocks.append({"type": "input_image", "image_url": url})
                elif provider == "openrouter":
                    blocks.append({"type": "image_url", "image_url": {"url": url}})
                else:
                    blocks.append({"type": "image", "source": {k: source[k] for k in ("type", "media_type", "data")}})
            else:
                raise ProviderError("This coaching input is not supported.", "unsupported_input", 400)
        normalized.append({"role": role, "content": blocks})
    return normalized


def _response_text(provider, data):
    try:
        if provider == "openai":
            if data.get("status") != "completed":
                raise ValueError("incomplete")
            messages = [item for item in data["output"] if item.get("type") == "message"]
            if any(item.get("status") not in (None, "completed") for item in messages):
                raise ValueError("incomplete message")
            blocks = [block for item in messages for block in item["content"]]
            if any(block.get("type") == "refusal" for block in blocks):
                raise ValueError("refusal")
            text = "\n".join(block["text"] for block in blocks if block.get("type") == "output_text")
        elif provider == "anthropic":
            if data.get("type") != "message" or data.get("stop_reason") != "end_turn":
                raise ValueError("incomplete")
            if (data.get("stop_details") or {}).get("type") == "refusal":
                raise ValueError("refusal")
            text = "\n".join(block["text"] for block in data["content"] if block.get("type") == "text")
        else:
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal") or choice["message"].get("tool_calls"):
                raise ValueError("incomplete")
            text = choice["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty")
        return text.strip()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise ProviderError("The provider did not return a complete text response. Try again or choose another model.",
                         "incomplete_provider_response", 502) from None


def _generate(provider, config, system, messages):
    if provider == "chatgpt":
        return chatgpt_provider.generate_text(system=system, messages=messages)
    meta = _metadata(provider, config)
    if not meta["configured"]:
        raise ProviderError("Add an API key and model for the selected provider in Settings.", "provider_not_configured", 409)
    normalized = _messages(messages, provider, meta["supports_images"])
    payload = {"model": meta["model"]}
    if provider == "openai":
        payload.update({"instructions": system, "input": normalized, "store": False, "max_output_tokens": 16000})
        path = "/responses"
    elif provider == "anthropic":
        payload.update({"messages": normalized, "max_tokens": 8192})
        if system:
            payload["system"] = system
        path = "/messages"
    else:
        payload.update({"messages": ([{"role": "system", "content": system}] if system else []) + normalized,
                        "max_tokens": 8192, "provider": {"allow_fallbacks": False}})
        path = "/chat/completions"
    return _response_text(provider, _request(provider, config["api_key"], path, payload))


def generate_text(system="", messages=None):
    with credentials.locked_store() as store:
        provider = _provider(store.get("active_provider", "chatgpt"))
        config = dict(store["providers"].get(provider, {}))
    return _generate(provider, config, system, messages)


def verify(provider):
    _provider(provider, api_only=True)
    config = _config(provider)
    try:
        response = _generate(provider, config, "Reply exactly: AI connection is working.",
                             [{"role": "user", "content": "Test the connection."}])
    except CoachError as error:
        with credentials.locked_store() as store:
            current = store["providers"].get(provider, {})
            if current.get("api_key") == config.get("api_key") and current.get("model") == config.get("model"):
                current["verification"], current["message"] = "failed", str(error)
                credentials.write(store)
        raise
    with credentials.locked_store() as store:
        current = store["providers"].get(provider, {})
        if current.get("api_key") == config.get("api_key") and current.get("model") == config.get("model"):
            current["verification"] = "verified"
            current.pop("message", None)
            credentials.write(store)
    # A controlled success message avoids echoing a provider's arbitrary verification output.
    return {"response": "AI connection is working." if response else "", "status": provider_status(provider)}
