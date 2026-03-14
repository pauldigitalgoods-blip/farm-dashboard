"""
Adopt Me Farm Dashboard Server
Deploy to Railway: https://railway.app
Just upload this file + requirements.txt, Railway handles the rest.
Your URL will be: https://yourapp.railway.app
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, json, time, os

app = Flask(__name__, static_folder=".")
CORS(app)

DB = "farm.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                display_name TEXT,
                last_ping REAL,
                inventory TEXT,
                currency INTEGER DEFAULT 0,
                currency_key TEXT DEFAULT 'eggs.2026',
                last_action TEXT,
                config TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                message TEXT,
                timestamp REAL
            )
        """)
        db.commit()

init_db()

# Default config for new accounts
DEFAULT_CONFIG = {
    "trade_target": "23nuns",
    "trade_legendaries": True,
    "trade_mega_neons": True,
    "trade_neons": False,
    "trade_full_growns": True,
    "trade_newborns": False,
    "trade_gifts": True,
    "trade_food": False,
    "trade_pet_wear": False,
    "trade_cocoadiles": True,
    "auto_buy": [],  # list of {name, remote, category, item_id, max_count}
    "scan_interval": 5,
    "join_wait": 30
}

# ============================================================
# ACCOUNT ENDPOINTS (called by Lua script)
# ============================================================

@app.route("/ping", methods=["POST"])
def ping():
    """Called by script every 2 mins — updates inventory + currency"""
    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "no username"}), 400

    with get_db() as db:
        existing = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        config = existing["config"] if existing else json.dumps(DEFAULT_CONFIG)

        db.execute("""
            INSERT INTO accounts (username, display_name, last_ping, inventory, currency, currency_key, last_action, config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                last_ping=excluded.last_ping,
                inventory=excluded.inventory,
                currency=excluded.currency,
                currency_key=excluded.currency_key,
                last_action=excluded.last_action
        """, (
            username,
            data.get("display_name", username),
            time.time(),
            json.dumps(data.get("inventory", {})),
            data.get("currency", 0),
            data.get("currency_key", "eggs.2026"),
            data.get("last_action", "")
        ))
        db.commit()

    return jsonify({"ok": True, "config": json.loads(config)})


@app.route("/log", methods=["POST"])
def log():
    """Script sends activity logs here"""
    data = request.json or {}
    username = data.get("username")
    message = data.get("message")
    if not username or not message:
        return jsonify({"error": "missing fields"}), 400

    with get_db() as db:
        db.execute("INSERT INTO logs (username, message, timestamp) VALUES (?, ?, ?)",
                   (username, message, time.time()))
        # Also update last_action
        db.execute("UPDATE accounts SET last_action=? WHERE username=?", (message, username))
        # Keep only last 50 logs per account
        db.execute("""
            DELETE FROM logs WHERE username=? AND id NOT IN (
                SELECT id FROM logs WHERE username=? ORDER BY timestamp DESC LIMIT 50
            )
        """, (username, username))
        db.commit()

    return jsonify({"ok": True})


@app.route("/config/<username>", methods=["GET"])
def get_config(username):
    """Script polls this every 30s to get latest config"""
    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify(DEFAULT_CONFIG)
        return jsonify(json.loads(row["config"]))


# ============================================================
# DASHBOARD ENDPOINTS (called by the webpage)
# ============================================================

@app.route("/dashboard/accounts", methods=["GET"])
def dashboard_accounts():
    """Returns all accounts with online status"""
    with get_db() as db:
        rows = db.execute("""
            SELECT username, display_name, last_ping, inventory, currency, currency_key, last_action, config
            FROM accounts ORDER BY last_ping DESC
        """).fetchall()

    now = time.time()
    accounts = []
    for row in rows:
        inv = json.loads(row["inventory"] or "{}")
        cfg = json.loads(row["config"] or "{}")
        online = (now - (row["last_ping"] or 0)) < 180  # online if pinged within 3 mins

        # Count pets by type
        pets = inv.get("pets", {})
        leg_count = sum(1 for p in pets.values() if isinstance(p, dict) and p.get("rarity") == "legendary")
        croc_count = sum(1 for p in pets.values() if isinstance(p, dict) and "cocoadile" in str(p.get("kind", "")))

        accounts.append({
            "username": row["username"],
            "display_name": row["display_name"],
            "online": online,
            "last_ping": row["last_ping"],
            "last_action": row["last_action"],
            "currency": row["currency"],
            "currency_key": row["currency_key"],
            "pet_count": len(pets),
            "legendary_count": leg_count,
            "cocoadile_count": croc_count,
            "inventory": inv,
            "config": cfg
        })

    return jsonify(accounts)


@app.route("/dashboard/logs/<username>", methods=["GET"])
def dashboard_logs(username):
    with get_db() as db:
        rows = db.execute("""
            SELECT message, timestamp FROM logs
            WHERE username=? ORDER BY timestamp DESC LIMIT 30
        """, (username,)).fetchall()
    return jsonify([{"message": r["message"], "timestamp": r["timestamp"]} for r in rows])


@app.route("/dashboard/config/<username>", methods=["POST"])
def save_config(username):
    """Dashboard saves config for one account"""
    cfg = request.json
    if not cfg:
        return jsonify({"error": "no config"}), 400

    with get_db() as db:
        db.execute("UPDATE accounts SET config=? WHERE username=?",
                   (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True})


@app.route("/dashboard/config/bulk", methods=["POST"])
def save_config_bulk():
    """Dashboard saves same config for multiple accounts"""
    data = request.json or {}
    usernames = data.get("usernames", [])
    cfg = data.get("config", {})

    with get_db() as db:
        for username in usernames:
            db.execute("UPDATE accounts SET config=? WHERE username=?",
                       (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True, "updated": len(usernames)})


@app.route("/dashboard/force_trade/<username>", methods=["POST"])
def force_trade(username):
    """Queues a force trade command — script picks it up on next config poll"""
    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify({"error": "account not found"}), 404
        cfg = json.loads(row["config"])
        cfg["force_trade"] = True
        db.execute("UPDATE accounts SET config=? WHERE username=?", (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True})


# Serve dashboard HTML
@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
