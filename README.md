# Daily Champions League Telegram Poster (100% Free, No Server)

This bot posts to your Telegram channel **every day automatically**, with zero manual work
after setup. It uses **GitHub Actions** as the free scheduler — no hosting, no server, no cost.

What it posts (rotates automatically):
- 🏆 Today's Champions League fixtures + a live prediction poll (when there's a match)
- 🧠 Football trivia questions
- 📚 Fun facts about the competition
- 🎮 Emoji "guess the player" quizzes

---

## Setup (15 minutes, one-time)

### 1. Create your Telegram bot
1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, follow the prompts, and copy the **bot token** it gives you
   (looks like `123456789:ABCdefGhIJKlmNoPQRstuVwxyz`).

### 2. Add the bot to your channel
1. Open your Telegram channel → **Administrators** → **Add Admin** → search your bot's
   username → give it permission to **Post Messages**.
2. Get your channel's chat ID:
   - Post any message in the channel.
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser.
   - Look for `"chat":{"id":-1001234567890...}` — that negative number is your `TELEGRAM_CHAT_ID`.
   - (If getUpdates shows nothing, forward a channel message to **@userinfobot** instead — it shows the ID directly.)

### 3. Get a free football data API key
1. Register free at https://www.football-data.org/client/register
2. Copy the API key from your account page.
   (Free tier covers Champions League fixtures with a small rate limit — plenty for one call/day.)

### 4. Put this code on GitHub
1. Create a new **public or private** GitHub repo (e.g. `cl-daily-bot`).
2. Upload all files in this folder to the repo (keep the `.github/workflows/` folder structure intact).

### 5. Add your secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | your bot token from step 1 |
| `TELEGRAM_CHAT_ID` | your channel ID from step 2 |
| `FOOTBALL_DATA_API_KEY` | your key from step 3 |

### 6. Test it
Go to the **Actions** tab → **Daily Football Post** → **Run workflow** (manual trigger button).
Check your Telegram channel — you should see a post within a minute.

### 7. Done
From now on, it runs **automatically every day at 09:00 UTC** (edit the `cron` line in
`.github/workflows/daily_post.yml` to change the time — cron times are always in UTC).

---

## Customizing content
- Edit `content_bank.json` to add/remove trivia, facts, or emoji quizzes — no code changes needed.
- Add more competitions (Premier League, La Liga, etc.) by adding more competition codes
  and fixture calls in `main.py` (e.g. `"PL"`, `"PD"`).
- Want images/memes instead of text? Telegram's `sendPhoto` API can be added the same way
  `sendMessage`/`sendPoll` work here — happy to extend this if you want that next.

## Notes on WhatsApp
WhatsApp doesn't allow free automated posting to groups/channels without either:
- The official **WhatsApp Business API** (needs Meta approval + a paid provider like
  Twilio or 360dialog), or
- Unofficial browser-automation tools, which violate WhatsApp's Terms of Service and
  risk your number being banned.

If you later get a WhatsApp Business API set up, the same `content_bank.json` and posting
logic here can be reused — just swap the `send_message`/`send_poll` functions for the
WhatsApp API calls.
