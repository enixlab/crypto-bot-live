"""Upload dashboard_data.js vers GitHub branche 'data-feed' à chaque cycle.

Permet au user de voir le dashboard depuis n'importe où sans RDP.
URL publique : https://raw.githubusercontent.com/enixlab/crypto-bot-live/data-feed/dashboard/dashboard_data.js
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

_LAST_PUSH = 0


def push_dashboard_to_github(repo_dir: Path, min_interval_sec: int = 300) -> bool:
    """Push dashboard_data.js sur la branche 'data-feed'. Rate-limit 5 min."""
    global _LAST_PUSH
    now = time.time()
    if now - _LAST_PUSH < min_interval_sec:
        return False

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return False

    try:
        repo_url = f"https://{token}@github.com/enixlab/crypto-bot-live.git"
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        def run(cmd, check=False, timeout=15):
            return subprocess.run(cmd, cwd=str(repo_dir), env=env, check=check, timeout=timeout,
                                  capture_output=True, text=True)

        run(["git", "config", "user.email", "bot@enix-lab.com"])
        run(["git", "config", "user.name", "Enix Bot"])

        # Save current branch
        cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "main"

        # Switch/create data-feed branch (orphan-like: single commit force-pushed)
        run(["git", "checkout", "-B", "data-feed"])

        # Add dashboard_data.js
        run(["git", "add", "-f", "dashboard/dashboard_data.js"])

        # Commit with --allow-empty so it doesn't fail if no changes
        run(["git", "commit", "-m", f"data {int(now)}", "--allow-empty"])

        # Push force to data-feed
        push_result = run(["git", "push", "-f", repo_url, "data-feed"], timeout=20)

        # Switch back to main
        run(["git", "checkout", cur])

        if push_result.returncode == 0:
            _LAST_PUSH = now
            log.info("dashboard pushed to GitHub data-feed branch")
            return True
        else:
            log.warning("git push failed: %s", push_result.stderr[:200])
            return False
    except Exception as e:
        log.warning("sync_dashboard err: %s", e)
        return False
