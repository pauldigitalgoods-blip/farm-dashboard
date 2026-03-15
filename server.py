"""
Adopt Me Farm Dashboard Server
Deploy to Railway: https://railway.app
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import sqlite3, json, time, os

app = Flask(__name__, static_folder=".")
CORS(app)
app.secret_key = "farm_secret_xk29zq"  # used for session cookies

DB = "/tmp/farm.db"
DASHBOARD_PASSWORD = "testvps12345"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        # Always drop and recreate to guarantee correct schema
        db.execute("DROP TABLE IF EXISTS accounts")
        db.execute("DROP TABLE IF EXISTS logs")
        db.execute("""
            CREATE TABLE accounts (
                username TEXT PRIMARY KEY,
                display_name TEXT,
                last_ping REAL,
                inventory TEXT,
                currency INTEGER DEFAULT 0,
                currency_key TEXT DEFAULT 'eggs_2026',
                bucks INTEGER DEFAULT 0,
                candy INTEGER DEFAULT 0,
                tickets INTEGER DEFAULT 0,
                current_task TEXT DEFAULT 'idle',
                current_pet TEXT DEFAULT '',
                potions INTEGER DEFAULT 0,
                money_farmed INTEGER DEFAULT 0,
                last_action TEXT,
                config TEXT
            )
        """)
        db.execute("""
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                message TEXT,
                timestamp REAL
            )
        """)
        db.commit()
        print("[DB] Tables created fresh")

init_db()

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
    "auto_buy": [],
    "scan_interval": 5,
    "join_wait": 30
}

def is_authed():
    return session.get("authed") is True

# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET"])
def login_page():
    return """<!DOCTYPE html>
<html>
<head>
<title>Farm Dashboard — Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f0f;color:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:14px;padding:36px 32px;width:320px}
h2{font-size:18px;margin-bottom:6px}
.sub{font-size:13px;color:#888;margin-bottom:24px}
input{width:100%;padding:8px 12px;border-radius:8px;border:1px solid #2a2a2a;background:#222;color:#e8e8e8;font-size:14px;outline:none;margin-bottom:12px}
input:focus{border-color:#1D9E75}
button{width:100%;padding:9px;border-radius:8px;border:none;background:#1D9E75;color:white;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#0F6E56}
.err{color:#f87171;font-size:13px;margin-bottom:12px}
</style>
</head>
<body>
<div class="box">
  <h2>🐾 farm dashboard</h2>
  <div class="sub">enter password to continue</div>
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="password" autofocus>
    <button type="submit">login</button>
  </form>
</div>
</body>
</html>"""

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == DASHBOARD_PASSWORD:
        session["authed"] = True
        return redirect("/")
    return """<!DOCTYPE html>
<html>
<head>
<title>Farm Dashboard — Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f0f;color:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:14px;padding:36px 32px;width:320px}
h2{font-size:18px;margin-bottom:6px}
.sub{font-size:13px;color:#888;margin-bottom:24px}
input{width:100%;padding:8px 12px;border-radius:8px;border:1px solid #2a2a2a;background:#222;color:#e8e8e8;font-size:14px;outline:none;margin-bottom:12px}
input:focus{border-color:#1D9E75}
button{width:100%;padding:9px;border-radius:8px;border:none;background:#1D9E75;color:white;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#0F6E56}
.err{color:#f87171;font-size:13px;margin-bottom:12px}
</style>
</head>
<body>
<div class="box">
  <h2>🐾 farm dashboard</h2>
  <div class="sub">enter password to continue</div>
  <div class="err">wrong password</div>
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="password" autofocus>
    <button type="submit">login</button>
  </form>
</div>
</body>
</html>"""

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ============================================================
# ACCOUNT ENDPOINTS (called by Lua script — no auth needed)
# ============================================================

@app.route("/ping", methods=["POST"])
def ping():
    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "no username"}), 400

    with get_db() as db:
        existing = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        config = existing["config"] if existing else json.dumps(DEFAULT_CONFIG)

        db.execute("""
            INSERT INTO accounts (username, display_name, last_ping, inventory, currency, currency_key, bucks, candy, tickets, current_task, current_pet, potions, money_farmed, last_action, config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                last_ping=excluded.last_ping,
                inventory=excluded.inventory,
                currency=excluded.currency,
                currency_key=excluded.currency_key,
                bucks=excluded.bucks,
                candy=excluded.candy,
                tickets=excluded.tickets,
                current_task=excluded.current_task,
                current_pet=excluded.current_pet,
                potions=excluded.potions,
                money_farmed=excluded.money_farmed,
                last_action=excluded.last_action
        """, (
            username,
            data.get("display_name", username),
            time.time(),
            json.dumps(data.get("inventory", {})),
            data.get("currency", 0),
            data.get("currency_key", "eggs_2026"),
            data.get("bucks", 0),
            data.get("candy", 0),
            data.get("tickets", 0),
            data.get("current_task", "idle"),
            data.get("current_pet", ""),
            data.get("potions", 0),
            data.get("money_farmed", 0),
            data.get("last_action", data.get("current_task", "idle")),
            config
        ))
        db.commit()

    return jsonify({"ok": True, "config": json.loads(config)})


@app.route("/log", methods=["POST"])
def log():
    data = request.json or {}
    username = data.get("username")
    message = data.get("message")
    if not username or not message:
        return jsonify({"error": "missing fields"}), 400

    with get_db() as db:
        db.execute("INSERT INTO logs (username, message, timestamp) VALUES (?, ?, ?)",
                   (username, message, time.time()))
        db.execute("UPDATE accounts SET last_action=? WHERE username=?", (message, username))
        db.execute("""
            DELETE FROM logs WHERE username=? AND id NOT IN (
                SELECT id FROM logs WHERE username=? ORDER BY timestamp DESC LIMIT 50
            )
        """, (username, username))
        db.commit()

    return jsonify({"ok": True})


@app.route("/config/<username>", methods=["GET"])
def get_config(username):
    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify(DEFAULT_CONFIG)
        return jsonify(json.loads(row["config"]))


# ============================================================
# DASHBOARD ENDPOINTS (password protected)
# ============================================================

@app.route("/dashboard/accounts", methods=["GET"])
def dashboard_accounts():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as db:
        rows = db.execute("""
            SELECT username, display_name, last_ping, inventory, currency, currency_key, bucks, candy, tickets, current_task, current_pet, potions, money_farmed, last_action, config
            FROM accounts ORDER BY last_ping DESC
        """).fetchall()

    now = time.time()
    accounts = []
    for row in rows:
        inv = json.loads(row["inventory"] or "{}")
        cfg = json.loads(row["config"] or "{}")
        online = (now - (row["last_ping"] or 0)) < 180

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
            "bucks": row["bucks"] if "bucks" in row.keys() else 0,
            "candy": row["candy"] if "candy" in row.keys() else 0,
            "tickets": row["tickets"] if "tickets" in row.keys() else 0,
            "current_task": row["current_task"] if "current_task" in row.keys() else "idle",
            "current_pet": row["current_pet"] if "current_pet" in row.keys() else "",
            "potions": row["potions"] if "potions" in row.keys() else 0,
            "money_farmed": row["money_farmed"] if "money_farmed" in row.keys() else 0,
            "pet_count": len(pets),
            "legendary_count": leg_count,
            "cocoadile_count": croc_count,
            "inventory": inv,
            "config": cfg
        })

    return jsonify(accounts)


@app.route("/dashboard/logs/<username>", methods=["GET"])
def dashboard_logs(username):
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as db:
        rows = db.execute("""
            SELECT message, timestamp FROM logs
            WHERE username=? ORDER BY timestamp DESC LIMIT 30
        """, (username,)).fetchall()
    return jsonify([{"message": r["message"], "timestamp": r["timestamp"]} for r in rows])


@app.route("/dashboard/config/<username>", methods=["POST"])
def save_config(username):
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

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
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    data = request.json or {}
    usernames = data.get("usernames", [])
    cfg = data.get("config", {})

    with get_db() as db:
        for username in usernames:
            db.execute("UPDATE accounts SET config=? WHERE username=?",
                       (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True, "updated": len(usernames)})


@app.route("/dashboard/jump/<username>", methods=["POST"])
def jump(username):
    """Sends a jump command — script picks it up on next config poll (30s)"""
    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify({"error": "account not found"}), 404
        cfg = json.loads(row["config"])
        cfg["jump"] = True
        db.execute("UPDATE accounts SET config=? WHERE username=?", (json.dumps(cfg), username))
        db.commit()
    return jsonify({"ok": True})


@app.route("/dashboard/force_trade/<username>", methods=["POST"])
def force_trade(username):
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify({"error": "account not found"}), 404
        cfg = json.loads(row["config"])
        cfg["force_trade"] = True
        db.execute("UPDATE accounts SET config=? WHERE username=?", (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True})


# Serve dashboard — redirect to login if not authed
@app.route("/")
def index():
    if not is_authed():
        return redirect("/login")
    return send_from_directory(".", "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
