"""Friendly error pages (brief: members of every digital skill level). A page in the member's
language with plain words and a way back home; the /api/ routes keep their JSON errors. A
server error never shows its details, only logs them."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from reimbursement_council.web.context import Page
from reimbursement_council.web.i18n import text_for

logger = logging.getLogger(__name__)

TITLES = {400: "error_400", 404: "error_404", 409: "error_409"}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith(("/api/", "/static/"))


def add_error_pages(app: FastAPI, page: Page) -> None:
    def friendly(request: Request, status: int, detail: str | None) -> Response:
        lang = request.query_params.get("lang", "en")
        text = text_for(lang)
        title = text[TITLES.get(status, "error_500")]
        return page(request, "error.html", lang, title=title, detail=detail, status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> Response:
        if _is_api(request):
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        detail = error.detail if isinstance(error.detail, str) else None
        return friendly(request, error.status_code, detail)

    @app.exception_handler(RequestValidationError)
    async def form_error(request: Request, error: RequestValidationError) -> Response:
        if _is_api(request):
            return JSONResponse({"detail": "The request is not complete."}, status_code=400)
        return friendly(request, 400, None)

    @app.exception_handler(Exception)
    async def server_error(request: Request, error: Exception) -> Response:
        logger.exception("server error on %s", request.url.path)
        if _is_api(request):
            return JSONResponse({"detail": "Server error."}, status_code=500)
        return friendly(request, 500, None)
