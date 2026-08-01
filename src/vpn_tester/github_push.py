"""Push result files to GitHub using the Contents API.

Why not git? v1 put the token inside the remote URL, which:
  - gets stored in .git/config on disk, and
  - appears in error output on every failed command.

The Contents API uses a Bearer header only, so the token never touches the
filesystem or subprocess arguments. Files are updated atomically per-request
and creation of new files is handled automatically.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import urllib.parse
from pathlib import Path

import aiohttp

from .config import Settings

log = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


def _file_to_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


async def _api(
    session: aiohttp.ClientSession, method: str, url: str, token: str, payload: dict | None = None
) -> dict | None:
    """One GitHub API call with a Bearer token; returns parsed JSON or None."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with session.request(method, url, headers=headers, json=payload) as resp:
        body = (
            await resp.json(content_type=None)
            if resp.content_type == "application/json"
            else await resp.text()
        )
        if resp.status >= 400:
            detail = body if isinstance(body, str) else body.get("message", body)
            log.warning("GitHub API %s %s -> HTTP %s: %s", method, url, resp.status, detail)
            return None
        return body if isinstance(body, dict) else {}


def _repo_rel(rel: str) -> str:
    """GitHub API path for a configured file.

    Nested relative entries (e.g. ``output/best_configs.txt``) map to the same
    repo path; absolute local paths fall back to their basename.
    """
    p = Path(rel)
    return p.name if p.is_absolute() else rel


async def _upsert_file(
    session: aiohttp.ClientSession, settings: Settings, path: Path, repo_rel: str, sha: str | None
) -> bool:
    api_url = (
        f"{API_BASE}/repos/{settings.github_owner}/{settings.github_repo}"
        f"/contents/{urllib.parse.quote(repo_rel, safe='/')}"
    )
    payload = {
        "message": f"chore: update {repo_rel}",
        "content": _file_to_b64(path),
        "branch": settings.github_branch,
        "author": {
            "name": settings.github_commit_name,
            "email": settings.github_commit_email,
        },
        "committer": {
            "name": settings.github_commit_name,
            "email": settings.github_commit_email,
        },
    }
    if sha:
        payload["sha"] = sha  # update existing file
    result = await _api(session, "PUT", api_url, settings.github_token, payload)
    return result is not None


async def _current_sha(
    session: aiohttp.ClientSession, settings: Settings, repo_rel: str
) -> str | None:
    api_url = (
        f"{API_BASE}/repos/{settings.github_owner}/"
        f"{settings.github_repo}/contents/{urllib.parse.quote(repo_rel, safe='/')}"
        f"?ref={settings.github_branch}"
    )
    data = await _api(session, "GET", api_url, settings.github_token)
    if data and isinstance(data.get("sha"), str):
        return data["sha"]
    return None


async def push_to_github(
    settings: Settings, attempt: int = 3, session: aiohttp.ClientSession | None = None
) -> bool:
    """Upload every configured output file; returns True if all succeeded.

    `session` is injectable for tests; when omitted an internal one is created.
    """
    if not (settings.github_token and settings.github_owner and settings.github_repo):
        raise ValueError("GitHub push requires GITHUB_TOKEN, GITHUB_OWNER and GITHUB_REPO.")

    own_session = session is None
    for _ in range(attempt):
        try:
            if own_session:
                timeout = aiohttp.ClientTimeout(total=30)
                session = aiohttp.ClientSession(timeout=timeout)
            try:
                for rel in settings.github_files:
                    path = Path(rel)
                    if not path.exists():
                        log.warning("File not found, skipping: %s", rel)
                        continue
                    repo_rel = _repo_rel(rel)
                    sha = await _current_sha(session, settings, repo_rel)
                    ok = await _upsert_file(session, settings, path, repo_rel, sha)
                    if not ok:
                        raise RuntimeError(f"Failed to upload {repo_rel}")
                    log.info("Uploaded %s", repo_rel)
            finally:
                if own_session:
                    await session.close()
            log.info("GitHub push succeeded.")
            return True
        except Exception as exc:
            log.warning("GitHub push attempt failed: %s", exc)
            await asyncio.sleep(2)
    return False
