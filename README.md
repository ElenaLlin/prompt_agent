# Goal Reflection Agent

A LangGraph-powered conversational agent that runs on **Vercel** from the same codebase.

---

## Architecture

```
app.py                      ← Flask entry point
PromptBasedAgent.py         ← LangGraph agent 
prompts/
  agent.prompt              ← System prompt
requirements.txt
.env.example                ← Copy → .env for local dev
```

### Thread IDs (UUID5)

Each conversation is keyed by a **deterministic UUID5** derived from the patient ID (when provided) or a random per-browser-session seed.  
`uuid.uuid5(uuid.NAMESPACE_DNS, seed)`.

---

## Local development

```bash
# 1. Clone & install
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# Edit .env — add at minimum OPENAI_API_KEY

# 3. Run
flask --app app.py --debug run
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `SUPABASE_URL` | ✅ | Supabase URL |
| `SUPABASE_KEY` | ✅ | Supabase KEY |
| `ADMIN_ _PASSWORD` | ✅ | Password required for `/admin` |

The admin study builder is protected by `ADMIN_PASSWORD`. Set it in `.env` or
your deployment environment before starting the app. The app fails closed with
a `503` response if the variable is missing.

## Study languages

When creating a study, enter one language per line using an ISO two-letter
locale code followed by the display name, for example:

```text
en: English
es: Español
pt: Português
```

The participant page builds its language selector from the active study's
`language_options`. A matching Babel catalog must exist under
`translations/<code>/LC_MESSAGES/` for translated interface text; without one,
the interface falls back to the original message text.
