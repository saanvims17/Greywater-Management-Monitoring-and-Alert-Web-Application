# Greywater-Management-Monitoring-and-Alert-Web-Application
Project is Built using Flask,Firebase Realtime Database,and Twilio to simulate pH and water-level readings and store them as entries. Developed a live monitoring dashboard and implemented automated WhatsApp alerts when threshold limits are exceeded. Skills Used: Python,Flask,Firebase Realtime Database,Twilio WhatsApp API,HTML,CSS,JavaScript
<img width="1470" height="656" alt="Screenshot 2025-11-27 at 12 11 50 PM" src="https://github.com/user-attachments/assets/59f3dedc-3361-4fbf-9633-c2adfee8e95e" />
<img width="1470" height="797" alt="Screenshot 2025-11-27 at 12 12 31 PM" src="https://github.com/user-attachments/assets/1c8ed6dc-24af-461b-9e40-ae8b809283a4" />
<img width="1467" height="793" alt="Screenshot 2025-11-27 at 12 12 46 PM" src="https://github.com/user-attachments/assets/8bfd069f-846e-4acd-86bc-b87d58b816b2" />




**Simulates sensor data**

**Randomly generates:**

pH (5.0–9.5)

water_level (5–95%)

**Classifies each reading as:**

OK

WARNING

CRITICAL

based on safe ranges from environment variables.

Stores readings in Firebase Realtime Database

Uses firebase_admin SDK

Pushes each reading under sensor_readings with:

timestamp (UTC)

epoch time

pH

water_level

status

**Sends WhatsApp alerts via Twilio**

Sends alerts only when:

status transitions from:

OK → WARNING or OK → CRITICAL

WARNING → CRITICAL

AND:

at least ALERT_MIN_INTERVAL_SEC seconds have passed

daily alerts < ALERTS_PER_DAY_LIMIT

**Message includes:**

Time

pH

Water level

Status

Safe ranges

Runs a background generator thread

If GENERATOR_ENABLED=true, it:

runs generator_loop() in a background thread

periodically generates readings every GENERATOR_INTERVAL_SEC seconds

stores them + triggers alerts if needed

**Exposes web routes**

/ → index.html

/product → product.html

/about → about.html

/monitoring → monitoring dashboard (passes safe ranges + Firebase URL to frontend)

/simulate → manually trigger one reading (for testing)

/generator/start & /generator/stop → control background data generation via API

**Tech Stack**

Backend: Flask (Python)

Database: Firebase Realtime Database

Background Processing: Python threads for continuous sensor simulation

Alerts & Notifications: Twilio WhatsApp API with throttling and daily caps

Cloud Integration: Firebase Admin SDK for real-time data storage

Config & Secrets Management: .env with python-dotenv

Monitoring UI: HTML templates (index.html, product.html, monitoring.html) consuming Firebase data

                         ┌───────────────────────────┐
                         │        User / Admin       │
                         │  (opens website in browser) 
                         └─────────────┬─────────────┘
                                       │  HTTP
                                       ▼
                         ┌───────────────────────────┐
                         │        Flask App          │
                         │  (Python backend server)  │
                         ├─────────────┬─────────────┤
                         │ Routes:     │             │
                         │   /         │ index.html  │
                         │   /product  │ product.html│
                         │   /about    │ about.html  │
                         │   /monitoring (dashboard) │
                         │   /simulate (manual test) │
                         │   /generator/start|stop   │
                         └─────────────┬─────────────┘
                                       │
                        App config, .env│ (keys, safe ranges)
                                       ▼
                       ┌────────────────────────────┐
                       │  Sensor Generator Thread   │
                       │  (background Python loop)  │
                       ├────────────────────────────┤
                       │ - Generates random pH      │
                       │   and water_level values   │
                       │ - Computes status:         │
                       │     OK / WARNING / CRITICAL│
                       │ - Stores reading in        │
                       │   Firebase Realtime DB     │
                       │ - Calls alert logic        │
                       └─────────────┬──────────────┘
                                     │
                     write readings  │  REST / SDK
                                     ▼
                    ┌────────────────────────────────┐
                    │   Firebase Realtime Database    │
                    │   node: /sensor_readings        │
                    │  { timestamp, pH, water_level,  │
                    │    status, epoch_time }         │
                    └────────────────┬────────────────┘
                                     │
                    read data (JS)   │
                                     ▼
                    ┌────────────────────────────────┐
                    │   Monitoring Dashboard (HTML/JS)│
                    │   - Uses Firebase REST API      │
                    │   - Shows latest reading, status│
                    │   - Can visualize trends        │
                    └────────────────┬────────────────┘
                                     │
                                     │ triggers alerts
                                     ▼
                     ┌────────────────────────────────┐
                     │    Alert Logic (Flask backend) │
                     │  - Checks transitions:         │
                     │      OK→WARNING/CRITICAL       │
                     │      WARNING→CRITICAL          │
                     │  - Enforces:                   │
                     │      min time between alerts   │
                     │      max alerts per day        │
                     └────────────────┬───────────────┘
                                      │
                                      │ WhatsApp API call
                                      ▼
                         ┌──────────────────────────────┐
                         │        Twilio API            │
                         │      (WhatsApp Sender)       │
                         └──────────────────────────────┘


