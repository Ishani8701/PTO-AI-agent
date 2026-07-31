# Time-Off Management Agent — Bootcamp Shell

This is the **starting point** for the bootcamp. It is deliberately small: a
chat UI, a user switcher, and a backend that holds a plain conversation with an
LLM. It does **not** answer policy questions, check balances, or submit
time-off requests yet — you build all of that.

**👉 The lab itself lives in [`coursework.md`](coursework.md). Read that next.**

## What's in the box

```
app/
  config.py     env vars and paths
  main.py       FastAPI: serves the UI, /api/users, /api/chat (plain chat)
  index.html    single-file chat UI with a user switcher
data/
  employees.json   the people you can act as
  balances.json    mock leave balances
  requests.json    mock existing time-off requests
samples/
  policies/        example policy documents you can copy or adapt
```

The `data/` files are mock data for you to use as you build. The
`samples/policies/` files are reference material — nothing reads them yet.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # then fill in your Azure OpenAI credentials

uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## What works on day one

- The UI loads and the **user switcher** is populated from `data/employees.json`.
- You can chat with the bot — it talks, and it knows which employee you're
  acting as. Ask it for your balance and it will tell you, honestly, that it
  can't do that yet.

Everything past "it can chat" is the lab. Head to [`coursework.md`](coursework.md).

> As you add capabilities you'll pull in more libraries (a vector store, an
> agent framework, and so on). Add them to `requirements.txt` as you go.
