#!/usr/bin/env python3
"""
Push best_configs.txt to GitHub automatically.
Reads GitHub settings from config.env or environment variables.
"""

import os
import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

def load_env(env_file: str = "config.env"):
    """Load key=value pairs from a simple env file."""
    p = Path(env_file)
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def run(cmd: list[str], cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    log.info("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        log.info(result.stdout.strip())
    if result.stderr.strip():
        log.warning(result.stderr.strip())
    if check and result.returncode != 0:
        log.error(f"Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    return result


def push_to_github():
    load_env()

    token      = os.environ.get("GITHUB_TOKEN", "")
    repo_owner = os.environ.get("GITHUB_OWNER", "")
    repo_name  = os.environ.get("GITHUB_REPO", "vpn-subscriptions")
    branch     = os.environ.get("GITHUB_BRANCH", "main")
    sub_file   = os.environ.get("OUTPUT_FILE", "best_configs.txt")
    repo_dir   = os.environ.get("REPO_DIR", "./repo")   # local clone path

    if not all([token, repo_owner, repo_name]):
        log.error("Missing GITHUB_TOKEN, GITHUB_OWNER, or GITHUB_REPO in environment / config.env")
        sys.exit(1)

    remote_url = f"https://{token}@github.com/{repo_owner}/{repo_name}.git"
    repo_path  = Path(repo_dir).resolve()

    # ── Clone or pull ─────────────────────────────────────────────────────
    if not (repo_path / ".git").exists():
        log.info(f"Cloning {repo_owner}/{repo_name} into {repo_path}")
        repo_path.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "-b", branch, remote_url, str(repo_path)])
    else:
        log.info("Pulling latest changes")
        run(["git", "pull", "--rebase"], cwd=str(repo_path))

    # ── Copy subscription file into repo ─────────────────────────────────
    src = Path(sub_file).resolve()
    dst = repo_path / sub_file
    if not src.exists():
        log.error(f"Source file not found: {src}")
        sys.exit(1)
    dst.write_bytes(src.read_bytes())
    log.info(f"Copied {src} → {dst}")

    # ── Git commit & push ─────────────────────────────────────────────────
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "config", "user.email", "vpn-bot@noreply.local"], cwd=str(repo_path))
    run(["git", "config", "user.name",  "VPN Tester Bot"],        cwd=str(repo_path))
    run(["git", "add", sub_file],                                  cwd=str(repo_path))

    diff = run(["git", "diff", "--cached", "--stat"], cwd=str(repo_path), check=False)
    if "nothing to commit" in diff.stdout or diff.stdout.strip() == "":
        log.info("No changes to commit.")
        return

    run(["git", "commit", "-m", f"chore: update subscription {ts}"], cwd=str(repo_path))
    run(["git", "push", "origin", branch],                          cwd=str(repo_path))
    log.info("✅  Pushed to GitHub successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    push_to_github()
