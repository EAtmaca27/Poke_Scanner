import sqlite3
import json

from tcgplayer_api import get_card_by_id, get_card_prices


# ----- CRUD Operations -----
def add_set(conn, set_id, name, set_code, release_date=None, total_cards=None, symbol_url=None):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO sets (id, name, set_code, release_date, total_cards, symbol_url)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (set_id, name, set_code, release_date, total_cards, symbol_url))
    conn.commit()


def add_card(conn, card_id, name, set_code, number_in_set, hp=None, body=None, rarity=None,
             set_id=None, image_url=None, tcgplayer_price=None, cardmarket_price=None):
    cur = conn.cursor()

    if body is not None:
        body = json.dumps(body)

    cur.execute("SELECT id FROM cards WHERE id = ?", (card_id,))

    if cur.fetchone():
        cur.execute("UPDATE cards SET quantity = quantity + 1 WHERE id = ?", (card_id,))
        conn.commit()
        return True

    try:
        cur.execute("""
            INSERT INTO cards (id, name, hp, body, set_code, number_in_set, rarity,
                                set_id, image_url, tcgplayer_price, cardmarket_price, last_price_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (card_id, name, hp, body, set_code, number_in_set, rarity,
              set_id, image_url, tcgplayer_price, cardmarket_price))
        conn.commit()
        return True

    except sqlite3.IntegrityError as e:
        print(f"Error adding card: {e}")
        return False


def get_cards(conn, set_code=None, rarity=None, min_hp=None, max_hp=None, name_contains=None):
    cur = conn.cursor()

    query = "SELECT cards.*, sets.name AS set_name FROM cards LEFT JOIN sets ON cards.set_id = sets.id"
    conditions = []
    values = []

    if set_code is not None:
        conditions.append("cards.set_code = ?")
        values.append(set_code)

    if rarity is not None:
        conditions.append("cards.rarity = ?")
        values.append(rarity)

    if min_hp is not None:
        conditions.append("cards.hp >= ?")
        values.append(min_hp)

    if max_hp is not None:
        conditions.append("cards.hp <= ?")
        values.append(max_hp)

    if name_contains is not None:
        conditions.append("cards.name LIKE ?")
        values.append(f"%{name_contains}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cur.execute(query, values)
    return cur.fetchall()


def update_card(conn, card_id, name=None, hp=None, body=None, set_code=None, number_in_set=None, rarity=None):
    cur = conn.cursor()

    fields = []
    values = []

    if name is not None:
        fields.append("name = ?")
        values.append(name)

    if hp is not None:
        fields.append("hp = ?")
        values.append(hp)

    if body is not None:
        fields.append("body = ?")
        values.append(json.dumps(body))

    if set_code is not None:
        fields.append("set_code = ?")
        values.append(set_code)

    if number_in_set is not None:
        fields.append("number_in_set = ?")
        values.append(number_in_set)

    if rarity is not None:
        fields.append("rarity = ?")
        values.append(rarity)

    if not fields:
        raise ValueError("update_card called without fields to update")

    query = f"UPDATE cards SET {', '.join(fields)} WHERE id = ?"
    values.append(card_id)

    cur.execute(query, values)
    conn.commit()

    return cur.rowcount > 0


def delete_card(conn, card_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    return cur.rowcount > 0


def get_distinct_set_codes(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT set_code FROM cards ORDER BY set_code")
    return [row["set_code"] for row in cur.fetchall()]


def get_distinct_rarities(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT rarity FROM cards WHERE rarity IS NOT NULL ORDER BY rarity")
    return [row["rarity"] for row in cur.fetchall()]


def get_set_filter_options(conn):
    """Set-Filteroptionen aus lokal gespeicherten Sets (stimmen immer mit den Karten überein)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT s.set_code, s.name
        FROM sets s
        JOIN cards c ON c.set_id = s.id
        ORDER BY s.name
    """)
    return [{"code": row["set_code"], "name": row["name"]} for row in cur.fetchall()]


# ----- TCG-API Import -----
def import_card_by_id(conn, card_id):
    card = get_card_by_id(card_id)
    return import_card(conn, card)


def import_card(conn, card):
    hp_raw = card.get("hp")
    hp = int(hp_raw) if hp_raw else None

    body = {
        "attacks": card.get("attacks"),
        "weaknesses": card.get("weaknesses"),
        "retreat_cost": card.get("retreatCost"),
    }

    prices = get_card_prices(card)
    tcgplayer_price = next(
        (p["market"] for p in prices["tcgplayer"].values() if p.get("market") is not None),
        None
    )
    cardmarket_price = prices["cardmarket"].get("trendPrice")

    set_info = card["set"]
    set_code = set_info.get("ptcgoCode") or set_info["name"]

    add_set(
        conn,
        set_id=set_info["id"],
        name=set_info["name"],
        set_code=set_code,
        release_date=set_info.get("releaseDate"),
        total_cards=set_info.get("total"),
        symbol_url=set_info.get("images", {}).get("symbol"),
    )

    added = add_card(
        conn,
        card_id=card["id"],
        name=card["name"],
        set_code=set_code,
        number_in_set=card["number"],
        hp=hp,
        body=body,
        rarity=card.get("rarity"),
        set_id=set_info["id"],
        image_url=card["images"]["large"],
        tcgplayer_price=tcgplayer_price,
        cardmarket_price=cardmarket_price,
    )

    return card["id"] if added else None
