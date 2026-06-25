import os
import sys

from dotenv import load_dotenv
load_dotenv()

import requests
import operations
import user_operations

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash

from db import get_db, close_db
from auth import get_current_user_id, login_required
from tcgplayer_api import search_card_options
from card_scanner import scan_with_cloud_llm, scan_with_claude, scan_with_tesseract


CARD_CONDITIONS = ["Mint", "Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")
app.teardown_appcontext(close_db)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = user_operations.get_user_by_username(conn, username)

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash(f"Welcome, {user['username']}!", "success")
        return redirect(url_for("collection"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        conn = get_db()
        user_id = user_operations.add_user(conn, username, password)

        if user_id is None:
            flash("Username is already taken.", "error")
            return render_template("register.html")

        session["user_id"] = user_id
        session["username"] = username
        flash(f"Welcome, {username}! Your account has been created.", "success")
        return redirect(url_for("collection"))

    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/inventory")
def inventory():
    conn = get_db()

    name = request.args.get("name", "").strip() or None
    set_code = request.args.get("set_code", "").strip() or None
    rarity = request.args.get("rarity", "").strip() or None
    min_hp = request.args.get("min_hp", "").strip() or None
    max_hp = request.args.get("max_hp", "").strip() or None

    cards = operations.get_cards(
        conn,
        set_code=set_code,
        rarity=rarity,
        min_hp=int(min_hp) if min_hp else None,
        max_hp=int(max_hp) if max_hp else None,
        name_contains=name,
    )

    return render_template(
        "inventory.html",
        cards=cards,
        set_options=operations.get_set_filter_options(conn),
        rarities=operations.get_distinct_rarities(conn),
        filters=request.args,
    )


@app.route("/collection")
@login_required
def collection():
    conn = get_db()
    user_id = get_current_user_id(conn)

    name = request.args.get("name", "").strip() or None
    set_code = request.args.get("set_code", "").strip() or None
    rarity = request.args.get("rarity", "").strip() or None
    condition = request.args.get("condition", "").strip() or None
    min_hp = request.args.get("min_hp", "").strip() or None
    max_hp = request.args.get("max_hp", "").strip() or None

    cards = user_operations.get_user_cards(
        conn, user_id,
        name=name,
        set_code=set_code,
        rarity=rarity,
        condition=condition,
        min_hp=int(min_hp) if min_hp else None,
        max_hp=int(max_hp) if max_hp else None,
    )

    return render_template(
        "collection.html",
        cards=cards,
        set_options=operations.get_set_filter_options(conn),
        rarities=operations.get_distinct_rarities(conn),
        conditions=CARD_CONDITIONS,
        filters=request.args,
    )


@app.route("/collection/add")
@login_required
def collection_add_page():
    return render_template("collection_add.html", conditions=CARD_CONDITIONS)


@app.route("/collection/search", methods=["POST"])
@login_required
def collection_search():
    name = request.form.get("name", "").strip()
    number = request.form.get("number", "").strip() or None
    hp = request.form.get("hp", "").strip() or None

    if not name:
        flash("Please enter a card name.", "error")
        return render_template("collection_add.html", conditions=CARD_CONDITIONS)

    try:
        results = search_card_options(name, number, hp=hp)
    except requests.RequestException:
        flash("The TCG API is currently unreachable. Please try again later.", "error")
        return render_template("collection_add.html", conditions=CARD_CONDITIONS)

    if not results:
        flash(f"No card found for '{name}'.", "error")

    return render_template(
        "collection_add.html", conditions=CARD_CONDITIONS, search_results=results,
        search_name=name, search_number=number or "", search_hp=hp or "",
    )


@app.route("/collection/scan/cloud", methods=["POST"])
@login_required
def scan_cloud():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No image provided."}), 400

    image_bytes = file.read()
    mime_type = file.content_type or "image/png"

    try:
        result = scan_with_cloud_llm(image_bytes, mime_type)

        conn = get_db()
        user_id = get_current_user_id(conn)
        conn.execute("""
            INSERT INTO scan_logs (user_id, scan_type, model, input_tokens, output_tokens, total_tokens, duration_ms, extracted_name, extracted_hp, extracted_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "cloud", result.get("model"), result.get("input_tokens"), result.get("output_tokens"),
              result.get("total_tokens"), result.get("duration_ms"), result.get("name"), result.get("hp"), result.get("number")))
        conn.commit()

        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Cloud scan failed. Check your API key and try again."}), 500


@app.route("/collection/scan/claude", methods=["POST"])
@login_required
def scan_claude_route():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No image provided."}), 400

    image_bytes = file.read()
    mime_type = file.content_type or "image/png"

    try:
        result = scan_with_claude(image_bytes, mime_type)

        conn = get_db()
        user_id = get_current_user_id(conn)
        conn.execute("""
            INSERT INTO scan_logs (user_id, scan_type, model, input_tokens, output_tokens, total_tokens, duration_ms, extracted_name, extracted_hp, extracted_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "claude", result.get("model"), result.get("input_tokens"), result.get("output_tokens"),
              result.get("total_tokens"), result.get("duration_ms"), result.get("name"), result.get("hp"), result.get("number")))
        conn.commit()

        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Claude scan failed. Check your API key and try again."}), 500


@app.route("/collection/scan/local", methods=["POST"])
@login_required
def scan_local():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No image provided."}), 400

    image_bytes = file.read()

    try:
        result = scan_with_tesseract(image_bytes)
        return jsonify(result)
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Local scan failed. Make sure Tesseract is installed."}), 500


@app.route("/collection", methods=["POST"])
@login_required
def collection_add():
    conn = get_db()
    user_id = get_current_user_id(conn)

    card_id = request.form.get("card_id")
    quantity = int(request.form.get("quantity") or 1)
    condition = request.form.get("condition") or "Near Mint"

    if not card_id:
        flash("Please select a card from the search results first.", "error")
        return redirect(url_for("collection_add_page"))

    try:
        imported_card_id = operations.import_card_by_id(conn, card_id)
    except requests.RequestException:
        flash("The TCG API is currently unreachable. Please try again later.", "error")
        return redirect(url_for("collection_add_page"))

    if not imported_card_id:
        flash("Card could not be imported.", "error")
        return redirect(url_for("collection_add_page"))

    user_operations.add_user_card(conn, user_id, imported_card_id, quantity=quantity, condition=condition)
    flash("Card was added to your collection.", "success")
    return redirect(url_for("collection_add_page"))


@app.route("/collection/<card_id>/<condition>/edit", methods=["POST"])
@login_required
def collection_edit(card_id, condition):
    conn = get_db()
    user_id = get_current_user_id(conn)

    quantity = request.form.get("quantity")
    notes = request.form.get("notes")

    user_operations.update_user_card(
        conn, user_id, card_id, condition,
        quantity=int(quantity) if quantity else None,
        notes=notes,
    )
    flash("Entry updated.", "success")
    return redirect(url_for("collection"))


@app.route("/collection/<card_id>/<condition>/delete", methods=["POST"])
@login_required
def collection_delete(card_id, condition):
    conn = get_db()
    user_id = get_current_user_id(conn)

    user_operations.delete_user_card(conn, user_id, card_id, condition)
    flash("Entry removed.", "success")
    return redirect(url_for("collection"))


@app.route("/scan-logs")
@login_required
def scan_logs():
    if session.get("username") != "test":
        flash("Access denied.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    logs = conn.execute("""
        SELECT sl.*, u.username FROM scan_logs sl
        JOIN users u ON sl.user_id = u.id
        ORDER BY sl.created_at DESC
    """).fetchall()
    return render_template("scan_logs.html", logs=logs)


@app.route("/chatbot", methods=["POST"])
@login_required
def chatbot():
    data = request.get_json()
    user_message = (data or {}).get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please enter a message."}), 400

    # TODO: integrate RAG + LLM here
    reply = "I'm not connected to a brain yet — RAG and LLM integration coming soon!"
    return jsonify({"reply": reply})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    app.run(host="127.0.0.1", port=5000, debug=True)