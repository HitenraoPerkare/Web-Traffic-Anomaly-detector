# Intelligent Real-Time Web Traffic Monitoring & Anomaly Detection System
## Final Technology Stack & Architecture (2-Week MVP, 4-Person Team)

This document proposes the simplest technically correct stack and architecture for the project exactly as scoped: one interactive web app (user side + admin side), two independent ML pipelines (supervised HTTP classifier + Isolation Forest behavioral anomaly detector), a controlled synthetic traffic generator, a risk engine, and a dashboard — buildable in ~2 weeks by 4 students with limited Linux/networking/DB experience, using AI-assisted coding (Antigravity).

**Guiding principle:** one language (Python) end-to-end, one running process for the web app, one lightweight database, no build tooling, no containers, no message queues. Every choice below is picked to minimize moving parts, not because it's trendy.

---

## PART 1 — HIGH-LEVEL ARCHITECTURE

```
                 ┌─────────────────────────────────────────┐
                 │             SINGLE FLASK APP              │
                 │  (one process, one port, localhost/LAN)    │
                 │                                             │
  Real user ───▶ │  USER ROUTES         ADMIN ROUTES           │
  Traffic  ───▶  │  /  /products        /admin/login           │
  generator      │  /search /login      /admin/dashboard       │
                 │  /contact /forms     /api/... (JSON)         │
                 │        │                    ▲                │
                 │        ▼                    │                │
                 │  REQUEST LOGGING MIDDLEWARE  │                │
                 │  (before/after_request hook) │                │
                 │        │                    │                │
                 │        ▼                    │                │
                 │  IN-MEMORY REQUEST BUFFER    │                │
                 │        │                    │                │
                 │        ├──▶ RF inference ────┤ per-request    │
                 │        │                    │ classification │
                 │        │                    │                │
                 │  BACKGROUND AGGREGATOR       │                │
                 │  THREAD (every 10s)          │                │
                 │        │                    │                │
                 │        ▼                    │                │
                 │  Isolation Forest inference ─┤ per-window     │
                 │        │                    │ anomaly result  │
                 │        ▼                    │                │
                 │      RISK ENGINE ────────────┤                │
                 │        │                    │                │
                 │        ▼                    │                │
                 │      ALERT ENGINE            │                │
                 │        │                    │                │
                 │        ▼                    │                │
                 │      SQLite DATABASE ────────┘                │
                 └─────────────────────────────────────────┘
                              ▲
                              │ python-requests, threading
                 ┌─────────────────────────┐
                 │  traffic_generator.py     │
                 │  (separate script,        │
                 │   NORMAL/REPETITIVE/      │
                 │   BURST/ERROR/HIGH-FREQ)  │
                 └─────────────────────────┘

  OFFLINE (run once, not part of the live app):
  CSIC 2010 CSV ──▶ feature_extraction.py ──▶ train_classifier.py ──▶ models/*.pkl
  Normal traffic logs ──▶ window_features.py ──▶ train_isoforest.py ──▶ models/*.pkl
```

**Why one Flask process instead of separate frontend/backend services:** no CORS configuration, no second dev server, no build step, one command to run, one thing to deploy on a college laptop/LAN. This directly serves the team's networking/deployment skill level (2/5 and 0/5).

**Important run flag:** start the app with `app.run(host="0.0.0.0", threaded=True)`. The background aggregator thread and per-request inference both need CPU time inside the same process; without `threaded=True` the dev server serializes requests and the "concurrent clients" traffic-generator scenario won't behave as intended.

---

## PART 2 — COMPLETE TECHNOLOGY STACK

| # | Area | Choice | Why it fits | What it avoids | MVP or optional |
|---|------|--------|-------------|-----------------|------------------|
| 1 | Frontend templating | **Jinja2** (built into Flask) + server-rendered HTML | No JS framework, no build step; member 2/3's HTML/CSS/JS skill applies directly; AI tools generate Jinja2 templates easily | React/Vue build tooling, npm config, SPA routing complexity | MVP |
| 2 | User website | **Flask routes + Jinja2 templates + Bootstrap 5 (CDN)** | Bootstrap gives a presentable UI with zero custom CSS work, freeing time for ML/backend | Custom CSS framework work, design time sink | MVP |
| 3 | Admin dashboard | **Same Flask app**, separate `/admin` blueprint, Jinja2 + Bootstrap + Chart.js (CDN) | Keeps one codebase; dashboard is just more templates + JS fetch calls | A second app/server, auth duplication, CORS | MVP |
| 4 | Backend/API | **Flask 3.x** (not FastAPI), run with `threaded=True` | Simplest mental model for beginners; huge docs/tutorials for AI tools to draw on; synchronous code is easier to debug for a 0/5 Linux team; built-in Jinja2 and sessions | Async complexity, separate ASGI server setup, extra dependency surface | MVP |
| 5 | Database | **SQLite** via **SQLAlchemy ORM** (Flask-SQLAlchemy) | Zero server setup (single file), ORM means the team writes Python objects instead of raw SQL (matches DB skill 1/5); AI tools generate SQLAlchemy models reliably | PostgreSQL install/config, connection pooling, DB server admin | MVP |
| 6 | HTTP request logging | **Flask `before_request`/`after_request` hooks** writing to an in-memory `collections.deque` buffer, periodically flushed to `REQUEST_LOGS` table | Captures method, path, status, size, timing, headers with ~10 lines of code, no external log parser needed | Nginx access-log parsing, log-shipping agents (Filebeat, Fluentd) | MVP |
| 7 | Traffic aggregation | **Background Python thread** — a plain `while True: time.sleep(10)` loop (a daemon thread) that flushes the 10-second window, computes behavioral features, writes one row to `TRAFFIC_WINDOWS` | No separate scheduler service or extra dependency; runs inside the same process | Celery, cron jobs, external job queues, APScheduler (unnecessary — a plain loop does the same job) | MVP |
| 8 | Traffic generator | **Standalone Python script** (`traffic_generator.py`) using `requests` + `concurrent.futures.ThreadPoolExecutor` for simulated concurrent clients, CLI flags for mode/client-count/rate/duration | Pure Python, matches Member 1's strongest skill; no external bot tooling; five modes are just five functions | Locust/JMeter/k6 (overkill, extra learning curve), real botnets | MVP |
| 9 | ML training | **pandas + scikit-learn** (Random Forest only for MVP), run as plain `.py` scripts or Jupyter notebooks | Standard, well-documented, AI-assistable; scikit-learn `Pipeline`/`ColumnTransformer` handles preprocessing cleanly; one classifier is enough to satisfy the brief's requirement | Deep learning frameworks (TensorFlow/PyTorch) — unnecessary for tabular data; XGBoost comparison — doubles the ML pipeline for a requirement that only asks for one classifier (**optional stretch goal only**, if Week 2 has slack) | MVP |
| 10 | ML inference | Same **scikit-learn objects**, loaded once at Flask app startup (`joblib.load`) and reused for every request/window | Avoids reloading/retraining per request; a global `models = {}` dict shared across the app | Model-serving frameworks (TorchServe, Triton, MLflow serving) — unnecessary for this scale | MVP |
| 11 | Model persistence | **joblib** `.pkl` files in `/models/` (classifier, isolation forest, and the fitted preprocessing pipeline for each) | One line to save, one line to load; keeps training and inference schema identical, satisfying the project's own consistency requirement | ONNX export, model registries | MVP |
| 12 | Data preprocessing | **scikit-learn `Pipeline` + `ColumnTransformer`**, encapsulating a shared `feature_extraction.py` module imported by both the training scripts and the live Flask app | Guarantees the *same* feature-extraction code path is used for CSIC training and live inference (this is explicitly required in the brief) | Reimplementing feature logic twice (major bug risk / leakage risk) | MVP |
| 13 | Visualization | **Chart.js** via CDN, fed by JSON from `/api/metrics/*` endpoints, polled every 3–5s with `fetch()` | No build step, huge number of AI-generatable examples, sufficient for time-series/line/bar charts needed here | D3.js (steeper learning curve), Plotly Dash (a second framework) | MVP |
| 14 | Real-time updates | **Polling** (`setInterval` + `fetch`) every few seconds, not WebSockets | One HTTP endpoint, no persistent connection management, trivial to debug and demo | Flask-SocketIO / WebSockets — adds a moving part with no benefit at this traffic scale | MVP |
| 15 | Authentication | **Flask's built-in `session`** + a small custom `@admin_required` decorator, single seeded admin user, password hashed via `werkzeug.security` | ~15 lines of code for `/admin/login`, session-based, no new dependency to learn | OAuth providers, JWT, external identity services, and even Flask-Login itself — a single hardcoded admin account doesn't need a dedicated auth extension | MVP |
| 16 | Development environment | **Python 3.11+ venv**, VS Code, `requirements.txt`, Antigravity for AI-assisted coding | Standard, lightweight, matches team skill; no OS-level tooling beyond Python | Docker Desktop for local dev (adds a layer none of the team needs yet) | MVP |
| 17 | Local deployment | `python app.py` / `flask run --host=0.0.0.0` on a laptop connected to the college LAN so classmates/faculty can hit it from other devices | Zero deployment infrastructure; matches "controlled local/college-network environment" requirement | Reverse proxy, TLS certs, systemd services, a third-party hosting tier — not needed to satisfy the brief | MVP |
| 18 | Version control | **Git + GitHub**, one repo, feature branches per team member, PR review before merging to `main` | Standard for 4-person collaboration; GitHub Issues can double as a lightweight task tracker | Monorepo tooling, Git submodules | MVP |
| 19 | Testing | **pytest** for `feature_extraction.py` (pure functions, easy to unit-test with known inputs/outputs) + manual exploratory testing of the web app and dashboard | Testing the feature extraction is the highest-value/lowest-effort test given it's shared between training and inference | Full CI/CD pipelines, load testing frameworks, Selenium UI test suites | Optional (unit tests for feature extraction recommended; everything else can be manual) |
| 20 | Package management | **pip + requirements.txt** inside a venv | Simplest possible dependency workflow; every tutorial/AI example uses this | Poetry/Conda — an extra tool to learn for no real benefit at this scale | MVP |

### Nginx (explicitly addressed)
Not used in the MVP. Flask's built-in dev server, run with `threaded=True`, is enough for a LAN demo. Nginx adds zero functional value to the ML pipeline and is explicitly optional per the brief — skip it entirely rather than adding it "to look production."

### Networking scope (explicitly addressed)
No Scapy, no raw sockets, no packet capture anywhere in this stack. Every "network" concept the team needs (IP, port, TCP, HTTP, packet, flow) shows up only conceptually in the write-up/demo narrative — the implementation stays entirely at the HTTP/application layer via Flask's request object.

---

## PART 3 — REPOSITORY / FOLDER STRUCTURE

```
traffic-monitor/
├── app/
│   ├── __init__.py              # Flask app factory, extension init
│   ├── config.py                # config (SQLite path, window size=10s, model paths)
│   ├── models_db.py             # SQLAlchemy models: RequestLog, TrafficWindow, Alert, AdminUser
│   ├── routes_user.py           # Blueprint: /, /products, /search, /login, /contact
│   ├── routes_admin.py          # Blueprint: /admin/login, /admin/dashboard
│   ├── routes_api.py            # Blueprint: /api/metrics/*, /api/anomalies, /api/alerts
│   ├── auth.py                  # session-based admin login helpers + @admin_required decorator
│   ├── middleware.py            # before_request/after_request logging hooks
│   ├── aggregator.py            # background thread: 10s window builder
│   ├── risk_engine.py           # combines classifier + anomaly → LOW/MEDIUM/HIGH/CRITICAL
│   ├── alert_engine.py          # alert generation + cooldown logic
│   ├── ml/
│   │   ├── feature_extraction.py   # SHARED: request-level features (used by training AND inference)
│   │   ├── window_features.py      # SHARED: window-level features (used by training AND inference)
│   │   ├── classifier_service.py   # loads RF model, exposes predict(request)
│   │   └── anomaly_service.py      # loads Isolation Forest model, exposes predict(window)
│   ├── templates/
│   │   ├── user/  (home.html, products.html, search.html, login.html, ...)
│   │   └── admin/ (login.html, dashboard.html)
│   └── static/ (css, js, chart configs)
├── ml_training/
│   ├── train_classifier.py      # CSIC 2010 → RF → models/classifier.pkl (includes evaluation: precision/recall/F1/confusion matrix)
│   ├── train_isoforest.py       # normal traffic logs → models/isoforest.pkl
│   └── data/csic2010.csv
├── models/
│   ├── classifier_pipeline.pkl
│   └── isoforest_pipeline.pkl
├── traffic_generator/
│   └── traffic_generator.py     # NORMAL / REPETITIVE / BURST / ERROR / HIGH-FREQ modes
├── instance/
│   └── app.db                   # SQLite file
├── requirements.txt
├── run.py                       # entry point
└── README.md
```

`feature_extraction.py` and `window_features.py` living in `app/ml/` and being imported by both `ml_training/*.py` and the live Flask services is the mechanism that guarantees training and inference always share the exact same feature schema — this directly satisfies the brief's "very important" compatibility requirement.

---

## PART 4 — DATABASE SCHEMA (SQLite / SQLAlchemy)

```python
class RequestLog(db.Model):
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, index=True)
    method = Column(String)
    path = Column(String)
    client_id = Column(String)         # e.g. IP or generator-assigned client id
    status_code = Column(Integer)
    response_time_ms = Column(Float)
    request_size = Column(Integer)
    classifier_result = Column(String) # BENIGN / ATTACK / NULL
    attack_probability = Column(Float, nullable=True)

class TrafficWindow(db.Model):
    id = Column(Integer, primary_key=True)
    window_start = Column(DateTime, index=True)
    requests_per_window = Column(Integer)
    requests_per_second = Column(Float)
    unique_client_count = Column(Integer)
    requests_per_client_avg = Column(Float)
    repeated_request_ratio = Column(Float)
    endpoint_diversity = Column(Float)
    avg_inter_request_time = Column(Float)
    traffic_bytes = Column(Integer)
    avg_request_size = Column(Float)
    avg_response_time = Column(Float)
    error_4xx_ratio = Column(Float)
    error_5xx_ratio = Column(Float)
    anomaly_score = Column(Float)
    anomaly_status = Column(String)    # NORMAL / ANOMALY

class Alert(db.Model):
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, index=True)
    severity = Column(String)          # LOW / MEDIUM / HIGH / CRITICAL
    alert_type = Column(String)
    message = Column(String)
    anomaly_score = Column(Float, nullable=True)
    classification = Column(String, nullable=True)
    window_id = Column(Integer, ForeignKey('traffic_window.id'), nullable=True)

class AdminUser(db.Model):
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
```

---

## PART 5 — API ENDPOINTS

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/metrics/live` | GET | Current req/s, req/min, client count, avg response time, error rates, current anomaly status, current risk level |
| `/api/metrics/history?minutes=60` | GET | Time-series of `TrafficWindow` rows for charts |
| `/api/anomalies` | GET | Recent anomaly windows + scores |
| `/api/alerts` | GET | Recent alerts (with cooldown-deduplicated list) |
| `/api/traffic` | GET | Endpoint/client distribution for the current window |
| `/api/ml/status` | GET | Which models are loaded, when they were trained, basic metadata |
| `/admin/login` | POST | Session-based admin login |

All dashboard JS hits these with periodic `fetch()` calls — no WebSocket layer needed.

---

## PART 6 — WHAT RUNS WHEN (explicit, per the brief's request)

| Component | Runs... |
|---|---|
| `train_classifier.py`, `train_isoforest.py` | **Once, offline**, whenever the team wants to retrain (not part of the live app) |
| Flask app (user + admin routes) | **Continuously**, as long as the server process is running |
| Request logging middleware | **Per HTTP request** |
| RF inference | **Per HTTP request** (or a sampled subset if you want to reduce load — optional) |
| Aggregator thread | **Every 10 seconds** (one tick = one window = one row) |
| Isolation Forest inference | **Per traffic window** (every 10 seconds) |
| Risk engine | **Per traffic window**, combining the latest classifier result(s) + the window's anomaly result |
| Alert engine | **Per traffic window**, only when a condition is met (with cooldown) |
| Dashboard polling | **Every 3–5 seconds** from the browser, reading already-computed results — no ML runs in the browser or on-demand from a dashboard click |
| SQLite writes | Per request (buffered/batched) and per window and per alert |
| Dashboard display | Reads from SQLite / in-memory latest-state cache, never triggers training |

---

## PART 7 — TWO-WEEK IMPLEMENTATION PLAN (mapped to the 4 roles, ~5-6 hrs/week each)

**Week 1**

- Day 1–2: Repo setup, Flask skeleton (app factory, blueprints), SQLite models, venv + requirements.txt. *(Member 3, with Member 1 support)*
- Day 2–4: User-facing pages (home, products, search, login, contact) with Bootstrap. *(Member 2 + Member 4 polishing)*
- Day 2–5: `feature_extraction.py` (request-level) and CSIC 2010 preprocessing script; `train_classifier.py` (Random Forest). *(Member 1)*
- Day 5–7: Request logging middleware + `RequestLog` persistence; begin `window_features.py` and the aggregator thread. *(Member 3)*

**Week 2**

- Day 8–9: `train_isoforest.py` using normal traffic (real + synthetic-normal) window features; save both pipelines with joblib. *(Member 1)*
- Day 8–10: `traffic_generator.py` — all five modes, CLI flags. *(Member 3 or 1)*
- Day 9–11: Admin dashboard templates + Chart.js wiring to `/api/metrics/*`; session-based admin auth. *(Member 2 + Member 4)*
- Day 10–12: Risk engine + alert engine + cooldown logic; wire classifier/anomaly results into `Alert` table. *(Member 3)*
- Day 12–13: End-to-end run-through of the demonstration scenario (Section 29 of the brief): normal → repetitive/burst → anomaly → alert → risk level shown on dashboard. Bug fixing.
- Day 13–14: Evaluation write-up (precision/recall/F1/confusion matrix for the classifier), README, buffer for polish and rehearsal. **If time remains only here**, an XGBoost comparison against the RF baseline is a reasonable stretch add — not before.

This order matches the brief's stated priority list (interactive website → logging → aggregation → Isolation Forest → dashboard → CSIC preprocessing → classifier → risk/alerts → polish), just parallelized across the two ML-capable and two web-capable people so nothing sits idle.

---

## PART 8 — WHAT THIS STACK DELIBERATELY DOES NOT DO

- No microservices, no message queues, no Kubernetes, no Docker requirement for MVP.
- No merging of the two ML tasks into one model or one feature space.
- No CSIC labels used for Isolation Forest training.
- No raw packet capture or Scapy.
- No external bot services — the generator only ever talks to your own Flask app.
- No algorithm comparison for the MVP classifier — one Random Forest model satisfies the requirement; XGBoost is a stretch goal only, never a Week 1–2 default.
- No auth extension (Flask-Login), scheduler library (APScheduler), or extra hosting tier — each of these problems is small enough to solve with a few lines of plain Python instead of a new dependency.
- No claim of universal attack detection — the dashboard should present results exactly as two separate signals (classification, anomaly) combined by a project-defined risk engine, not as a certified security product.

This is the smallest stack that implements every requirement in the brief correctly and can realistically be finished by four students in two weeks at 5–6 hours/week each.
