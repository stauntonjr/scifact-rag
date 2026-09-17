from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..generation import GenerationContextStrategyName
from ..strategies import DEFAULT_RETRIEVAL_STRATEGY, RetrievalStrategyName

_CONFIG_MARKER = "__SCIFACT_CONFIG__"


@lru_cache(maxsize=3)
def _asset_text(name: str) -> str:
    return files("scifact_rag.web").joinpath(name).read_text(encoding="utf-8")


def _configuration_json() -> str:
    value = json.dumps(
        {
            "retrieval_strategies": [strategy.value for strategy in RetrievalStrategyName],
            "default_retrieval_strategy": DEFAULT_RETRIEVAL_STRATEGY.value,
            "context_strategies": [strategy.value for strategy in GenerationContextStrategyName],
            "default_context_strategy": GenerationContextStrategyName.WHOLE_DOCUMENT.value,
        },
        separators=(",", ":"),
    )
    return value.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def create_web_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)
    index = _asset_text("index.html").replace(_CONFIG_MARKER, _configuration_json())
    stylesheet = _asset_text("scifact.css")
    script = _asset_text("scifact.js")

    @router.get("/", response_class=HTMLResponse)
    def web_index() -> HTMLResponse:
        return HTMLResponse(index, headers={"Cache-Control": "no-store"})

    @router.get("/assets/scifact.css")
    def web_stylesheet() -> Response:
        return Response(stylesheet, media_type="text/css", headers={"Cache-Control": "no-store"})

    @router.get("/assets/scifact.js")
    def web_script() -> Response:
        return Response(script, media_type="text/javascript", headers={"Cache-Control": "no-store"})

    return router
