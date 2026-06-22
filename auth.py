from functools import wraps

from flask import flash, redirect, session, url_for

import user_operations


def get_current_user_id(conn):
    """Solange nicht eingeloggt, wird der erste User der DB verwendet."""
    if "user_id" in session:
        return session["user_id"]

    cur = conn.cursor()
    cur.execute("SELECT id FROM users LIMIT 1")
    row = cur.fetchone()
    if row:
        return row["id"]
    return user_operations.add_user(conn, "test", "test")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access 'My Collection'.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped
