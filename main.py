"""
Daily Champions League / Football Telegram Poster
---------------------------------------------------
Runs once a day (scheduled by GitHub Actions cron).
- If there's a Champions League fixture today -> posts fixtures + a prediction poll.
- Otherwise -> posts trivia, a fun fact, or an emoji quiz (rotated by day).

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
    team_names = []
    for m in matches:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        time_str = m["utcDate"][11:16]
        lines.append(f"⚽ {home} vs {away} — {time_str} UTC")
        team_names.extend([home, away])
    send_message("\n".join(lines))

    if len(matches) >= 1:
        first = matches[0]
        home = first["homeTeam"]["name"]
        away = first["awayTeam"]["name"]
        poll_q = random.choice(bank["polls"])
        send_poll(f"{poll_q} ({home} vs {away})", [home, "Draw", away])


def post_variety_content(bank):
    day_index = datetime.date.today().toordinal()
    content_type = day_index % 3

    if content_type == 0:
        item = random.choice(bank["trivia"])
        send_message(f"🧠 <b>Football Trivia of the Day</b>\n\n{item['q']}\n\n<i>Reply with your guess! Answer revealed tomorrow.</i>")
    elif content_type == 1:
        fact = random.choice(bank["fun_facts"])
        send_message(f"📚 <b>Did You Know?</b>\n\n{fact}")
    else:
        quiz = random.choice(bank["emoji_quiz"])
        send_message(f"🎮 <b>Emoji Quiz</b>\n\n{quiz['clue']}\n\n<i>First correct answer wins bragging rights!</i>")


def main():
    bank = load_bank()
    matches = get_today_fixtures()

    if matches:
        post_fixtures_and_poll(matches, bank)
    else:
        post_variety_content(bank)


if __name__ == "__main__":
    main()
