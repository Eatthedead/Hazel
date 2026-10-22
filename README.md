# 🐿️ Hazel the Wonder Squirrel

Wildlife triage assistant at **hazelthesquirrel.com**, grounded in *The Comprehensive Squirrel Bible* by Tye Lombardi.

- **Sam** (`/goodsam`): for people who just found a baby squirrel. Public, short answers, no medical detail.
- **Hazel** (`/rehabber`): for rehabbers, behind a password. She searches the full Bible for every answer.
- **Release Ready mode** (`app`): the full formulary with a dose calculator. It's built and switched off until the app has real logins.

## How Hazel knows things

She no longer carries a summary in her prompt. She has a **library**:

| File | What it is | Rebuilt by |
|---|---|---|
| `data/chunks.jsonl` | The whole Bible, split into 178 sections | `tools/chunk_bible.py` |
| `data/field_notes.jsonl` | Hazel's original quick-reference notes (fills small gaps; the Bible wins any conflict) | `tools/build_field_notes.py` |
| `data/doses.json` | Formulary doses for the calculator | `tools/doses.py` |

For each question, she looks at the table of contents, searches, reads the 1–4 sections she needs, and answers from them. Dose math is **never** done by the model. `calculate_dose` does it in code.

## Updating Hazel after you edit the Bible

1. In Google Docs, open the Bible and go to **File → Download → Markdown (.md)**.
2. In Cmd, from this folder:
   ```
   python tools/chunk_bible.py "C:\path\to\downloaded.md" data/chunks.jsonl
   python tools/verify_doses.py
   python -m pytest tests
   ```
   `verify_doses.py` checks every printed dose table against the calculator. If it reports a mismatch, either the Bible table or `tools/doses.py` needs fixing before you ship.
3. If you changed a dose, edit it in `tools/doses.py`, run `python tools/doses.py`, then run `verify_doses.py` again.
4. Commit and push to GitHub. Railway deploys automatically.

## Settings (Railway → service → Variables)

| Variable | |
|---|---|
| `ANTHROPIC_API_KEY` | required |
| `SECRET_KEY` | required. A long random string that signs the login cookie. Generate one with `python -c "import secrets;print(secrets.token_hex(32))"` |
| `REHABBER_PASSWORD` | required. The website rehabber password (it's no longer in the code) |
| `HAZEL_MODEL` | optional. Defaults to `claude-opus-4-5` |
| `RATE_LIMIT` | optional. Messages per visitor per 10 minutes (default 30) |

Never put keys or passwords in files in this repo.

## Running locally

```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=...
set SECRET_KEY=anything-long
set REHABBER_PASSWORD=...
set FLASK_DEBUG=1
python app.py
```
Then open http://localhost:5000.

## Security notes

- `/chat` checks the login cookie on the server, so the rehabber password can't be bypassed by calling the API directly.
- Each visitor is rate-limited. Error messages never include internal details.
- Message history from the browser is validated: only plain user/assistant text is accepted, and the size is capped.
