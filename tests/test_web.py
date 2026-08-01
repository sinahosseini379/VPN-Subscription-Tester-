from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest
from aiohttp.test_utils import TestClient, TestServer

from vpn_tester.config import Settings
from vpn_tester.runtime import RunCoordinator
from vpn_tester.web import HTML, _load_configs, _update_env, create_app


async def _noop_run(settings, *, do_push: bool = True) -> bool:
    return True


def _make_env(tmp_path) -> str:
    env = tmp_path / "config.env"
    env.write_text("# comment\nSCHEDULE_TIME=04:04\n", encoding="utf-8")
    return str(env)


def _make_settings(tmp_path) -> Settings:
    return Settings(
        subscriptions_file=str(tmp_path / "subscriptions.txt"),
        output_file=str(tmp_path / "best_configs.txt"),
        metadata_file=str(tmp_path / "best_configs.txt.meta.json"),
        config_file=str(tmp_path / "config.env"),
        max_subscription_urls=3,
    )


def test_update_env_uncomments_and_replaces(tmp_path):
    env = _make_env(tmp_path)
    _update_env(env, "SCHEDULE_TIME", "07:30")
    _update_env(env, "TIMEZONE", "UTC")
    content = (tmp_path / "config.env").read_text(encoding="utf-8")
    assert "SCHEDULE_TIME=07:30" in content
    assert "TIMEZONE=UTC" in content


def test_load_configs_merges_uris_and_meta(tmp_path):
    settings = _make_settings(tmp_path)
    uris = ["vless://a@x.com:443#A", "vless://b@x.com:443#B"]
    (tmp_path / "best_configs.txt").write_text(
        base64.b64encode("\n".join(uris).encode()).decode(), encoding="utf-8"
    )
    (tmp_path / "best_configs.txt.meta.json").write_text(
        json.dumps(
            {"generated_at": "t", "items": [{"name": "A"}, {"name": "B"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    data = _load_configs(settings)
    assert data["count"] == 2
    assert data["configs"][0]["uri"] == "vless://a@x.com:443#A"
    assert data["configs"][0]["name"] == "A"


@pytest.mark.asyncio
async def test_api_flow(tmp_path):
    settings = _make_settings(tmp_path)
    (tmp_path / "subscriptions.txt").write_text("https://sub.example.com/a\n", encoding="utf-8")
    coordinator = RunCoordinator(settings, run_once_fn=_noop_run)
    app = create_app(settings, coordinator, env_file=str(tmp_path / "config.env"))

    async with TestClient(TestServer(app)) as client:
        # configs (none yet)
        r = await client.get("/api/configs")
        assert r.status == 200
        assert (await r.json())["count"] == 0

        # subscriptions read
        r = await client.get("/api/subscriptions")
        assert r.status == 200
        assert (await r.json())["urls"] == ["https://sub.example.com/a"]

        # add
        r = await client.post("/api/subscriptions/add", json={"url": "https://sub.example.com/b"})
        assert r.status == 200
        urls = (await r.json())["urls"]
        assert "https://sub.example.com/b" in urls

        # max cap enforced
        await client.post("/api/subscriptions/add", json={"url": "https://s/c"})
        await client.post("/api/subscriptions/add", json={"url": "https://s/d"})
        r = await client.get("/api/subscriptions")
        assert len((await r.json())["urls"]) == 3

        # remove
        r = await client.post(
            "/api/subscriptions/remove", json={"url": "https://sub.example.com/b"}
        )
        assert "https://sub.example.com/b" not in (await r.json())["urls"]

        # schedule get/set
        r = await client.get("/api/schedule")
        sched = await r.json()
        assert sched["schedule_time"] == "04:04"

        r = await client.post("/api/schedule", json={"schedule_time": "09:15", "timezone": "UTC"})
        assert r.status == 200
        body = await r.json()
        assert body["schedule_time"] == "09:15"
        assert settings.schedule_time == "09:15"
        env_content = (tmp_path / "config.env").read_text(encoding="utf-8")
        assert "SCHEDULE_TIME=09:15" in env_content
        assert "TIMEZONE=UTC" in env_content

        # invalid schedule rejected
        r = await client.post("/api/schedule", json={"schedule_time": "25:99", "timezone": "UTC"})
        assert r.status == 400

        # status endpoint
        r = await client.get("/api/status")
        assert r.status == 200
        assert "status" in await r.json()

        # manual run triggers coordinator (no-op lambda)
        r = await client.post("/api/run")
        assert r.status == 200
        assert (await r.json())["started"] is True


@pytest.mark.asyncio
async def test_subscription_endpoint_headers(tmp_path):
    settings = _make_settings(tmp_path)
    content = base64.b64encode(b"vless://a@x.com:443#A").decode()
    (tmp_path / "best_configs.txt").write_text(content, encoding="utf-8")
    settings.subscription_name = "Fiddel"
    settings.subscription_interval_hours = 24
    coordinator = RunCoordinator(settings, run_once_fn=_noop_run)
    app = create_app(settings, coordinator, env_file=str(tmp_path / "config.env"))

    async with TestClient(TestServer(app)) as client:
        r = await client.get("/subscription")
        assert r.status == 200
        assert (await r.text()) == content
        assert r.headers["content-type"].startswith("text/plain")
        assert r.headers["subscription-userinfo"] == "interval=86400"
        assert r.headers["profile-update-interval"] == "86400"
        assert r.headers["profile-title"] == base64.b64encode(b"Fiddel").decode()


@pytest.mark.asyncio
async def test_subscription_endpoint_404_before_publish(tmp_path):
    settings = _make_settings(tmp_path)
    coordinator = RunCoordinator(settings, run_once_fn=_noop_run)
    app = create_app(settings, coordinator, env_file=str(tmp_path / "config.env"))
    async with TestClient(TestServer(app)) as client:
        r = await client.get("/subscription")
        assert r.status == 404


def test_index_js_is_valid_javascript():
    """The served <script> block must parse, otherwise every dashboard button dies."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")

    match = re.search(r"<script>(.*?)</script>", HTML, re.S)
    assert match, "no <script> block found in dashboard HTML"

    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(match.group(1))
        result = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    finally:
        os.unlink(path)
