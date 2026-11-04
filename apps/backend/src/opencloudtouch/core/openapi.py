"""OpenAPI customisation: publish the standard error models.

Error responses are produced by exception handlers (``JSONResponse``), so
FastAPI does not see ``ErrorDetail``/``ErrorItem``. They are injected into
``components.schemas`` so generated clients get the error contract; success
schemas stay unchanged.
"""

from typing import Any

from fastapi import FastAPI

from opencloudtouch.core.exceptions import ErrorDetail, ErrorItem

_REF_TEMPLATE = "#/components/schemas/{model}"


def install_error_schemas(app: FastAPI) -> None:
    """Make ``app.openapi()`` include ``ErrorDetail`` and ``ErrorItem``."""
    original = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original()
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (ErrorDetail, ErrorItem):
            model_schema = model.model_json_schema(
                ref_template=_REF_TEMPLATE, mode="serialization"
            )
            for name, definition in model_schema.pop("$defs", {}).items():
                schemas.setdefault(name, definition)
            schemas[model.__name__] = model_schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
