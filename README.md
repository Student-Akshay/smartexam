# SmartExam — AI-Based Anti-Cheating System

A full-stack web application for conducting online examinations with real-time AI-powered proctoring using **MediaPipe** and **OpenCV**.

---

## ✨ Features

| Category | Details |
|---|---|
| **Auth** | Student self-registration, bcrypt passwords, role-based login (student / admin) |
| **Exam** | MCQ with timer, Prev/Next navigation, auto-score calculation, resume support |
| **AI Monitoring** | Webcam → MediaPipe FaceMesh → gaze + head-pose detection every 700 ms |
| **Warning System** | Configurable threshold before an event fires; graduated warnings → mark deductions |
| **Violation Log** | Per-event DB record with type, warning number, penalty marks, timestamp |
| **Admin Dashboard** | Students list, exam results, full violation log with multi-column filters |

---

## 🗂 Project Structure

```
smartexam/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # All tunable thresholds & DB config
│   ├── extensions.py        # SQLAlchemy + Flask-Login init
│   ├── models/              # SQLAlchemy ORM models
│   ├── auth/                # Register / Login / Logout
│   ├── student/             # Dashboard, exam, submit, result
│   ├── admin/               # Admin dashboard, students, results, violations
│   ├── monitoring/          # AI detector + API endpoints
│   └── templates/           # Jinja2 HTML templates
├── static/
│   ├── css/style.css        # Design system
│   └── js/
│       ├── exam.js          # Timer, MCQ nav, submit
│       └── monitor.js       # Webcam → AI state machine
├── db/
│   └── schema.sql           # MySQL DDL + seed data
├── requirements.txt
└── run.py                   # Entry point
```

---

## ⚙️ Prerequisites

- Python 3.10+
- MySQL 8.0+
- A webcam (for AI monitoring during exams)

---

## 🚀 Installation & Setup

### 1. Clone / download the project

```bash
cd smartexam
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **Note:** MediaPipe and OpenCV may take a few minutes to install.

### 4. Set up the MySQL database

Log in to MySQL and run the schema:

```bash
mysql -u root -p < db/schema.sql
```

Or paste the contents of `db/schema.sql` into your MySQL client.

### 5. Configure the database connection

Edit `app/config.py` and update these values to match your MySQL setup:

```python
DB_USER     = "root"          # your MySQL username
DB_PASSWORD = ""              # your MySQL password
DB_NAME     = "smartexam"
DB_HOST     = "localhost"
DB_PORT     = 3306
```

You can also set these via environment variables:

```bash
export DB_USER=root
export DB_PASSWORD=yourpassword
```

### 6. Run the application

```bash
python run.py
```

Open your browser at **http://localhost:5000**

---

## 🔑 Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@smartexam.com | Admin@123 |
| Student | alice@example.com | Student@123 |

---

## 🧠 AI Monitoring — How It Works

```
Browser (monitor.js)
  ├─ getUserMedia() → video stream
  ├─ Every 700 ms: canvas.toDataURL() → base64 JPEG
  ├─ POST /api/monitor/frame   ← sends frame
  │     └─ detector.py:
  │           MediaPipe FaceMesh → iris landmarks → gaze ratio
  │                              → head yaw/pitch → pose
  │     └─ Returns: { violation, gaze, head_pose, face_count }
  │
  └─ State machine:
       if violation: start timer
       if sustained > threshold: POST /api/monitor/event
            └─ server: writes ViolationLog, applies penalty
            └─ client: shows warning overlay, updates counters
```

**Detected violations:**

| Code | Trigger |
|---|---|
| `FACE_MISSING` | No face detected for N seconds |
| `MULTIPLE_FACES` | >1 face in frame |
| `GAZE_LEFT` | Iris ratio < 0.35 (looking left) |
| `GAZE_RIGHT` | Iris ratio > 0.65 (looking right) |
| `HEAD_TURNED` | Head yaw > 20° |

---

## ⚙️ Configuration

All thresholds are in `app/config.py` and can be changed without touching business logic:

```python
LOOK_AWAY_THRESHOLD_SEC    = 3    # seconds before a sustained look-away fires
MAX_WARNINGS_BEFORE_PENALTY = 3   # Nth warning triggers mark deduction
PENALTY_MARKS_PER_VIOLATION = 1   # marks deducted per penalty event
MAX_PENALTY_MARKS           = 5   # hard cap on total deductions

GAZE_RATIO_LEFT_THRESHOLD  = 0.35  # iris ratio thresholds
GAZE_RATIO_RIGHT_THRESHOLD = 0.65
HEAD_YAW_THRESHOLD         = 20.0  # degrees
```

Per-exam overrides can be set in the `exam_config` database table.

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'mediapipe'` | Run `pip install mediapipe==0.10.14` |
| `Access denied for user 'root'@'localhost'` | Check `DB_PASSWORD` in `config.py` |
| Camera not working | Allow camera permissions in your browser; use HTTPS or localhost |
| `Table 'smartexam.users' doesn't exist` | Re-run `db/schema.sql` |
| Warning overlay fires too quickly | Increase `LOOK_AWAY_THRESHOLD_SEC` in `config.py` |

---

## 📄 License

MIT License — free to use and modify.
