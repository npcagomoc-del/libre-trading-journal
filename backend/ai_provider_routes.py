"""Local-only API provider controls. ChatGPT OAuth controls remain separate."""
from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, SecretStr

import ai_provider as provider
from chatgpt_routes import require_local, require_mutation

class PrivateValidationRoute(APIRoute):
    """Pydantic validation inputs can contain the submitted key; never echo them."""
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": {
                    "message": "Provide a model ID and a text API key, if updating the key.",
                    "code": "invalid_provider_settings"}})
        return private_handler


router = APIRouter(route_class=PrivateValidationRoute)


class ProviderRequest(BaseModel):
    provider: str


class ProviderConfigRequest(BaseModel):
    model: str
    api_key: SecretStr | None = None


@router.get("/api/ai/providers")
def providers(request: Request):
    require_local(request)
    return provider.status()


@router.put("/api/ai/provider")
def select(request: Request, body: ProviderRequest):
    require_mutation(request)
    return provider.select_provider(body.provider)


@router.put("/api/ai/providers/{provider_id}/config")
def configure(provider_id: str, request: Request, body: ProviderConfigRequest):
    require_mutation(request)
    return provider.configure(provider_id, body.model, body.api_key.get_secret_value() if body.api_key else None)


@router.delete("/api/ai/providers/{provider_id}/config")
def remove(provider_id: str, request: Request):
    require_mutation(request)
    return provider.remove_key(provider_id)


@router.get("/api/ai/providers/{provider_id}/models")
def models(provider_id: str, request: Request):
    require_local(request)
    return provider.list_models(provider_id)


@router.post("/api/ai/providers/{provider_id}/verify")
def verify(provider_id: str, request: Request):
    require_mutation(request)
    return provider.verify(provider_id)
