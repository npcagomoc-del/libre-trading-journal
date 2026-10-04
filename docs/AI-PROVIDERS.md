# Choose an AI provider

Choose ChatGPT sign-in, OpenAI API, Claude API or OpenRouter in Libre Trading Journal. Brain, diary analysis, insights and reviews use the provider selected in Settings. Imports, calculations and ordinary reports work without AI.

## Set up your connection

Open **More → Settings → AI connection → AI provider**.

| Choice | Credential and billing |
|---|---|
| ChatGPT sign-in | Existing ChatGPT plan connection. Model availability, permissions and usage limits come from the account. No API key required. |
| OpenAI API key (ChatGPT API) | OpenAI Platform key. This is separate API billing, independent of a ChatGPT subscription. |
| Claude API key | Direct Anthropic API key. A Claude subscription and an OpenRouter key are not direct Anthropic API credentials. |
| OpenRouter API key | OpenRouter key and a model ID from its catalog, including supported Claude models. Uses OpenRouter pricing and access. |

Changing the dropdown changes the active provider. If it is not configured, coaching asks for setup instead of silently using a different provider. Configurations for the other choices remain saved, and selecting an API provider does not disconnect ChatGPT.

### ChatGPT sign-in

1. Select **ChatGPT sign-in**.
2. Use **Continue with ChatGPT** and finish the browser sign-in and plan authorization.
3. Return to Settings, select an available model, then **Test connection**.
4. A completed response verifies inference. Signing in alone does not prove model access works.

Existing tokens and registrations remain in their original installation store. Keep the backend on port 8010 for its existing callback. Use **Manage ChatGPT usage** for plan limits and credit permissions. The app does not automatically switch to API billing if plan access fails.

### API-key connection

1. Select **OpenAI API key**, **Claude API key**, or **OpenRouter API key**.
2. Paste that provider's key into the password field. Do not paste it into Brain or public bug reports.
3. Choose or enter the exact **Model ID**. In OpenRouter, use its full catalog slug rather than a direct Anthropic model ID.
4. Click **Save settings**. Saving records configuration; it does not make an inference request or verify access.
5. Use **Refresh models** to retrieve suggestions and model capabilities. Available models and access depend on the provider. Manual model IDs are supported.
6. Click **Test connection**. This sends a small request and can consume paid API usage. A completed response changes the verification status.
7. Open Brain and confirm the displayed provider/model before sending journal context.

Leave the key field blank when changing only the model: it keeps the saved key. **Remove API key → Confirm remove key** removes that provider's saved key; its model remains selected. An active provider without a key stops coaching until configured again.

## Images and model capabilities

Typed diaries and Brain use text. Screenshots require a model with confirmed image support. Settings still validates model capabilities and reports unsupported image models; refresh the model list when a manually entered OpenRouter model is unknown. A successful text test does not prove image analysis works.

If screenshot analysis is unsupported, choose a compatible model or upload typed notes. The diary upload can save the entry before AI analysis fails; inspect Diary before reuploading to avoid duplicates. Stored review content is cached and is not automatically regenerated merely because you switch provider. Brain messages remain session state and disappear after reload.

## Privacy and storage

- Relevant journal context and supported images go to the selected service. For OpenRouter, requests also go through its routed model provider. Do not use coaching for information you do not intend to send there.
- API keys and provider selection are stored under `%LOCALAPPDATA%\TradingJournalAI\ai-providers\` on Windows, outside this checkout and the trading database. The file is protected with Windows DPAPI for the current Windows user.
- On other platforms, the store is a user-restricted file (0600) under `~/.config/TradingJournalAI/ai-providers/`; it is **not encrypted** by this implementation. The UI describes this limitation.
- The browser does not persist keys in local storage. API status responses contain configuration metadata, not secret values. The password input is cleared after a successful save.
- Downloaded journal backups exclude keys, OAuth tokens, and .env files. Reconnect services after moving machines. Restoring a journal on the same installation does not replace its AI credentials or active provider.
- No automatic fallback to another API provider or key is performed. OpenRouter provider-endpoint fallback is disabled for these requests.

## Error recovery

| Symptom | What to do |
|---|---|
| Setup needed / provider not configured | Select the intended provider, enter its own key and model, then save. |
| Authentication or model-access error | Confirm key provider, key validity, and model access. An OpenRouter key belongs in OpenRouter. Replace the key through Settings if necessary. |
| Credits / usage limit | Review the selected provider's billing or quota. ChatGPT plan controls apply only to ChatGPT sign-in. |
| Unknown model / unsupported image model | Use the exact provider model ID; refresh models and choose an image-capable model for screenshots. |
| Timeout / unavailable provider | Check connection and provider availability, then retry deliberately. No automatic paid provider switch occurs. |
| Incomplete or invalid analysis | Keep the saved diary, inspect whether it already exists, and select a suitable model. An incomplete response is not accepted as a successful test. |
| Credential storage error | Check local file permissions/Windows user context. Do not publish store files. Keep existing stores while diagnosing; reconnect through Settings when required. |

See [general troubleshooting](TROUBLESHOOTING.md) and [backup/restore](BACKUP-RESTORE.md).

## Implementation references

[ai_provider.py](../backend/ai_provider.py) handles provider dispatch/transports, [ai_credentials.py](../backend/ai_credentials.py) handles installation storage, and [ai_provider_routes.py](../backend/ai_provider_routes.py) adds local configuration endpoints. Existing [ChatGPT OAuth](../backend/chatgpt_provider.py) remains separate. [AIProviderSettings.js](../frontend/src/components/AIProviderSettings.js) and [Brain.js](../frontend/src/components/Brain.js) are the UI entry points.

Official contracts: [OpenAI Responses text](https://developers.openai.com/api/docs/guides/text), [ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source), [Claude Messages](https://platform.claude.com/docs/en/api/messages/create), and [OpenRouter](https://openrouter.ai/docs/quickstart). Provider APIs and model availability can change; implementation tests use mock responses rather than real account inference.
