"""Bounded request body reading for routes that take input from the LAN."""

from fastapi import Request

DEFAULT_BODY_LIMIT = 4096


class RequestBodyTooLarge(Exception):
    """The request body exceeds the allowed size."""


async def read_limited_body(request: Request, limit: int = DEFAULT_BODY_LIMIT) -> bytes:
    """Read the body, rejecting anything over ``limit`` bytes.

    A declared ``Content-Length`` over the limit is refused before a single byte is
    read; without one (chunked) reading aborts as soon as the limit is passed.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise RequestBodyTooLarge
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise RequestBodyTooLarge
    return bytes(body)
