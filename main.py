"""
Hourly Champions League / Football Telegram Poster
---------------------------------------------------
Runs every hour (scheduled by GitHub Actions cron).
- 09:00 UTC on a match day -> posts fixtures + a prediction poll (once).
- During a match's live window -> posts a live score update.
- All other hours -> posts a random trivia question, fun fact, or emoji quiz.

Required environment variables (set as GitHub repo secrets):
  TELEGRAM_BOT_TOKEN   - token from @BotFather
  TELEGRAM_CHAT_ID     - your channel's chat id (e.g. -1001234567890)
  FOOTBALL_DATA_API_KEY - free key from https://www.football-data.org/client/register
"""

import os
import json
import random
import datetime
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CL_COMPETITION_CODE = "CL"  # UEFA Champions League on football-data.org


def load_bank():
    with open(os.path.join(os.path.dirname(__file__), "content_bank.json")) as f:
        return json.load(f)


def get_today_fixtures():
    """Fetch today's Champions League fixtures from football-data.org (free tier)."""
    if not FOOTBALL_API_KEY:
        return []
    today = datetime.date.today().isoformat()
    url = f"https://api.football-data.org/v4/competitions/{CL_COMPETITION_CODE}/matches"
    params = {"dateFrom": today, "dateTo": today}
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except requests.RequestException as e:
        print(f"Fixture fetch failed: {e}")
        return []


def send_message(text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def send_poll(question, options):
    url = f"{TELEGRAM_API}/sendPoll"
    payload = {
        "chat_id": CHAT_ID,
        "question": question,
        "options": json.dumps(options),
        "is_anonymous": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def post_fixtures_and_poll(matches, bank):
    lines = ["🏆 <b>Today's Champions League Fixtures</b>\n"]
    for m in matches:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        time_str = m["utcDate"][11:16]
        lines.append(f"⚽ {home} vs {away} — {time_str} UTC")
    send_message("\n".join(lines))

    first = matches[0]
    home = first["homeTeam"]["name"]
    away = first["awayTeam"]["name"]
    poll_q = random.choice(bank["polls"])
    send_poll(f"{poll_q} ({home} vs {away})", [home, "Draw", away])


def post_live_scores(live_matches):
    lines = ["🔴 <b>Live Score Update</b>\n"]
    for m in live_matches:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        ft = m.get("score", {}).get("fullTime", {})
        hs = ft.get("home")
        as_ = ft.get("away")
        score_str = f"{hs if hs is not None else 0} - {as_ if as_ is not None else 0}"
        status = "🟢 LIVE" if m["status"] == "IN_PLAY" else "⏸️ HALFTIME"
        lines.append(f"{status}  {home} {score_str} {away}")
    send_message("\n".join(lines))


def post_variety_content(bank):
    # Fully random each run (not tied to day) so hourly posts don't repeat.
    content_type = random.choice(["trivia", "fact", "quiz"])

    if content_type == "trivia":
        item = random.choice(bank["trivia"])
        send_message(f"🧠 <b>Football Trivia</b>\n\n{item['q']}\n\n<i>Reply with your guess!</i>")
    elif content_type == "fact":
        fact = random.choice(bank["fun_facts"])
        send_message(f"📚 <b>Did You Know?</b>\n\n{fact}")
    else:
        quiz = random.choice(bank["emoji_quiz"])
        send_message(f"🎮 <b>Emoji Quiz</b>\n\n{quiz['clue']}\n\n<i>First correct answer wins bragging rights!</i>")


def main():
    bank = load_bank()
    matches = get_today_fixtures()
    now_hour = datetime.datetime.utcnow().hour

    live_matches = [m for m in matches if m.get("status") in ("IN_PLAY", "PAUSED")]

    if live_matches:
        # A match is actually in progress right now -> live score update.
        post_live_scores(live_matches)
    elif matches and now_hour == 9:
        # Morning fixture announcement, once per match day.
        post_fixtures_and_poll(matches, bank)
    else:
        # No live match and not the 9am slot -> keep the channel active with variety content.
        post_variety_content(bank)


if __name__ == "__main__":
    main()
