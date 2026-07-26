# Poke Scanner

A Flask web app for tracking a Pokémon TCG card collection. Search for cards via
the [pokemontcg.io](https://pokemontcg.io) API, scan physical cards to auto-fill
their name/HP/number using an LLM or local OCR, and manage a personal collection
with quantities, conditions, and notes. Includes a public inventory view and an
in-app chatbot for questions about your collection.

## Features

- **Public inventory** — browse every card that's been imported by any user, filterable by name, set, rarity, and HP range (no login required).
- **Personal collection** — logged-in users track their own cards with quantity, condition, and notes.
- **Card search & import** — look up cards by name/number via the TCG API and add them to your collection.
- **Card scanning** — snap or upload a photo of a card and extract its name, HP, and number using:
  - OpenAI (`gpt-4.1-mini`)
  - Claude (`claude-opus-4-8`)
  - Llama 3.2 Vision via NVIDIA NIM
  - Local OCR (Tesseract), no API key required
- **PokéChat** — a Claude-powered chatbot (bottom-right panel) that can answer questions about your collection.
- **Scan logs** — token usage/latency per scan, viewable at `/scan-logs` (restricted to the `test` user).

## Tech stack

- Python / Flask
- SQLite (`data/pokemon.db`)
- Vanilla HTML/CSS/JS templates (Jinja2)
- [pokemontcg.io](https://pokemontcg.io) API for card data
- Anthropic, OpenAI, and NVIDIA NIM APIs for card scanning and chat

## Setup

1. **Install dependencies:**

   ```bash
   pip install flask requests python-dotenv anthropic werkzeug pytesseract pillow
   ```

   `pytesseract` is only needed for the local (offline) scan option, and also
   requires [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) to be
   installed on your machine.

2. **Configure environment variables** — create a `.env` file in the project root:

   ```env
   SECRET_KEY=your-flask-secret-key
   POKEMON_TCG_API_KEY=your-pokemontcg.io-api-key
   ANTHROPIC_API_KEY=your-anthropic-api-key
   OPENAI_API_KEY=your-openai-api-key
   NVIDIA_KIMI_API_KEY=your-nvidia-nim-api-key
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

   All API keys are optional except the ones needed for the scan/chat features
   you intend to use — each route returns a clear error if its key is missing.

3. **Initialize the database:**

   ```bash
   python data/db_init.py
   ```

4. **Run the app:**

   ```bash
   python app.py
   ```

   The app will be available at `http://127.0.0.1:5000`.

## Project structure

```
app.py              Flask routes/app entry point
auth.py             Login-required decorator and current-user helper
db.py               SQLite connection handling (per-request)
operations.py       Card/set CRUD and TCG API import logic
user_operations.py  User accounts and per-user collection entries
tcgplayer_api.py     pokemontcg.io API client
card_scanner.py      Image-to-card-data extraction (OpenAI/Claude/Llama Vision/Tesseract)
chatbot.py           PokéChat: chat history + Claude-powered replies
data/db_init.py      Creates the SQLite schema
templates/           Jinja2 templates
static/style.css     App styling
endpoints.md         Route reference
```

See [endpoints.md](endpoints.md) for the full API/route reference.