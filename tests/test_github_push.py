from __future__ import annotations

import base64
import json

import pytest

from vpn_tester.config import Settings
from vpn_tester.github_push import push_to_github

GITHUB_API = "https://api.github.com/repos/owner/repo/contents/"


class _FakeResponse:
    def __init__(self, status: int, payload):
        self.status = status
        self.content_type = "application/json"
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return json.dumps(self._payload) if not isinstance(self._payload, str) else self._payload


class _FakeSession:
    """Records all requests; returns scripted responses per URL."""

    def __init__(self, routes: dict[str, _FakeResponse]):
        self._routes = routes
        self.requests: list[dict] = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, "kwargs": kwargs})
        for route_url, resp in self._routes.items():
            if url == route_url:
                return resp
        return _FakeResponse(404, "no route")


def _settings() -> Settings:
    return Settings(
        github_token="tok123",
        github_owner="owner",
        github_repo="repo",
        github_branch="main",
        github_files=["best_configs.txt"],
    )


async def test_push_creates_new_file(tmp_path):
    out = tmp_path / "best_configs.txt"
    out.write_text("vless://x@y.com:443", encoding="utf-8")
    s = _settings()
    s.github_files = [str(out)]

    session = _FakeSession(
        {
            GITHUB_API + "best_configs.txt?ref=main": _FakeResponse(404, {"message": "nf"}),
            GITHUB_API + "best_configs.txt": _FakeResponse(201, {"content": {}}),
        }
    )

    ok = await push_to_github(s, attempt=1, session=session)
    assert ok is True

    put = next(r for r in session.requests if r["method"] == "PUT")
    assert put["url"] == GITHUB_API + "best_configs.txt"
    assert "tok123" not in put["url"]
    body = put["kwargs"]["json"]
    assert body["content"] == base64.b64encode(b"vless://x@y.com:443").decode()
    assert body["branch"] == "main"
    assert put["kwargs"]["headers"]["Authorization"] == "Bearer tok123"


async def test_push_updates_existing_file(tmp_path):
    out = tmp_path / "best_configs.txt"
    out.write_text("vless://x@y.com:443", encoding="utf-8")
    s = _settings()
    s.github_files = [str(out)]

    session = _FakeSession(
        {
            GITHUB_API + "best_configs.txt?ref=main": _FakeResponse(
                200, {"sha": "abc123", "content": "bm90aGluZw=="}
            ),
            GITHUB_API + "best_configs.txt": _FakeResponse(200, {"content": {}}),
        }
    )

    assert await push_to_github(s, attempt=1, session=session) is True
    put = next(r for r in session.requests if r["method"] == "PUT")
    assert put["kwargs"]["json"]["sha"] == "abc123"


async def test_push_retries_then_fails(tmp_path):
    out = tmp_path / "best_configs.txt"
    out.write_text("data", encoding="utf-8")
    s = _settings()
    s.github_files = [str(out)]

    # Always 401 -> all attempts fail -> returns False
    _session = _FakeSession(
        {
            GITHUB_API + "best_configs.txt?ref=main": _FakeResponse(401, {"message": "bad token"}),
            GITHUB_API + "best_configs.txt": _FakeResponse(401, {"message": "bad token"}),
        }
    )
    assert await push_to_github(s, attempt=2, session=_session) is False


async def test_push_skips_missing_file(tmp_path):
    s = _settings()
    s.github_files = [str(tmp_path / "nope.txt")]
    _session = _FakeSession({})
    assert await push_to_github(s, attempt=1, session=_session) is True  # nothing to upload


async def test_push_requires_credentials():
    s = Settings(github_token="", github_owner="o", github_repo="r")
    with pytest.raises(ValueError):
        await push_to_github(s, attempt=1)
