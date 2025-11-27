# App.py 

import os
import threading
import time
import random
from datetime import datetime, timezone, date
from typing import Dict, Any

from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

# Firebase Import 
import firebase_admin
from firebase_admin import credentials, db

# Twilio Import 
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# App and Config 
load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")

# Firebase setup
FIREBASE_CRED_PATH = os.getenv("FIREBASE_CRED_PATH", "firebase-key.json")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")  
if not os.path.isfile(FIREBASE_CRED_PATH):
    raise FileNotFoundError(
        f"Firebase service account not found at '{FIREBASE_CRED_PATH}'. "
        "Place your service account JSON there or set FIREBASE_CRED_PATH."
    )
if not FIREBASE_DB_URL:
    raise ValueError("Set FIREBASE_DB_URL in your .env (e.g., https://<project-id>.firebaseio.com)")

cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
FIREBASE_REF = db.reference("sensor_readings")

# Twilio setup 
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886") 
TWILIO_WHATSAPP_TO = os.getenv("TWILIO_WHATSAPP_TO", "")  
twilio_client = None

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_TO:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    app.logger.warning("Twilio not fully configured. WhatsApp alerts are disabled.")

# Safe limits
SAFE_PH_MIN = float(os.getenv("SAFE_PH_MIN", "6.5"))
SAFE_PH_MAX = float(os.getenv("SAFE_PH_MAX", "8.5"))
SAFE_WATER_LEVEL_MIN = int(os.getenv("SAFE_WATER_LEVEL_MIN", "20"))   
SAFE_WATER_LEVEL_MAX = int(os.getenv("SAFE_WATER_LEVEL_MAX", "80"))  

# Generator config
GENERATOR_ENABLED = os.getenv("GENERATOR_ENABLED", "true").lower() == "true"
GENERATOR_INTERVAL_SEC = int(os.getenv("GENERATOR_INTERVAL_SEC", "10"))

# Expose DB url to template for client-side Firebase REST reads
FIREBASE_DB_URL_PUBLIC = FIREBASE_DB_URL.rstrip("/")

# Logic 
def now_strings() -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    return {
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timestamp_epoch": int(now_utc.timestamp()),
    }

def generate_sensor_data() -> Dict[str, Any]:
    """Create a new reading (single source)."""
    ph = round(random.uniform(5.0, 9.5), 2)
    water_level = random.randint(5, 95)  
    t = now_strings()
    reading = {
        "timestamp": t["timestamp"],
        "timestamp_epoch": t["timestamp_epoch"],
        "pH": ph,
        "water_level": water_level,
    }
    reading["status"] = compute_status(reading["pH"], reading["water_level"])
    return reading

def compute_status(ph: float, water_level: int) -> str:
    ph_ok = SAFE_PH_MIN <= ph <= SAFE_PH_MAX
    wl_ok = SAFE_WATER_LEVEL_MIN <= water_level <= SAFE_WATER_LEVEL_MAX
    if ph_ok and wl_ok:
        return "OK"
    elif not ph_ok and not wl_ok:
        return "CRITICAL"
    else:
        return "WARNING"

def store_reading_to_firebase(reading: Dict[str, Any]) -> None:
    # Always store the computed status along with the reading
    FIREBASE_REF.push(reading)

# Alert throttling 
ALERT_MIN_INTERVAL_SEC = int(os.getenv("ALERT_MIN_INTERVAL_SEC", "120"))  # at least 2 min between alerts
ALERTS_PER_DAY_LIMIT = int(os.getenv("ALERTS_PER_DAY_LIMIT", "8"))        # Because Twilio has only 9/day trials 
_last_alert_epoch = 0
_alerts_sent_day = date.today()
_alerts_sent_count = 0
_last_status = "OK"  # track transitions

def _reset_daily_counter_if_needed():
    global _alerts_sent_day, _alerts_sent_count
    today = date.today()
    if today != _alerts_sent_day:
        _alerts_sent_day = today
        _alerts_sent_count = 0

def _should_send_alert(new_status: str) -> bool:
    """
    Send alerts only:
    - on transitions from OK -> WARNING/CRITICAL
    - or WARNING -> CRITICAL (escalation)
    - and respect min interval & daily cap
    """
    global _last_status, _last_alert_epoch

    # Daily counter check
    _reset_daily_counter_if_needed()
    if _alerts_sent_count >= ALERTS_PER_DAY_LIMIT:
        return False

    # Transition logic
    transitioned = (
        (_last_status == "OK" and new_status in ("WARNING", "CRITICAL")) or
        (_last_status == "WARNING" and new_status == "CRITICAL")
    )
    if not transitioned:
        return False

    # Interval check
    now = int(time.time())
    if now - _last_alert_epoch < ALERT_MIN_INTERVAL_SEC:
        return False

    return True

def maybe_send_whatsapp_alert(reading: Dict[str, Any]) -> None:
    global _last_alert_epoch, _alerts_sent_count, _last_status

    status = reading.get("status", "OK")
    if status == "OK" or not twilio_client:
        _last_status = status
        return

    if not _should_send_alert(status):
        _last_status = status
        return

    body = (
        " *Sensor Alert* \n\n"
        f"Time: {reading['timestamp']}\n"
        f"pH: {reading['pH']}\n"
        f"Water Level: {reading['water_level']}%\n"
        f"Status: {reading['status']}\n\n"
        f"Safe pH: {SAFE_PH_MIN}–{SAFE_PH_MAX}\n"
        f"Safe Water Level: {SAFE_WATER_LEVEL_MIN}%–{SAFE_WATER_LEVEL_MAX}%"
    )

    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=TWILIO_WHATSAPP_TO,
            body=body
        )
        _last_alert_epoch = int(time.time())
        _alerts_sent_count += 1
        app.logger.info(f"WhatsApp alert sent. Count today: {_alerts_sent_count}")
    except TwilioRestException as e:
        # Don’t crash the generator if Twilio limits are hit
        app.logger.error(f"Twilio error while sending WhatsApp: {e}")
    finally:
        _last_status = status

# Generator
stop_flag = threading.Event()

def generator_loop():
    app.logger.info("Sensor generator started.")
    while not stop_flag.is_set():
        try:
            reading = generate_sensor_data()         # generate once
            store_reading_to_firebase(reading)       # store exactly what we generated
            maybe_send_whatsapp_alert(reading)       # alert based on the same stored reading
        except Exception as e:
            app.logger.exception(f"Generator error: {e}")
        finally:
            stop_flag.wait(GENERATOR_INTERVAL_SEC)
    app.logger.info("Sensor generator stopped.")

generator_thread = None
if GENERATOR_ENABLED:
    generator_thread = threading.Thread(target=generator_loop, daemon=True)
    generator_thread.start()

#  Routes 
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/product")
def product():
    return render_template("product.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/monitoring")
def monitoring():
    return render_template(
        "monitoring.html",
        safe_ph_min=SAFE_PH_MIN,
        safe_ph_max=SAFE_PH_MAX,
        safe_wl_min=SAFE_WATER_LEVEL_MIN,
        safe_wl_max=SAFE_WATER_LEVEL_MAX,
        firebase_db_url_public=FIREBASE_DB_URL_PUBLIC,
    )

@app.route("/simulate")
def simulate_once():
    """
    Manually generate one reading (useful for testing).
    """
    reading = generate_sensor_data()
    store_reading_to_firebase(reading)
    maybe_send_whatsapp_alert(reading)
    return jsonify({"ok": True, "reading": reading})

@app.route("/generator/<action>")
def generator_control(action: str):
    """
    Start/stop the background generator via:
    /generator/start  or  /generator/stop
    """
    global generator_thread
    if action == "stop":
        stop_flag.set()
        return jsonify({"ok": True, "status": "stopping"})
    elif action == "start":
        if generator_thread and generator_thread.is_alive():
            return jsonify({"ok": True, "status": "already-running"})
        stop_flag.clear()
        generator_thread = threading.Thread(target=generator_loop, daemon=True)
        generator_thread.start()
        return jsonify({"ok": True, "status": "started"})
    else:
        return jsonify({"ok": False, "error": "unknown action"}), 400

# Main 
if __name__ == "__main__":
    # NOTE: For production, set debug=False
    app.run(debug=True, host="0.0.0.0", port=5001)
