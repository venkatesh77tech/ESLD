"""
app.py
------
ESLD Backend — single Flask app, single DB connection style (flask_mysqldb),
all routes in one place. This replaces the old app.py, which had TWO entire
Flask apps pasted into one file (the second one silently overwrote the first
`app` object, and two routes were even defined twice on the same app, which
would have crashed Flask at import time with "View function mapping is
overwriting an existing endpoint function"). Every route below is defined
exactly once.

Run with: python app.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_mysqldb import MySQL
import bcrypt
import uuid
import datetime
import os
import json
import requests

app = Flask(__name__)
CORS(app)  # handles OPTIONS preflight for every route automatically

# ─── MYSQL CONFIG ───
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 3306))

mysql = MySQL(app)

VALID_MODULES = {'dyslexia', 'dysgraphia', 'adhd'}


def normalize_module(value):
    """Keep bad/missing module values from breaking the ENUM column."""
    v = (value or '').strip().lower()
    return v if v in VALID_MODULES else 'dyslexia'


# ════════════════════════════════════════
#  HOME
# ════════════════════════════════════════
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# ════════════════════════════════════════
#  STUDENT AUTH
# ════════════════════════════════════════

@app.route('/register', methods=['POST'])
def register():
    data       = request.get_json()
    name       = data.get('name', '').strip()
    email      = data.get('email', '').strip().lower()
    password   = data.get('password', '')
    disability = data.get('disability', 'dyslexia')
    school     = data.get('school', '')      # free text from the school dropdown
    standard   = data.get('standard', '')    # e.g. "3"
    section    = data.get('section', '')     # e.g. "A"
    school_id  = data.get('school_id', 1)
    class_id   = data.get('class_id', 1)

    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM students WHERE email=%s", [email])
    if cur.fetchone():
        return jsonify({"error": "Email already registered"}), 400

    cur.execute("SELECT COUNT(*) FROM students")
    total      = cur.fetchone()[0] + 1
    student_id = f"ESLD2026ST{total:03}"

    cur.execute(
        """INSERT INTO students(student_id, school_id, class_id, school, standard, section,
                                 name, email, password, disability, total_coins)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (student_id, school_id, class_id, school, standard, section, name, email, hashed, disability, 0)
    )
    mysql.connection.commit()
    return jsonify({"message": "Registered successfully", "student_id": student_id})


@app.route('/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT student_id, name, password, disability, total_coins FROM students WHERE email=%s",
        [email]
    )
    user = cur.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        return jsonify({
            "student_id":  user[0],
            "name":        user[1],
            "disability":  user[3],
            "total_coins": user[4] or 0
        })

    return jsonify({"error": "Invalid email or password"}), 401


# ════════════════════════════════════════
#  FORGOT / RESET PASSWORD
# ════════════════════════════════════════

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()

    cur = mysql.connection.cursor()
    cur.execute("SELECT student_id FROM students WHERE email=%s", [email])
    user = cur.fetchone()

    # Always return success to prevent email enumeration
    if not user:
        return jsonify({"message": "If that email is registered, a reset token has been sent."})

    token   = str(uuid.uuid4()).replace('-', '')[:32]
    expires = datetime.datetime.now() + datetime.timedelta(hours=1)

    cur.execute("DELETE FROM password_resets WHERE email=%s", [email])
    cur.execute(
        "INSERT INTO password_resets(email, token, expires_at) VALUES(%s,%s,%s)",
        (email, token, expires)
    )
    mysql.connection.commit()

    # ⚠️ In production: email the token link instead of returning it
    return jsonify({
        "message": "Reset token generated successfully.",
        "token": token,   # REMOVE in production — send via email instead
        "dev_note": "Copy this token and paste it on the reset password page."
    })


@app.route('/reset-password', methods=['POST'])
def reset_password():
    data         = request.get_json()
    token        = data.get('token', '').strip()
    new_password = data.get('password', '')

    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT email, expires_at FROM password_resets WHERE token=%s", [token])
    row = cur.fetchone()

    if not row:
        return jsonify({"error": "Invalid reset token"}), 400

    email, expires = row
    if datetime.datetime.now() > expires:
        cur.execute("DELETE FROM password_resets WHERE token=%s", [token])
        mysql.connection.commit()
        return jsonify({"error": "Token has expired. Please request a new one."}), 400

    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute("UPDATE students SET password=%s WHERE email=%s", (hashed, email))
    cur.execute("DELETE FROM password_resets WHERE token=%s", [token])
    mysql.connection.commit()

    return jsonify({"message": "Password reset successfully. You can now login."})


# ════════════════════════════════════════
#  GAME PROGRESS  (this is what feeds every report)
# ════════════════════════════════════════

@app.route('/save-progress', methods=['POST'])
def save_progress():
    data         = request.get_json()
    student_id   = data.get('student_id')
    game         = data.get('game')                       # display name, e.g. 'Letter Tracing'
    module       = normalize_module(data.get('module'))    # 'dyslexia' | 'dysgraphia' | 'adhd'
    mode         = data.get('mode')
    level        = data.get('level')
    accuracy     = data.get('accuracy', 0)
    coins        = data.get('coins', 0)
    session_time = data.get('session_time', 0)
    questions    = data.get('questions', 0)
    correct      = data.get('correct', 0)
    wrong        = data.get('wrong', 0)

    if not student_id or not game:
        return jsonify({"error": "student_id and game are required"}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        """INSERT INTO game_progress
           (student_id, game, module, mode, level, accuracy, coins, session_time, questions, correct, wrong, date_played)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURDATE())""",
        (student_id, game, module, mode, level, accuracy, coins, session_time, questions, correct, wrong)
    )

    if coins > 0:
        cur.execute(
            "UPDATE students SET total_coins = total_coins + %s WHERE student_id=%s",
            (coins, student_id)
        )

    mysql.connection.commit()
    return jsonify({"message": "Progress saved", "coins_added": coins})


@app.route('/get-progress/<student_id>', methods=['GET'])
def get_progress(student_id):
    cur = mysql.connection.cursor()

    cur.execute(
        """SELECT game, module, mode, level, accuracy, coins, session_time, questions, correct, wrong, date_played
           FROM game_progress WHERE student_id=%s ORDER BY date_played DESC, id DESC LIMIT 100""",
        [student_id]
    )
    rows = cur.fetchall()

    progress = [{
        "game":         r[0],
        "module":       r[1],
        "mode":         r[2],
        "level":        r[3],
        "accuracy":     r[4],
        "coins":        r[5],
        "session_time": r[6],
        "questions":    r[7],
        "correct":      r[8],
        "wrong":        r[9],
        "date":         str(r[10])
    } for r in rows]

    # Per-module rollup (used to draw the Dyslexia/Dysgraphia/ADHD bars correctly)
    cur.execute(
        """SELECT module, COUNT(*), COALESCE(AVG(accuracy),0)
           FROM game_progress WHERE student_id=%s GROUP BY module""",
        [student_id]
    )
    module_rows = cur.fetchall()
    modules = {m: {"sessions": 0, "avg_accuracy": 0} for m in VALID_MODULES}
    for m, sessions, avg_acc in module_rows:
        if m in modules:
            modules[m] = {"sessions": sessions, "avg_accuracy": round(float(avg_acc), 1)}

    cur.execute(
        "SELECT name, disability, total_coins FROM students WHERE student_id=%s",
        [student_id]
    )
    s = cur.fetchone()

    return jsonify({
        "student_id":  student_id,
        "name":        s[0] if s else "",
        "disability":  s[1] if s else "",
        "total_coins": s[2] if s else 0,
        "progress":    progress,
        "modules":     modules
    })


@app.route('/all-students-progress', methods=['GET'])
def all_students_progress():
    """For teacher dashboard — every student with aggregated stats.
    Optional query params ?school=&standard=&section= restrict the result to a
    matching class. Any blank/omitted param means 'don't filter on this field'."""
    school   = request.args.get('school', '').strip()
    standard = request.args.get('standard', '').strip()
    section  = request.args.get('section', '').strip()

    where_clauses = []
    params = []
    if school:
        where_clauses.append("s.school = %s")
        params.append(school)
    if standard:
        where_clauses.append("s.standard = %s")
        params.append(standard)
    if section:
        where_clauses.append("s.section = %s")
        params.append(section)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    cur = mysql.connection.cursor()
    cur.execute(f"""
        SELECT
            s.student_id, s.name, s.disability, s.total_coins,
            COUNT(g.id)                  AS sessions,
            COALESCE(AVG(g.accuracy), 0) AS avg_accuracy,
            MAX(g.date_played)           AS last_active,
            COALESCE(SUM(g.correct), 0)  AS total_correct,
            COALESCE(SUM(g.wrong), 0)    AS total_wrong
        FROM students s
        LEFT JOIN game_progress g ON s.student_id = g.student_id
        {where_sql}
        GROUP BY s.student_id, s.name, s.disability, s.total_coins
        ORDER BY avg_accuracy DESC
    """, params)
    rows = cur.fetchall()

    students = []
    for r in rows:
        acc = round(float(r[5]), 1)
        status = "high" if acc >= 75 else ("medium" if acc >= 50 else "low")
        students.append({
            "student_id":    r[0],
            "name":          r[1],
            "disability":    r[2],
            "total_coins":   r[3] or 0,
            "sessions":      r[4],
            "avg_accuracy":  acc,
            "last_active":   str(r[6]) if r[6] else "Never",
            "total_correct": r[7],
            "total_wrong":   r[8],
            "status":        status
        })

    return jsonify({"students": students, "filtered_by": {"school": school, "standard": standard, "section": section}})


@app.route('/student-game-summary/<student_id>', methods=['GET'])
def student_game_summary(student_id):
    """Detailed per-game + per-module stats for the parent/teacher detail modal"""
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT game, module, COUNT(*) sessions, ROUND(AVG(accuracy),1) avg_acc, SUM(coins) total_coins
        FROM game_progress WHERE student_id=%s GROUP BY game, module
    """, [student_id])
    game_stats = [{
        "game":         r[0],
        "module":       r[1],
        "sessions":     r[2],
        "avg_accuracy": float(r[3]) if r[3] else 0,
        "total_coins":  r[4] or 0
    } for r in cur.fetchall()]

    cur.execute("""
        SELECT module, COUNT(*), COALESCE(AVG(accuracy),0)
        FROM game_progress WHERE student_id=%s GROUP BY module
    """, [student_id])
    module_stats = [{
        "module": r[0], "sessions": r[1], "avg_accuracy": round(float(r[2]), 1)
    } for r in cur.fetchall()]

    cur.execute("""
        SELECT date_played, ROUND(AVG(accuracy),1)
        FROM game_progress WHERE student_id=%s
          AND date_played >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY date_played ORDER BY date_played
    """, [student_id])
    weekly = [{"date": str(r[0]), "accuracy": float(r[1]) if r[1] else 0}
              for r in cur.fetchall()]

    cur.execute("""
        SELECT date_played, ROUND(AVG(accuracy),1)
        FROM game_progress WHERE student_id=%s
          AND date_played >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY date_played ORDER BY date_played
    """, [student_id])
    monthly = [{"date": str(r[0]), "accuracy": float(r[1]) if r[1] else 0}
               for r in cur.fetchall()]

    cur.execute(
        "SELECT name, disability, total_coins FROM students WHERE student_id=%s",
        [student_id]
    )
    s = cur.fetchone()

    return jsonify({
        "student_id":       student_id,
        "name":             s[0] if s else "",
        "disability":       s[1] if s else "",
        "total_coins":      s[2] if s else 0,
        "game_stats":       game_stats,
        "module_stats":     module_stats,
        "weekly_accuracy":  weekly,
        "monthly_accuracy": monthly
    })


# ════════════════════════════════════════
#  PARENT AUTH
# ════════════════════════════════════════

@app.route('/parent-register', methods=['POST'])
def parent_register():
    data       = request.get_json()
    name       = data.get('name', '').strip()
    email      = data.get('email', '').strip().lower()
    password   = data.get('password', '')
    student_id = data.get('student_id', '').strip().upper()

    if not all([name, email, password, student_id]):
        return jsonify({"error": "All fields are required"}), 400

    cur = mysql.connection.cursor()

    cur.execute("SELECT student_id FROM students WHERE student_id=%s", [student_id])
    if not cur.fetchone():
        return jsonify({"error": "Student ID not found. Check with your school."}), 404

    cur.execute("SELECT id FROM parents WHERE email=%s", [email])
    if cur.fetchone():
        return jsonify({"error": "Email already registered"}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute("SELECT COUNT(*) FROM parents")
    total     = cur.fetchone()[0] + 1
    parent_id = f"PAR2026{total:03}"

    cur.execute(
        "INSERT INTO parents(parent_id, name, email, password, student_id) VALUES(%s,%s,%s,%s,%s)",
        (parent_id, name, email, hashed, student_id)
    )
    mysql.connection.commit()
    return jsonify({"message": "Parent account created", "parent_id": parent_id})


@app.route('/parent-login', methods=['POST'])
def parent_login():
    data     = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT parent_id, name, password, student_id FROM parents WHERE email=%s",
        [email]
    )
    user = cur.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        return jsonify({
            "parent_id":  user[0],
            "name":       user[1],
            "student_id": user[3]
        })

    return jsonify({"error": "Invalid email or password"}), 401


# ════════════════════════════════════════
#  TEACHER AUTH
#  (matches the `teachers` table in schema.sql — teacher_id is auto-generated
#   the same way student_id is, so no extra roster/users tables are needed)
# ════════════════════════════════════════

@app.route('/teacher-register', methods=['POST'])
def teacher_register():
    data      = request.get_json()
    name      = data.get('name', '').strip()
    email     = data.get('email', '').strip().lower()
    password  = data.get('password', '')
    school    = data.get('school', '')       # free-text school name from the dropdown
    standard  = data.get('standard', '')     # class/grade this teacher teaches; '' = whole school
    section   = data.get('section', '')      # '' = all sections
    role      = data.get('role', 'teacher')
    school_id = data.get('school_id', 1)
    class_id  = data.get('class_id', 1)
    subject   = data.get('subject', 'General')

    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM teachers WHERE email=%s", [email])
    if cur.fetchone():
        return jsonify({"error": "An account with this email already exists. Try signing in."}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute("SELECT COUNT(*) FROM teachers")
    total      = cur.fetchone()[0] + 1
    teacher_id = f"ESLD2026TC{total:03}"

    cur.execute(
        """INSERT INTO teachers(teacher_id, school_id, class_id, school, standard, section, role,
                                 name, email, password, subject)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (teacher_id, school_id, class_id, school, standard, section, role, name, email, hashed, subject)
    )
    mysql.connection.commit()
    # teacher-login.html's completeLogin() expects id/school/role on the response
    return jsonify({"message": "Account created", "teacher_id": teacher_id,
                     "id": teacher_id, "school": school, "standard": standard,
                     "section": section, "role": role})


@app.route('/teacher-login', methods=['POST'])
def teacher_login():
    data     = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT teacher_id, name, password, school, standard, section, role FROM teachers WHERE email=%s",
        [email]
    )
    user = cur.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        # teacher-login.html's completeLogin() reads data.id / data.school / data.standard /
        # data.section / data.role and stores them in sessionStorage so the dashboard can
        # filter to just this teacher's class without asking them to re-pick it every login.
        return jsonify({"id": user[0], "teacher_id": user[0], "name": user[1],
                         "school": user[3] or '', "standard": user[4] or '',
                         "section": user[5] or '', "role": user[6] or 'teacher'})

    return jsonify({"error": "Invalid email or password"}), 401


# ════════════════════════════════════════
#  AI LETTER RECOGNITION (Air Writing game)
#  ─────────────────────────────────────────
#  dysgraphia-air-writing.html used to call api.anthropic.com DIRECTLY from
#  the browser with no API key — that request will always fail with 401
#  (browsers can't send a secret key safely anyway), so the game was quietly
#  running its random-simulation fallback 100% of the time, never real
#  recognition. This route holds the key server-side instead.
#
#  Set your key once before running:
#     export ANTHROPIC_API_KEY=sk-ant-...      (macOS/Linux)
#     setx ANTHROPIC_API_KEY "sk-ant-..."       (Windows)
# ════════════════════════════════════════

@app.route('/recognize-letter', methods=['POST'])
def recognize_letter():
    data           = request.get_json()
    target_letter  = data.get('targetLetter', '')
    points         = data.get('points', [])
    difficulty     = data.get('difficulty', 'medium')
    time_taken     = data.get('timeTaken')

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 503

    prompt = f"""You are an AI letter recognition system for a children's handwriting game.
A child tried to write the letter "{target_letter}" using air writing or a touch canvas.
The letter was written as {len(points)} points across a canvas.
Stroke data (normalized 0-100): {json.dumps(points[:60])}
Canvas dimensions hint: width=100, height=100. Top-left is (0,0).
Target letter: "{target_letter}"
Difficulty: {difficulty}
Time taken: {(str(time_taken) + 's') if time_taken else 'unknown'}

Analyze the stroke pattern and respond ONLY with valid JSON (no markdown, no backticks):
{{
  "recognized": "LETTER",
  "confidence": 85,
  "isCorrect": true,
  "topGuesses": [
    {{"letter": "{target_letter}", "confidence": 85}},
    {{"letter": "X", "confidence": 10}},
    {{"letter": "Y", "confidence": 5}}
  ],
  "feedback": "Short encouraging feedback for a child in 1 sentence.",
  "strokeQuality": "good",
  "tipForImprovement": "One specific tip about stroke shape in 1 sentence."
}}
"recognized" must be one uppercase English letter A-Z.
"confidence" is 0-100.
"isCorrect" is true if recognized matches target.
"strokeQuality" is "excellent", "good", "fair", or "needs work".
Be generous with children — if the stroke is somewhat similar to "{target_letter}", say it's correct with moderate confidence. Hard difficulty requires stricter matching."""

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json={"model": "claude-sonnet-4-6", "max_tokens": 400,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=10
        )
        resp.raise_for_status()
        text = ''.join(b.get('text', '') for b in resp.json().get('content', []))
        text = text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Recognition failed: {e}"}), 502


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)