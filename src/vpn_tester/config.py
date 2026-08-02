"""Load configuration from config.env and environment variables.

Precedence (highest wins): real environment variable > config.env file > default.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file(path: Path | str) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. Comments (#) and blanks are ignored."""
    p = Path(path)
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not value:  # empty value == unset
            continue
        # strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


DEFAULT_TEST_URLS: list[tuple[str, str, float]] = [
    ("Google", "http://www.gstatic.com/generate_204", 1.0),
    ("YouTube", "https://www.youtube.com/generate_204", 1.0),
    ("Cloudflare", "http://cp.cloudflare.com/", 1.0),
    ("X.com", "https://x.com/", 1.0),
]

DEFAULT_ALLOWED_COUNTRIES: dict[str, tuple[str, str]] = {
    "DE": ("Germany", "🇩🇪"),
    "FI": ("Finland", "🇫🇮"),
    "NL": ("Netherlands", "🇳🇱"),
    "GB": ("United Kingdom", "🇬🇧"),
    "US": ("United States", "🇺🇸"),
    "TR": ("Turkey", "🇹🇷"),
}

DEFAULT_GEOIP_PROVIDERS: list[str] = [
    "https://ipinfo.io/json",
    "https://ip-api.com/json/",
    "https://ipapi.co/json/",
]

DEFAULT_GITHUB_FILES: list[str] = [
    "best_configs.txt",
    "best_configs.txt.meta.json",
]


@dataclass
class Settings:
    """All tunables for the tester, resolved from defaults < config.env < env."""

    # -- Pipeline behaviour -------------------------------------------------
    configs_per_country: int = 2
    url_test_rounds: int = 5
    tcp_ping_tries: int = 5
    tcp_ping_min_success: int = 4
    max_error_rate: float = 0.15
    schedule_time: str = "04:04"
    timezone: str = "Asia/Tehran"
    max_concurrent: int = 10
    tcp_concurrency: int = 100  # max parallel TCP probes (pre-filter)
    max_configs: int = 500  # hard cap on configs taken into the pipeline
    allow_insecure: bool = True  # tolerate self-signed/loose TLS (avoids false negatives)
    xray_startup_timeout: float = 15.0
    socks_port_base: int = 20000
    connect_timeout: float = 10.0
    request_timeout: float = 15.0
    download_timeout: float = 30.0
    max_subscription_urls: int = 10

    # -- What we test against ----------------------------------------------
    # Each target is (label, url, weight); weight influences the final score.
    test_urls: list[tuple[str, str, float]] = field(default_factory=lambda: list(DEFAULT_TEST_URLS))

    allowed_countries: dict[str, tuple[str, str]] = field(
        default_factory=lambda: dict(DEFAULT_ALLOWED_COUNTRIES)
    )

    # -- Inputs / outputs ---------------------------------------------------
    subscriptions_file: str = "subscriptions.txt"
    output_file: str = "best_configs.txt"
    metadata_file: str = "best_configs.txt.meta.json"
    log_file: str = "vpn_tester.log"
    log_level: str = "INFO"
    log_rotate_mb: int = 20
    log_backup_count: int = 5

    # -- Xray ---------------------------------------------------------------
    xray_bin: str = ""  # empty = search PATH + common locations, or auto-managed core
    xray_extra_args: list[str] = field(default_factory=list)

    # -- Managed cores (auto-download + auto-update from GitHub releases) ----
    cores_dir: str = "cores"
    auto_update_cores: bool = True
    sing_box_bin: str = ""  # empty = auto-managed under cores_dir
    hysteria_bin: str = ""  # empty = auto-managed under cores_dir

    # -- Incremental runs -----------------------------------------------------
    # From the second run onward, keep previous configs that still work and only
    # replace the dead ones (instead of publishing a fresh list every time).
    incremental: bool = True

    # -- Subscription profile (name + auto-update interval for clients) ------
    subscription_name: str = "Fiddel"
    subscription_interval_hours: int = 24

    # -- Geo-IP providers (queried in order, first success wins) ------------
    geoip_providers: list[str] = field(default_factory=lambda: list(DEFAULT_GEOIP_PROVIDERS))

    # -- GitHub -------------------------------------------------------------
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""
    github_branch: str = "main"
    github_commit_email: str = "vpn-bot@noreply.local"
    github_commit_name: str = "VPN Tester Bot"
    github_files: list[str] = field(default_factory=lambda: list(DEFAULT_GITHUB_FILES))

    # -- Alerting (optional; empty = disabled) ------------------------------
    alert_webhook: str = ""  # Telegram bot API or ntfy URL
    alert_min_configs: int = 3  # alert if fewer than this many configs survive

    # -- Dashboard (web UI served alongside the scheduler loop) -------------
    dashboard_enabled: bool = True
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 30445

    # -- Output naming ------------------------------------------------------
    output_naming_format: str = "{country} | {num:02d}"

    # -- Runtime bookkeeping -------------------------------------------------
    config_file: str = "config.env"  # env file used to load settings

    @classmethod
    def from_env(
        cls, env_file: str | os.PathLike = "config.env", environ: Mapping[str, str] | None = None
    ) -> Settings:
        env = _load_env_file(env_file)
        env.update(environ or os.environ)  # real env vars always win

        def _b(key: str, default: bool) -> bool:
            raw = env.get(key)
            if raw is None or raw == "":
                return default
            return raw.strip().lower() in ("1", "true", "yes", "on")

        def _i(key: str, default: int) -> int:
            raw = env.get(key)
            return int(raw) if raw else default

        def _f(key: str, default: float) -> float:
            raw = env.get(key)
            return float(raw) if raw else default

        def _s(key: str, default: str) -> str:
            return env.get(key, default).strip()

        urls_raw = env.get("TEST_URLS", "")
        test_urls = None
        if urls_raw:
            test_urls = []
            for entry in urls_raw.split("|"):
                if not entry.strip():
                    continue
                parts = entry.split(",")
                if len(parts) >= 2:
                    label, url = parts[0].strip(), parts[1].strip()
                    weight = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 1.0
                    test_urls.append((label, url, weight))

        countries_raw = env.get("ALLOWED_COUNTRIES", "")
        allowed = None
        if countries_raw:
            allowed = {}
            for entry in countries_raw.split(","):
                parts = entry.split(":")
                if len(parts) >= 2:
                    allowed[parts[0].strip().upper()] = (
                        parts[1].strip(),
                        parts[2].strip() if len(parts) > 2 else "",
                    )

        xray_extra = env.get("XRAY_EXTRA_ARGS", "")
        extra_args = (xray_extra.split()) if xray_extra else []

        files_raw = env.get("GITHUB_FILES", "")
        gh_files = ([f.strip() for f in files_raw.split(",") if f.strip()]) if files_raw else None

        geo_raw = env.get("GEOIP_PROVIDERS", "")
        providers = ([u.strip() for u in geo_raw.split(",") if u.strip()]) if geo_raw else None

        return cls(
            configs_per_country=_i("CONFIGS_PER_COUNTRY", cls.configs_per_country),
            url_test_rounds=_i("URL_TEST_ROUNDS", cls.url_test_rounds),
            tcp_ping_tries=_i("TCP_PING_TRIES", cls.tcp_ping_tries),
            tcp_ping_min_success=_i("TCP_PING_MIN_SUCCESS", cls.tcp_ping_min_success),
            max_error_rate=_f("MAX_ERROR_RATE", cls.max_error_rate),
            schedule_time=_s("SCHEDULE_TIME", cls.schedule_time),
            timezone=_s("TIMEZONE", cls.timezone),
            max_concurrent=_i("MAX_CONCURRENT", cls.max_concurrent),
            tcp_concurrency=_i("TCP_CONCURRENCY", cls.tcp_concurrency),
            max_configs=_i("MAX_CONFIGS", cls.max_configs),
            allow_insecure=_b("ALLOW_INSECURE", cls.allow_insecure),
            xray_startup_timeout=_f("XRAY_STARTUP_TIMEOUT", cls.xray_startup_timeout),
            socks_port_base=_i("SOCKS_PORT_BASE", cls.socks_port_base),
            connect_timeout=_f("CONNECT_TIMEOUT", cls.connect_timeout),
            request_timeout=_f("REQUEST_TIMEOUT", cls.request_timeout),
            download_timeout=_f("DOWNLOAD_TIMEOUT", cls.download_timeout),
            max_subscription_urls=_i("MAX_SUBSCRIPTION_URLS", cls.max_subscription_urls),
            incremental=_b("INCREMENTAL", cls.incremental),
            test_urls=test_urls or DEFAULT_TEST_URLS,
            allowed_countries=allowed or DEFAULT_ALLOWED_COUNTRIES,
            subscriptions_file=_s("SUBSCRIPTIONS_FILE", cls.subscriptions_file),
            output_file=_s("OUTPUT_FILE", cls.output_file),
            metadata_file=_s("METADATA_FILE", cls.metadata_file),
            log_file=_s("LOG_FILE", cls.log_file),
            log_level=_s("LOG_LEVEL", cls.log_level).upper(),
            log_rotate_mb=_i("LOG_ROTATE_MB", cls.log_rotate_mb),
            log_backup_count=_i("LOG_BACKUP_COUNT", cls.log_backup_count),
            xray_bin=_s("XRAY_BIN", cls.xray_bin),
            xray_extra_args=extra_args,
            geoip_providers=providers or DEFAULT_GEOIP_PROVIDERS,
            github_token=_s("GITHUB_TOKEN", cls.github_token),
            github_owner=_s("GITHUB_OWNER", cls.github_owner),
            github_repo=_s("GITHUB_REPO", cls.github_repo),
            github_branch=_s("GITHUB_BRANCH", cls.github_branch),
            github_commit_email=_s("GITHUB_COMMIT_EMAIL", cls.github_commit_email),
            github_commit_name=_s("GITHUB_COMMIT_NAME", cls.github_commit_name),
            github_files=gh_files or DEFAULT_GITHUB_FILES,
            alert_webhook=_s("ALERT_WEBHOOK", cls.alert_webhook),
            alert_min_configs=_i("ALERT_MIN_CONFIGS", cls.alert_min_configs),
            dashboard_enabled=_b("DASHBOARD_ENABLED", cls.dashboard_enabled),
            dashboard_host=_s("DASHBOARD_HOST", cls.dashboard_host),
            dashboard_port=_i("DASHBOARD_PORT", cls.dashboard_port),
            auto_update_cores=_b("AUTO_UPDATE_CORES", cls.auto_update_cores),
            cores_dir=_s("CORES_DIR", cls.cores_dir),
            subscription_name=_s("SUBSCRIPTION_NAME", cls.subscription_name),
            subscription_interval_hours=_i(
                "SUBSCRIPTION_INTERVAL_HOURS",
                # Accept the legacy name so old config.env files keep working.
                _i("SUBSCRIPTION_UPDATE_INTERVAL_HOURS", cls.subscription_interval_hours),
            ),
            output_naming_format=_s("OUTPUT_NAMING_FORMAT", cls.output_naming_format),
            config_file=str(env_file),
        )


def load_settings(env_file: str | os.PathLike = "config.env") -> Settings:
    return Settings.from_env(env_file)
