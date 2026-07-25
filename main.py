"""
Hourly Champions League / Football Telegram Poster
---------------------------------------------------
Runs every hour (scheduled by GitHub Actions cron).
- Checks replies to the PREVIOUS trivia/quiz post and announces if anyone
  got it right (or reveals the answer if nobody did).
- 09:00 UTC on a match day -> posts fixtures + a prediction poll (once).
- During a match's live window -> posts a live score update.
- Otherwise -> asks Claude to generate a fresh trivia question, fun fact,
  or emoji quiz, and remembers the correct answer for next run.

Required environment variables (set as GitHub repo secrets):
  TELEGRAM_BOT_TOKEN     - token from @BotFather
  TELEGRAM_CHAT_ID       - your group's chat id (e.g. -1001234567890)
  FOOTBALL_DATA_API_KEY  - free key from https://www.football-data.org/client/register
  ANTHROPIC_API_KEY      - key from https://console.claude.com (paid, usage here is tiny)
"""

import os
import json
import random
import datetime
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CL_COMPETITION_CODE = "CL"  # UEFA Champions League on football-data.org
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap, plenty for short posts

BASE_DIR = os.path.dirname(__file__)
STATE_PATH = os.path.join(BASE_DIR, "state.json")
POSTED_TEXTS_LIMIT = 40  # how many past questions/facts to remember, to avoid near-duplicates


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posted_texts": [], "last_update_id": 0, "pending": None}


def save_state(state):
    state["posted_texts"] = state.get("posted_texts", [])[-POSTED_TEXTS_LIMIT:]
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


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


def get_updates(offset):
    url = f"{TELEGRAM_API}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("result", [])


def check_pending_answer(state):
    """Look at messages sent since the last quiz/trivia post and see if anyone got it right."""
    pending = state.get("pending")
    offset = state.get("last_update_id") or None
    updates = get_updates(offset)

    max_update_id = state.get("last_update_id", 0)
    winner_name = None

    for u in updates:
        max_update_id = max(max_update_id, u["update_id"])
        msg = u.get("message")
        if not msg:
            continue
        if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
            continue
        text = msg.get("text", "")
        if not text or not pending or winner_name:
            continue
        if pending["answer"].strip().lower() in text.lower():
            winner_name = msg.get("from", {}).get("first_name", "Someone")

    state["last_update_id"] = max_update_id + 1

    if pending:
        if winner_name:
            send_message(
                f"✅ <b>{winner_name} got it right!</b>\n\nThe answer was: <b>{pending['answer']}</b> 🎉"
            )
        else:
            send_message(
                f"⏰ <b>Time's up, nobody got it!</b>\n\nThe answer was: <b>{pending['answer']}</b>"
            )
        state["pending"] = None


def post_fixtures_and_poll(matches):
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
    send_poll(f"🔮 Who wins today? ({home} vs {away})", [home, "Draw", away])


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


def generate_ai_content(content_type, posted_texts):
    """Ask Claude to write a fresh trivia question, fun fact, or emoji quiz (with answer)."""
    avoid_list = "\n".join(f"- {t}" for t in posted_texts[-25:]) or "(none yet)"

    prompts = {
        "trivia": (
            "Write ONE short, accurate football/Champions League trivia question "
            "for a group chat. Football history and facts only — no invented "
            "statistics. Under 30 words, end with a question mark.\n\n"
            f"Avoid repeating any of these already-posted questions:\n{avoid_list}\n\n"
            'Respond with ONLY raw JSON, no markdown fences: '
            '{"question": "...", "answer": "the short correct answer, e.g. a name or number"}'
        ),
        "fact": (
            "Write ONE short, accurate, interesting football/Champions League fun fact "
            "for a group chat. Under 30 words. No invented statistics.\n\n"
            f"Avoid repeating any of these already-posted facts:\n{avoid_list}\n\n"
            'Respond with ONLY raw JSON, no markdown fences: {"text": "..."}'
        ),
        "quiz": (
            "Write ONE emoji-clue guessing game for a football fan group: 2-4 emojis "
            "that hint at a real, well-known current or former footballer, followed by "
            "'Who am I?'. Do not reveal the name in the clue itself.\n\n"
            f"Avoid repeating any of these already-posted clues:\n{avoid_list}\n\n"
            'Respond with ONLY raw JSON, no markdown fences: '
            '{"clue": "emoji clue + Who am I?", "answer": "player full name"}'
        ),
    }

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 250,
            "messages": [{"role": "user", "content": prompts[content_type]}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_text = "".join(block.get("text", "") for block in data.get("content", []))
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def post_ai_generated_content(state):
    content_type = random.choice(["trivia", "fact", "quiz"])
    parsed = generate_ai_content(content_type, state.get("posted_texts", []))

    if content_type == "trivia":
        send_message(f"🧠 <b>Football Trivia</b>\n\n{parsed['question']}\n\n<i>Reply with your guess!</i>")
        state["pending"] = {"type": "trivia", "answer": parsed["answer"]}
        state.setdefault("posted_texts", []).append(parsed["question"])
    elif content_type == "fact":
        send_message(f"📚 <b>Did You Know?</b>\n\n{parsed['text']}")
        state.setdefault("posted_texts", []).append(parsed["text"])
    else:
        send_message(f"🎮 <b>Emoji Quiz</b>\n\n{parsed['clue']}\n\n<i>First correct answer wins!</i>")
        state["pending"] = {"type": "quiz", "answer": parsed["answer"]}
        state.setdefault("posted_texts", []).append(parsed["clue"])


def main():
    state = load_state()

    # First, resolve any quiz/trivia posted last run before posting anything new.
    check_pending_answer(state)

    matches = get_today_fixtures()
    now_hour = datetime.datetime.utcnow().hour
    live_matches = [m for m in matches if m.get("status") in ("IN_PLAY", "PAUSED")]

    if live_matches:
        post_live_scores(live_matches)
    elif matches and now_hour == 9:
        post_fixtures_and_poll(matches)
    else:
        post_ai_generated_content(state)

    save_state(state)


if __name__ == "__main__":
    main()
