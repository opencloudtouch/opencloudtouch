"""Bounded body reading (AC-A6, helper part)."""

import pytest

from opencloudtouch.core.request_body import RequestBodyTooLarge, read_limited_body


class _FakeRequest:
    def __init__(self, chunks, headers=None):
        self.headers = headers or {}
        self._chunks = chunks
        self.stream_started = False

    async def stream(self):
        self.stream_started = True
        for chunk in self._chunks:
            yield chunk


async def test_small_body_is_returned():
    request = _FakeRequest([b"ab", b"cd"], {"content-length": "4"})
    assert await read_limited_body(request, limit=4) == b"abcd"


async def test_declared_length_over_limit_is_refused_without_reading():
    request = _FakeRequest([b"x" * 10], {"content-length": "10"})
    with pytest.raises(RequestBodyTooLarge):
        await read_limited_body(request, limit=4)
    assert request.stream_started is False


async def test_chunked_body_aborts_at_the_limit():
    consumed = []

    class Endless(_FakeRequest):
        async def stream(self):
            for _ in range(1000):
                consumed.append(1)
                yield b"x" * 3

    with pytest.raises(RequestBodyTooLarge):
        await read_limited_body(Endless([]), limit=4)
    assert len(consumed) == 2


async def test_malformed_content_length_falls_back_to_streaming():
    request = _FakeRequest([b"abc"], {"content-length": "nope"})
    assert await read_limited_body(request, limit=4) == b"abc"
