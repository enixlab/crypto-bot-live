#!/usr/bin/env python3
"""
Fleet Monitor — surveille la sante de la flotte de bots ENIX.
Tourne sur GitHub Actions (externe au VPS), toutes les 15 min.

Alerte si :
  - le feed data-feed est gele (> FRESH_MAX min) => VPS probablement a l'arret
  - un bot attendu est vide / inactif (equity=0 et capital=0)

Canaux d'alerte :
  - GitHub Issue (titre fixe) => email automatique au proprietaire du repo
  - Telegram (si TELEGRAM_TOKEN + TELEGRAM_CHAT_ID definis dans les secrets)
"""
import json, os, re, subprocess, sys, urllib.request, urllib.parse
from datetime import datetime, timezone

REPO          = os.environ.get("REPO", "enixlab/crypto-bot-live")
FEED_BRANCH   = "data-feed"
FEED_PATH     = "dashboard/dashboard_data.js"
FRESH_MAX_MIN = 30           # feed considere gele au-dela
ISSUE_TITLE   = "ENIX Fleet Monitor — alerte sante flotte"
EXPECTED_BOTS = ["LS V3 LO", "Conflu Rev", "Ult.V2 Rev", "LS V3", "LS V3 TP"]

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def fetch_feed():
    url = f"https://raw.githubusercontent.com/{REPO}/{FEED_BRANCH}/{FEED_PATH}"
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    j = re.sub(r"^window\.BOT_DATA\s*=\s*", "", raw.strip()).rstrip().rstrip(";")
    return json.loads(j)


def analyze(data):
    problems = []
    now = datetime.now(timezone.utc)

    # 1) fraicheur du feed
    ua = data.get("updated_at", "")
    try:
        t = datetime.fromisoformat(ua.replace("Z", "+00:00"))
        age_min = (now - t).total_seconds() / 60
        if age_min > FRESH_MAX_MIN:
            problems.append(
                f"🔴 Feed GELE depuis {int(age_min)} min (derniere maj {ua}). "
                f"Le VPS Contabo est probablement a l'arret ou hors-ligne."
            )
    except Exception:
        problems.append(f"🔴 updated_at illisible dans le feed: {ua!r}")

    # 2) bots vides / inactifs
    seen = {}
    for b in data.get("bots", []):
        if not b:
            continue
        st = b.get("state") or {}
        eq = st.get("equity", 0) or 0
        init = st.get("initial_capital", 0) or 0
        seen[b.get("name", "?")] = (eq, init)

    for name in EXPECTED_BOTS:
        if name not in seen:
            problems.append(f"🟠 Bot « {name} » absent du feed.")
        else:
            eq, init = seen[name]
            if eq == 0 and init == 0:
                problems.append(f"🟠 Bot « {name} » vide/inactif (equity=0, capital=0).")

    return problems, now


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def find_open_issue():
    r = gh("issue", "list", "--state", "open", "--search",
           f'in:title "{ISSUE_TITLE}"', "--json", "number", "--limit", "1")
    try:
        arr = json.loads(r.stdout or "[]")
        return arr[0]["number"] if arr else None
    except Exception:
        return None


def telegram(msg):
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30
        )
    except Exception as e:
        print(f"Telegram echec: {e}", file=sys.stderr)


def main():
    try:
        data = fetch_feed()
    except Exception as e:
        # impossible de lire le feed = anomalie en soi
        problems = [f"🔴 Impossible de lire le feed: {e}"]
        data = {}
        now = datetime.now(timezone.utc)
    else:
        problems, now = analyze(data)

    existing = find_open_issue()

    if problems:
        body = ("**Le moniteur de flotte a detecte un probleme** "
                f"({now.strftime('%Y-%m-%d %H:%M UTC')}) :\n\n"
                + "\n".join(f"- {p}" for p in problems)
                + "\n\n---\n"
                "Verifier sur le VPS (PowerShell admin) :\n"
                "```\nGet-ScheduledTask EnixCryptoBot*,EnixDashSync,EnixWatchdog | ft TaskName,State\n```\n"
                "Le watchdog relance normalement tout seul sous 5 min. "
                "Si l'alerte persiste, le VPS lui-meme est peut-etre hors-ligne.")
        tg_msg = ("🚨 <b>ENIX Fleet Monitor</b>\n"
                  f"{now.strftime('%Y-%m-%d %H:%M UTC')}\n\n" + "\n".join(problems))
        if existing:
            gh("issue", "comment", str(existing), "--body", body)
        else:
            gh("issue", "create", "--title", ISSUE_TITLE, "--body", body)
        telegram(tg_msg)
        print("ALERTE:\n" + "\n".join(problems))
        sys.exit(0)
    else:
        if existing:
            gh("issue", "comment", str(existing), "--body",
               f"✅ Tout est revenu a la normale ({now.strftime('%Y-%m-%d %H:%M UTC')}). Cloture automatique.")
            gh("issue", "close", str(existing))
            telegram(f"✅ ENIX Fleet Monitor : flotte revenue a la normale ({now.strftime('%H:%M UTC')}).")
        print("OK — flotte saine.")


if __name__ == "__main__":
    main()
