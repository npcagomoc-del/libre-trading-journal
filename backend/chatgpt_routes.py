"""Local connection UI endpoints; OAuth credentials never leave the backend."""
import html
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import chatgpt_provider as provider

router = APIRouter()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class RedactOAuthQueries(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            if isinstance(values[2], str) and values[2].split("?", 1)[0] in {"/auth/start", "/auth/callback"}:
                values[2] = values[2].split("?", 1)[0]
                record.args = tuple(values)
        return True


logging.getLogger("uvicorn.access").addFilter(RedactOAuthQueries())


def require_local(request):
    if not request.client or request.client.host not in LOCAL_HOSTS or request.url.hostname not in LOCAL_HOSTS:
        raise HTTPException(403, "Journal connection and data controls are available only on this computer.")
    origin = request.headers.get("origin")
    if origin and (urlparse(origin).scheme != "http" or urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}):
        raise HTTPException(403, "Open the journal on localhost to use its connection and data controls.")


def require_mutation(request):
    require_local(request)
    if request.headers.get("x-journal-request") != "1":
        raise HTTPException(403, "Use the journal's connection and data controls.")


class ConnectRequest(BaseModel):
    registration_id: str | None = None


class ModelRequest(BaseModel):
    slug: str


@router.get("/api/ai/status")
def ai_status(request: Request):
    require_local(request)
    return provider.status()


@router.post("/api/ai/connect")
def connect(request: Request, body: ConnectRequest):
    require_mutation(request)
    return provider.begin_connect(body.registration_id)


@router.get("/auth/start")
def auth_start(request: Request, ticket: str):
    require_local(request)
    if request.url.hostname != "127.0.0.1":
        # The OAuth cookie and callback must share a host. Do not consume yet.
        return RedirectResponse(str(request.url.replace(hostname="127.0.0.1")), status_code=302,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    url, browser_id = provider.start_authorization(ticket)
    response = RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.set_cookie("journal_oauth", browser_id, httponly=True, samesite="lax", max_age=600, path="/auth")
    return response


@router.get("/auth/callback")
def auth_callback(request: Request):
    require_local(request)
    query = request.query_params
    try:
        enabled = provider.complete_authorization(query.get("state"), request.cookies.get("journal_oauth"),
                                                   query.get("code"), query.get("client_id"), query.get("error"))
        title = "ChatGPT connected" if enabled else "ChatGPT plan permission is needed"
        message = ("Return to Libre Trading Journal and choose a model, then test the connection."
                   if enabled else "You signed in, but did not enable ChatGPT plan usage. Reconnect from Settings to enable it.")
    except provider.CoachError as exc:
        title, message = "Connection not completed", str(exc)
    response = HTMLResponse("<!doctype html><html><head><meta charset='utf-8'><title>Libre Trading Journal</title></head>"
                            "<body style='font:18px system-ui;max-width:600px;margin:15vh auto;padding:24px'>"
                            f"<h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
                            "<p><a href='http://localhost:3010'>Return to the journal</a></p></body></html>",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                     "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Frame-Options": "DENY"})
    response.delete_cookie("journal_oauth", path="/auth")
    return response


@router.get("/api/ai/models")
def models(request: Request):
    require_local(request)
    return {"models": provider.list_models()}


@router.put("/api/ai/model")
def model(request: Request, body: ModelRequest):
    require_mutation(request)
    return provider.select_model(body.slug)


@router.post("/api/ai/disconnect")
def disconnect(request: Request):
    require_mutation(request)
    return provider.disconnect()


@router.post("/api/ai/verify")
def verify(request: Request):
    require_mutation(request)
    text = provider.generate_text("You are verifying the connection. Reply exactly: ChatGPT connection is working.",
                                  [{"role": "user", "content": "Test the connection."}])
    return {"response": text, "status": provider.status()}
