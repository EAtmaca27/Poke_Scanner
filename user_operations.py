import sqlite3
import uuid

from werkzeug.security import generate_password_hash

# ----- User Cruds -----

def add_user(conn, username, password):
    cur = conn.cursor()
    user_id = str(uuid.uuid4())
    try:
        cur.execute("""
            INSERT INTO users (id, username, password)
            VALUES (?, ?, ?)
        """, (user_id, username, generate_password_hash(password)))
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        print(f"User '{username}' already exists.")
        return None


def get_user_by_username(conn, username):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cur.fetchone()


def add_user_card(conn, user_id, card_id, quantity=1, condition="Near Mint", notes=None):
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id FROM user_cards
        WHERE user_id = ? AND card_id = ? AND condition = ?""",
        (user_id, card_id, condition))

    if cur.fetchone():
        cur.execute("""
            UPDATE user_cards
            SET quantity = quantity + ?
            WHERE user_id = ? AND card_id = ? AND condition = ?""",
            (quantity, user_id, card_id, condition))
    else:
        cur.execute("""
            INSERT INTO user_cards (user_id, card_id, quantity, condition, notes)
            VALUES (?, ?, ?, ?, ?)""", (user_id, card_id, quantity, condition, notes))

    cur.execute("UPDATE cards SET quantity = quantity + ? WHERE id = ?", (quantity, card_id))

    conn.commit()
    return "Card added to inventory"


def get_user_cards(conn, user_id, name=None, min_hp=None, max_hp=None, set_code=None, quantity=None, condition=None, rarity=None):
    curr = conn.cursor()

    conditions = ["uc.user_id = ?"]
    values = [user_id]

    if name is not None:
        conditions.append("c.name LIKE ?")
        values.append(f"%{name}%")

    if min_hp is not None:
        conditions.append("c.hp >= ?")
        values.append(min_hp)

    if max_hp is not None:
        conditions.append("c.hp <= ?")
        values.append(max_hp)

    if set_code is not None:
        conditions.append("c.set_code = ?")
        values.append(set_code)

    if quantity is not None:
        conditions.append("uc.quantity >= ?")
        values.append(quantity)

    if condition is not None:
        conditions.append("uc.condition = ?")
        values.append(condition)

    if rarity is not None:
        conditions.append("c.rarity = ?")
        values.append(rarity)

    query = f"""SELECT uc.*, c.name, c.hp, c.body, c.set_code, c.number_in_set, c.rarity, c.image_url, c.tcgplayer_price, c.cardmarket_price, s.name AS set_name
                FROM user_cards uc
                JOIN cards c ON uc.card_id = c.id
                LEFT JOIN sets s ON c.set_id = s.id
                WHERE {' AND '.join(conditions)}"""
    curr.execute(query, values)
    return curr.fetchall()


def update_user_card(conn, user_id, card_id, condition, quantity=None, notes=None):
    curr = conn.cursor()

    fields = []
    values = []

    if quantity is not None:
        fields.append("quantity = ?")
        values.append(quantity)

    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)

    if not fields:
        raise ValueError("update_user_card called without fields to update")

    query = f"""UPDATE user_cards
                SET {', '.join(fields)}
                WHERE user_id = ? AND card_id = ? AND condition = ?"""
    values.extend([user_id, card_id, condition])

    curr.execute(query, values)
    conn.commit()

    return curr.rowcount > 0


def delete_user_card(conn, user_id, card_id, condition):
    curr = conn.cursor()
    curr.execute("""
        SELECT quantity FROM user_cards
        WHERE user_id = ? AND card_id = ? AND condition = ?""",
        (user_id, card_id, condition))
    row = curr.fetchone()

    if not row:
        return False

    if row["quantity"] > 1:
        curr.execute("""
            UPDATE user_cards SET quantity = quantity - 1
            WHERE user_id = ? AND card_id = ? AND condition = ?""",
            (user_id, card_id, condition))
    else:
        curr.execute("""
            DELETE FROM user_cards
            WHERE user_id = ? AND card_id = ? AND condition = ?""",
            (user_id, card_id, condition))

    conn.commit()
    return True