def generate_ai_content(content_type, posted_texts):
    """Ask Gemini to write a fresh trivia question, fun fact, or emoji quiz (with answer)."""
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
        GEMINI_URL,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompts[content_type]}]
                }
            ]
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)
