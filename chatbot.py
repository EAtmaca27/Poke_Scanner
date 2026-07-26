import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHAT_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are PokéChat, a assistant for the Poke Scanner app — a Pokémon TCG collection tracker.

Answer questions about the user's collection, Pokémon TCG rules, card values, and deck building.

Rules for every reply:
- Plain text only. No markdown, no bullet points, no headers, no tables.
- Be direct and concise. Only say what was asked.
- If the collection is empty, say so briefly.

The user's current collection:
{collection_context}"""


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_history(conn, user_id):
    ensure_table(conn)
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def clear_history(conn, user_id):
    ensure_table(conn)
    conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()


def append_to_chat_history(conn, user_id, role, content):
    conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content),
    )
    conn.commit()


def build_collection_context(conn, user_id):
    rows = conn.execute(
        """
        SELECT c.name, c.set_code, c.rarity, c.hp,
               c.tcgplayer_price, uc.quantity, uc.condition, uc.notes
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        WHERE uc.user_id = ?
        ORDER BY c.name
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return "The user currently has no cards in their collection."

    lines = ["Name | Set | Rarity | HP | Qty | Condition | TCGPlayer Price | Notes"]
    for r in rows:
        price = f"${r['tcgplayer_price']:.2f}" if r["tcgplayer_price"] else "N/A"
        lines.append(
            f"{r['name']} | {r['set_code']} | {r['rarity'] or 'N/A'} | "
            f"{r['hp'] or 'N/A'} HP | x{r['quantity']} | {r['condition']} | {price} | {r['notes'] or ''}"
        )
    return "\n".join(lines)


def chat(conn, user_id, user_message):
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in the .env file.")

    history = get_history(conn, user_id)
    collection_context = build_collection_context(conn, user_id)
    system = SYSTEM_PROMPT.format(collection_context=collection_context)

    messages = history + [{"role": "user", "content": user_message}]

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CHAT_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    reply = response.content[0].text

    append_to_chat_history(conn, user_id, "user", user_message)
    append_to_chat_history(conn, user_id, "assistant", reply)

    return reply
