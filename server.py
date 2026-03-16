"""
Adopt Me Farm Dashboard Server
Deploy to Railway: https://railway.app
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import sqlite3, json, time, os

app = Flask(__name__, static_folder=".")
CORS(app)
app.secret_key = "farm_secret_xk29zq"

# ── DB PATH ──
# Use /data/farm.db if Railway volume is mounted there, otherwise fall back to
# a path next to this file so it survives restarts on Railway's ephemeral /tmp.
# To make it truly persistent on Railway: add a Volume mounted at /data.
# Without a volume, configs survive as long as the dyno isn't restarted.
_here = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DB_PATH", os.path.join(_here, "farm.db"))

DASHBOARD_PASSWORD = os.environ.get("DASH_PASSWORD", "testvps12345")

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
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                message TEXT,
                timestamp REAL
            )
        """)
        # Migrate: add any columns that may be missing from older schema
        existing = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
        for col, defn in [
            ("bucks",        "INTEGER DEFAULT 0"),
            ("candy",        "INTEGER DEFAULT 0"),
            ("tickets",      "INTEGER DEFAULT 0"),
            ("current_task", "TEXT DEFAULT 'idle'"),
            ("current_pet",  "TEXT DEFAULT ''"),
            ("potions",      "INTEGER DEFAULT 0"),
            ("money_farmed", "INTEGER DEFAULT 0"),
        ]:
            if col not in existing:
                db.execute(f"ALTER TABLE accounts ADD COLUMN {col} {defn}")
                print(f"[DB] Migrated: added column {col}")
        db.commit()
        print(f"[DB] Ready — {DB}")

init_db()

# Full default config with ALL supported keys
DEFAULT_CONFIG = {
    # Core farming
    "farm_enabled":          False,
    "pet_farm":              False,
    "baby_farm":             False,
    "egg_farm":              False,
    "farm_eggs_type":        "",          # specific egg kind to farm
    "auto_buy_eggs":         False,
    "egg_buy_type":          "",
    "max_pets":              False,
    "max_pets_count":        6,
    "farm_until_full_grown": False,
    "prioritize_friendship": False,
    "selective_pet_farming": False,
    "pet_types_to_farm":     [],
    # Task exclusion
    "task_exclusion":        False,
    "excluded_tasks":        [],
    # Idle / pet pen
    "idle_progression":      False,
    "priority_pets_pen":     [],
    # Age potions
    "auto_age_potion":       False,
    "age_potion_pets":       [],
    # Auto recycle
    "auto_recycle":          False,
    "recycle_common":        False,
    "recycle_uncommon":      False,
    "recycle_rare":          False,
    "recycle_ultra_rare":    False,
    "recycle_legendary":     False,
    "keep_neon_mega":        True,
    "keep_full_grown":       True,
    "selective_recycle":     False,
    "pets_to_recycle":       [],
    # Misc
    "webhook":               "",
    "pet_unlock_webhook":    "",
    "unlock_rarity_filter":  [],
    "auto_neon":             False,
    "get_trade_license":     True,
    # Trade
    "trade_enabled":         False,
    "auto_accept_incoming":  False,
    "trade_target":          "23nuns",
    "trade_mode":            "all",       # all | selective
    "trade_categories":      [],
    "filter_by_age":         False,
    "pet_ages_filter":       [],
    "exclude_neon_mega":     False,
    "exclude_full_grown":    False,
    "trade_legendaries":     True,
    "trade_mega_neons":      True,
    "trade_neons":           False,
    "trade_full_growns":     True,
    "trade_newborns":        False,
    "trade_gifts":           True,
    "trade_food":            False,
    "trade_pet_wear":        False,
    "trade_cocoadiles":      True,
    "switch_on_grown":       False,
    # Auto buy
    "auto_buy":              False,
    "auto_buy_items":        [],
    # Auto open
    "auto_open":             False,
    "gifts_to_open":         [],
    # Auto pay
    "auto_pay":              False,
    "auto_pay_target":       "",
    # Performance
    "disable_3d":            False,
    "reduce_graphics":       False,
    # Commands (transient)
    "jump":                  False,
    "force_trade":           False,
    "scan_interval":         5,
    "join_wait":             30,
}

def is_authed():
    return session.get("authed") is True

# ============================================================
# LOGIN
# ============================================================

LOGIN_HTML = """<!DOCTYPE html>
<html><head><title>Farm Dashboard</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#070709;color:#f0f0f2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.box{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:36px 32px;width:320px}}
h2{{font-size:16px;font-weight:800;margin-bottom:4px}}
.sub{{font-size:12px;color:#505058;margin-bottom:24px}}
input{{width:100%;padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.04);color:#f0f0f2;font-size:13px;outline:none;margin-bottom:12px}}
button{{width:100%;padding:9px;border-radius:8px;border:none;background:rgba(255,255,255,0.9);color:#000;font-size:13px;font-weight:700;cursor:pointer}}
.err{{color:#ef4444;font-size:12px;margin-bottom:12px}}
</style></head><body>
<div class="box">
  <h2>🐾 Adopt Me Dashboard</h2>
  <div class="sub">enter password to continue</div>
  {err}
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="password" autofocus>
    <button type="submit">Login</button>
  </form>
</div></body></html>"""

@app.route("/login", methods=["GET"])
def login_page():
    return LOGIN_HTML.format(err="")

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == DASHBOARD_PASSWORD:
        session["authed"] = True
        return redirect("/")
    return LOGIN_HTML.format(err='<div class="err">Wrong password</div>')

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ============================================================
# ACCOUNT ENDPOINTS (no auth — called by Lua)
# ============================================================

@app.route("/ping", methods=["POST"])
def ping():
    data = request.json or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "no username"}), 400

    with get_db() as db:
        existing = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if existing and existing["config"]:
            try:
                stored = json.loads(existing["config"])
            except Exception:
                stored = {}
            # Merge stored over defaults so new keys are always present
            config = {**DEFAULT_CONFIG, **stored}
        else:
            config = dict(DEFAULT_CONFIG)

        db.execute("""
            INSERT INTO accounts
              (username, display_name, last_ping, inventory, currency, currency_key,
               bucks, candy, tickets, current_task, current_pet, potions, money_farmed,
               last_action, config)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            json.dumps(config),
        ))
        db.commit()

    return jsonify({"ok": True, "config": config})


@app.route("/log", methods=["POST"])
def log():
    data = request.json or {}
    username = data.get("username")
    message  = data.get("message")
    if not username or not message:
        return jsonify({"error": "missing fields"}), 400

    with get_db() as db:
        db.execute("INSERT INTO logs (username, message, timestamp) VALUES (?,?,?)",
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
        if not row or not row["config"]:
            return jsonify(DEFAULT_CONFIG)
        try:
            stored = json.loads(row["config"])
            return jsonify({**DEFAULT_CONFIG, **stored})
        except Exception:
            return jsonify(DEFAULT_CONFIG)


# ============================================================
# DASHBOARD ENDPOINTS (auth required)
# ============================================================

@app.route("/dashboard/accounts", methods=["GET"])
def dashboard_accounts():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as db:
        rows = db.execute("""
            SELECT username, display_name, last_ping, inventory,
                   currency, currency_key, bucks, candy, tickets,
                   current_task, current_pet, potions, money_farmed,
                   last_action, config
            FROM accounts ORDER BY last_ping DESC
        """).fetchall()

    now = time.time()
    accounts = []
    for row in rows:
        inv = {}
        try:
            inv = json.loads(row["inventory"] or "{}")
        except Exception:
            pass
        cfg = {}
        try:
            cfg = json.loads(row["config"] or "{}")
        except Exception:
            pass

        online = (now - (row["last_ping"] or 0)) < 180
        pets   = inv.get("pets", {})
        leg_count  = sum(1 for p in pets.values() if isinstance(p, dict) and p.get("rarity") == "legendary")
        croc_count = sum(1 for p in pets.values() if isinstance(p, dict) and "cocoadile" in str(p.get("kind", "")))

        accounts.append({
            "username":       row["username"],
            "display_name":   row["display_name"],
            "online":         online,
            "last_ping":      row["last_ping"],
            "last_action":    row["last_action"],
            "currency":       row["currency"]     or 0,
            "currency_key":   row["currency_key"] or "eggs_2026",
            "bucks":          row["bucks"]        or 0,
            "candy":          row["candy"]        or 0,
            "tickets":        row["tickets"]      or 0,
            "current_task":   row["current_task"] or "idle",
            "current_pet":    row["current_pet"]  or "",
            "potions":        row["potions"]      or 0,
            "money_farmed":   row["money_farmed"] or 0,
            "pet_count":      len(pets),
            "legendary_count":leg_count,
            "cocoadile_count":croc_count,
            "inventory":      inv,
            "config":         cfg,
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
    if cfg is None:
        return jsonify({"error": "no config"}), 400

    with get_db() as db:
        # Preserve existing config and merge on top
        existing = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if existing and existing["config"]:
            try:
                old = json.loads(existing["config"])
            except Exception:
                old = {}
        else:
            old = {}
        merged = {**DEFAULT_CONFIG, **old, **cfg}
        db.execute("UPDATE accounts SET config=? WHERE username=?",
                   (json.dumps(merged), username))
        db.commit()

    return jsonify({"ok": True})


@app.route("/dashboard/config/bulk", methods=["POST"])
def save_config_bulk():
    if not is_authed():
        return jsonify({"error": "unauthorized"}), 401

    data      = request.json or {}
    usernames = data.get("usernames", [])
    cfg       = data.get("config", {})

    with get_db() as db:
        for username in usernames:
            existing = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
            if existing and existing["config"]:
                try:
                    old = json.loads(existing["config"])
                except Exception:
                    old = {}
            else:
                old = {}
            merged = {**DEFAULT_CONFIG, **old, **cfg}
            db.execute("UPDATE accounts SET config=? WHERE username=?",
                       (json.dumps(merged), username))
        db.commit()

    return jsonify({"ok": True, "updated": len(usernames)})


@app.route("/dashboard/jump/<username>", methods=["POST"])
def jump(username):
    with get_db() as db:
        row = db.execute("SELECT config FROM accounts WHERE username=?", (username,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        try:
            cfg = json.loads(row["config"])
        except Exception:
            cfg = {}
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
            return jsonify({"error": "not found"}), 404
        try:
            cfg = json.loads(row["config"])
        except Exception:
            cfg = {}
        cfg["force_trade"] = True
        db.execute("UPDATE accounts SET config=? WHERE username=?", (json.dumps(cfg), username))
        db.commit()

    return jsonify({"ok": True})


@app.route("/")
def index():
    if not is_authed():
        return redirect("/login")
    return send_from_directory(".", "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
