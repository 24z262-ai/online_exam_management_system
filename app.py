import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from db import close_db, cursor, get_db


def calculate_score(questions, answers, marks_per_question):
    return sum(
        marks_per_question
        for question in questions
        if answers.get(str(question["question_id"])) == question["correct_answer"]
    )


def parse_schedule_datetime(value, timezone_name):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def local_schedule_value(value, timezone_name):
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%dT%H:%M")


def schedule_state(exam, now=None):
    if not exam.get("is_published"):
        return "Draft"
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    starts_at, ends_at = exam.get("starts_at"), exam.get("ends_at")
    if starts_at and now < starts_at:
        return "Scheduled"
    if ends_at and now >= ends_at:
        return "Ended"
    return "Available"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    csrf = CSRFProtect()
    csrf.init_app(app)
    app.teardown_appcontext(close_db)

    def login_required(role=None):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not session.get("user_id"):
                    return redirect(url_for("login"))
                if role and session.get("role") != role:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.get("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("home"))
        return render_template("landing.html")

    @app.get("/help")
    def help_page():
        return render_template("help.html")

    @app.get("/features")
    def features_page():
        return render_template("features.html")

    @app.get("/how-it-works")
    def how_it_works_page():
        return render_template("how_it_works.html")

    @app.get("/home")
    @login_required()
    def home():
        if session["role"] == "admin":
            with cursor(dictionary=True) as cur:
                cur.execute("SELECT COUNT(*) total FROM users WHERE role='student'")
                student_count = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) total FROM exams")
                exam_count = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) total FROM exams e WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.exam_id=e.exam_id)")
                draft_count = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) total FROM results")
                attempt_count = cur.fetchone()["total"]
                cur.execute("SELECT exam_id,exam_name,created_at FROM exams ORDER BY created_at DESC LIMIT 4")
                latest_exams = cur.fetchall()
                cur.execute("SELECT r.result_id,r.score,r.total_marks,r.submitted_at,u.name student_name,e.exam_name FROM results r JOIN users u ON u.user_id=r.student_id JOIN exams e ON e.exam_id=r.exam_id ORDER BY r.submitted_at DESC LIMIT 4")
                latest_results = cur.fetchall()
            return render_template("home.html", role="admin", student_count=student_count,
                                   exam_count=exam_count, draft_count=draft_count,
                                   attempt_count=attempt_count, latest_exams=latest_exams,
                                   latest_results=latest_results)

        with cursor(dictionary=True) as cur:
            cur.execute("SELECT e.exam_id,e.exam_name,e.description,e.duration_minutes,e.is_published,e.starts_at,e.ends_at,COUNT(q.question_id) question_count FROM exams e LEFT JOIN questions q ON q.exam_id=e.exam_id LEFT JOIN results r ON r.exam_id=e.exam_id AND r.student_id=%s WHERE e.is_published=1 AND r.result_id IS NULL GROUP BY e.exam_id ORDER BY e.created_at DESC", (session["user_id"],))
            exams = cur.fetchall()
            cur.execute("SELECT r.result_id,r.score,r.total_marks,r.submitted_at,e.exam_name FROM results r JOIN exams e ON e.exam_id=r.exam_id WHERE r.student_id=%s AND r.is_published=1 ORDER BY r.submitted_at DESC LIMIT 4", (session["user_id"],))
            latest_results = cur.fetchall()
            cur.execute("SELECT COUNT(*) total FROM results r WHERE r.student_id=%s AND r.is_published=1", (session["user_id"],))
            completed_count = cur.fetchone()["total"]
            cur.execute("SELECT COALESCE(ROUND(AVG(r.score / NULLIF(r.total_marks,0) * 100)),0) average_score FROM results r WHERE r.student_id=%s AND r.is_published=1", (session["user_id"],))
            average_score = cur.fetchone()["average_score"]
        for exam in exams:
            exam["status"] = schedule_state(exam)
        available_exams = [exam for exam in exams if exam["question_count"] and exam["status"] != "Ended"]
        open_count = sum(exam["status"] == "Available" for exam in exams if exam["question_count"])
        return render_template("home.html", role="student", exams=available_exams[:3],
                               available_count=open_count, completed_count=completed_count,
                               average_score=average_score, latest_results=latest_results)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name or "@" not in email or len(password) < 8:
                flash("Enter a name, valid email, and password of at least 8 characters.", "error")
                return render_template("register.html")
            try:
                with cursor() as cur:
                    cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'student')",
                                (name, email, generate_password_hash(password)))
                get_db().commit()
            except Exception:
                get_db().rollback()
                flash("That email is already registered.", "error")
                return render_template("register.html")
            flash("Account created. You can sign in now.", "success")
            return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email, password = request.form.get("email", "").strip().lower(), request.form.get("password", "")
            with cursor(dictionary=True) as cur:
                cur.execute("SELECT user_id,name,password_hash,role FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
            if not user or not check_password_hash(user["password_hash"], password):
                flash("Email or password is incorrect.", "error")
                return render_template("login.html")
            session.clear()
            session.update(user_id=user["user_id"], name=user["name"], role=user["role"])
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/admin/dashboard")
    @login_required("admin")
    def admin_dashboard():
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT COUNT(*) AS n FROM users WHERE role='student'")
            students = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS attempts, COALESCE(ROUND(AVG(score / NULLIF(total_marks,0) * 100)),0) AS average_score FROM results")
            result_stats = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS n FROM questions")
            question_count = cur.fetchone()["n"]
            cur.execute("SELECT e.*, COUNT(DISTINCT q.question_id) question_count, COUNT(DISTINCT r.result_id) attempt_count, COUNT(DISTINCT CASE WHEN r.is_published=1 THEN r.result_id END) released_count FROM exams e LEFT JOIN questions q ON q.exam_id=e.exam_id LEFT JOIN results r ON r.exam_id=e.exam_id GROUP BY e.exam_id ORDER BY e.created_at DESC")
            exams = cur.fetchall()
            cur.execute("SELECT r.*,u.name student_name,e.exam_name FROM results r JOIN users u ON u.user_id=r.student_id JOIN exams e ON e.exam_id=r.exam_id ORDER BY r.submitted_at DESC LIMIT 50")
            results = cur.fetchall()
        for exam in exams:
            exam["status"] = schedule_state(exam)
        return render_template("admin_dashboard.html", students=students, exams=exams, results=results,
                               total_attempts=result_stats["attempts"], average_score=result_stats["average_score"],
                               total_questions=question_count)

    @app.get("/admin/students")
    @login_required("admin")
    def student_directory():
        with cursor(dictionary=True) as cur:
            cur.execute("""SELECT u.user_id,u.name,u.email,u.created_at,COUNT(r.result_id) attempts,
                COALESCE(ROUND(AVG(r.score / NULLIF(r.total_marks,0) * 100)),0) average_score
                FROM users u LEFT JOIN results r ON r.student_id=u.user_id
                WHERE u.role='student' GROUP BY u.user_id ORDER BY u.created_at DESC""")
            students = cur.fetchall()
        return render_template("student_directory.html", students=students)

    @app.get("/admin/students/<int:student_id>")
    @login_required("admin")
    def student_profile(student_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT user_id,name,email,created_at FROM users WHERE user_id=%s AND role='student'", (student_id,))
            student = cur.fetchone()
            if not student:
                abort(404)
            cur.execute("""SELECT r.result_id,r.score,r.total_marks,r.submitted_at,e.exam_name
                FROM results r JOIN exams e ON e.exam_id=r.exam_id
                WHERE r.student_id=%s ORDER BY r.submitted_at DESC""", (student_id,))
            results = cur.fetchall()
        percentages = [round(row["score"] / row["total_marks"] * 100) if row["total_marks"] else 0 for row in results]
        stats = {"attempts": len(results), "average": round(sum(percentages) / len(percentages)) if percentages else 0,
                 "best": max(percentages, default=0)}
        return render_template("student_profile.html", student=student, results=results, stats=stats)

    @app.get("/results/<int:result_id>/review")
    @login_required()
    def review_answers(result_id):
        with cursor(dictionary=True) as cur:
            cur.execute("""SELECT r.result_id,r.score,r.total_marks,r.submitted_at,r.is_published,
                u.user_id student_id,u.name student_name,e.exam_name,e.marks_per_question
                FROM results r JOIN users u ON u.user_id=r.student_id
                JOIN exams e ON e.exam_id=r.exam_id WHERE r.result_id=%s""", (result_id,))
            result_row = cur.fetchone()
            if not result_row:
                abort(404)
            if session["role"] == "student" and result_row["student_id"] != session["user_id"]:
                abort(404)
            if session["role"] == "student" and not result_row["is_published"]:
                flash("Your teacher has not published this result yet.", "success")
                return redirect(url_for("student_dashboard"))
            cur.execute("""SELECT q.question_id,q.question_text,q.option_a,q.option_b,q.option_c,q.option_d,
                q.correct_answer,ra.selected_answer,ra.result_id answer_recorded,e.marks_per_question
                FROM questions q JOIN results r ON r.exam_id=q.exam_id
                JOIN exams e ON e.exam_id=r.exam_id
                LEFT JOIN result_answers ra ON ra.result_id=r.result_id AND ra.question_id=q.question_id
                WHERE r.result_id=%s ORDER BY q.question_id""", (result_id,))
            answers = cur.fetchall()
        return render_template("answer_review.html", result=result_row, answers=answers)

    @app.get("/admin/analytics")
    @login_required("admin")
    def admin_analytics():
        with cursor(dictionary=True) as cur:
            cur.execute("""SELECT e.exam_id,e.exam_name,COUNT(r.result_id) attempts,
                COALESCE(ROUND(AVG(r.score / NULLIF(r.total_marks,0) * 100)),0) average_score,
                COALESCE(MAX(ROUND(r.score / NULLIF(r.total_marks,0) * 100)),0) top_score
                FROM exams e LEFT JOIN results r ON r.exam_id=e.exam_id
                GROUP BY e.exam_id ORDER BY attempts DESC,e.created_at DESC""")
            exam_stats = cur.fetchall()
            cur.execute("SELECT COUNT(*) attempts, COALESCE(ROUND(AVG(score / NULLIF(total_marks,0) * 100)),0) average_score, COALESCE(SUM(score / NULLIF(total_marks,0) >= 0.6),0) passed FROM results")
            summary = cur.fetchone()
        return render_template("admin_analytics.html", exam_stats=exam_stats, summary=summary)

    @app.route("/admin/exams/new", methods=["GET", "POST"])
    @login_required("admin")
    def create_exam():
        if request.method == "POST":
            name, description = request.form.get("exam_name", "").strip(), request.form.get("description", "").strip()
            try:
                duration = int(request.form.get("duration", "0"))
                marks = int(request.form.get("marks_per_question", "1"))
                starts_at = parse_schedule_datetime(request.form.get("starts_at", ""), app.config["APP_TIMEZONE"])
                ends_at = parse_schedule_datetime(request.form.get("ends_at", ""), app.config["APP_TIMEZONE"])
            except (ValueError, TypeError):
                duration, marks = 0, 0
                starts_at, ends_at = None, None
                schedule_error = True
            else:
                schedule_error = False
            if not name or not 1 <= duration <= 600 or not 1 <= marks <= 100 or schedule_error or (starts_at and ends_at and ends_at <= starts_at):
                flash("Check the exam name, duration, marks, and make sure the end time is after the start time.", "error")
            else:
                with cursor() as cur:
                    cur.execute("INSERT INTO exams (exam_name,description,duration_minutes,marks_per_question,starts_at,ends_at,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (name, description, duration, marks, starts_at, ends_at, session["user_id"]))
                    exam_id = cur.lastrowid
                get_db().commit()
                return redirect(url_for("manage_questions", exam_id=exam_id))
            return render_template("create_exam.html", starts_at=request.form.get("starts_at", ""), ends_at=request.form.get("ends_at", ""), timezone_name=app.config["APP_TIMEZONE"])
        return render_template("create_exam.html", starts_at="", ends_at="", timezone_name=app.config["APP_TIMEZONE"])

    @app.route("/admin/exams/<int:exam_id>/edit", methods=["GET", "POST"])
    @login_required("admin")
    def edit_exam(exam_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM exams WHERE exam_id=%s", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                abort(404)
            if request.method == "POST":
                name, description = request.form.get("exam_name", "").strip(), request.form.get("description", "").strip()
                try:
                    duration = int(request.form.get("duration", "0"))
                    marks = int(request.form.get("marks_per_question", "1"))
                    starts_at = parse_schedule_datetime(request.form.get("starts_at", ""), app.config["APP_TIMEZONE"])
                    ends_at = parse_schedule_datetime(request.form.get("ends_at", ""), app.config["APP_TIMEZONE"])
                    schedule_error = False
                except (ValueError, TypeError):
                    duration, marks, starts_at, ends_at, schedule_error = 0, 0, None, None, True
                if not name or not 1 <= duration <= 600 or not 1 <= marks <= 100 or schedule_error or (starts_at and ends_at and ends_at <= starts_at):
                    flash("Check the exam name, duration, marks, and make sure the end time is after the start time.", "error")
                    exam.update(exam_name=name, description=description,
                                duration_minutes=request.form.get("duration", "30"),
                                marks_per_question=request.form.get("marks_per_question", "1"))
                    starts_value, ends_value = request.form.get("starts_at", ""), request.form.get("ends_at", "")
                else:
                    cur.execute("UPDATE exams SET exam_name=%s,description=%s,duration_minutes=%s,marks_per_question=%s,starts_at=%s,ends_at=%s WHERE exam_id=%s",
                                (name, description, duration, marks, starts_at, ends_at, exam_id))
                    get_db().commit()
                    flash("Examination details updated.", "success")
                    return redirect(url_for("manage_questions", exam_id=exam_id))
            else:
                starts_value = local_schedule_value(exam["starts_at"], app.config["APP_TIMEZONE"])
                ends_value = local_schedule_value(exam["ends_at"], app.config["APP_TIMEZONE"])
        return render_template("create_exam.html", exam=exam, starts_at=starts_value, ends_at=ends_value,
                               timezone_name=app.config["APP_TIMEZONE"])

    @app.route("/admin/exams/<int:exam_id>/questions", methods=["GET", "POST"])
    @login_required("admin")
    def manage_questions(exam_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM exams WHERE exam_id=%s", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                abort(404)
            exam["status"] = schedule_state(exam)
            if request.method == "POST":
                question = request.form.get("question_text", "").strip()
                options = [request.form.get(f"option_{letter.lower()}", "").strip() for letter in "ABCD"]
                answer = request.form.get("correct_answer", "").upper()
                if not question or not all(options) or answer not in ("A", "B", "C", "D"):
                    flash("Fill in the question, all four options, and the correct answer.", "error")
                else:
                    cur.execute("INSERT INTO questions (exam_id,question_text,option_a,option_b,option_c,option_d,correct_answer) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (exam_id, question, *options, answer))
                    get_db().commit()
                    flash("Question added.", "success")
                    return redirect(url_for("manage_questions", exam_id=exam_id))
            cur.execute("SELECT question_id,question_text,option_a,option_b,option_c,option_d FROM questions WHERE exam_id=%s ORDER BY question_id", (exam_id,))
            questions = cur.fetchall()
        return render_template("manage_questions.html", exam=exam, questions=questions,
                               starts_at=local_schedule_value(exam["starts_at"], app.config["APP_TIMEZONE"]),
                               ends_at=local_schedule_value(exam["ends_at"], app.config["APP_TIMEZONE"]))

    @app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
    @login_required("admin")
    def edit_question(question_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM questions WHERE question_id=%s", (question_id,))
            question = cur.fetchone()
            if not question:
                abort(404)
            if request.method == "POST":
                question_text = request.form.get("question_text", "").strip()
                options = [request.form.get(f"option_{letter.lower()}", "").strip() for letter in "ABCD"]
                answer = request.form.get("correct_answer", "").upper()
                if not question_text or not all(options) or answer not in ("A", "B", "C", "D"):
                    flash("Fill in the question, all four options, and the correct answer.", "error")
                    question.update(question_text=question_text, option_a=options[0], option_b=options[1],
                                    option_c=options[2], option_d=options[3], correct_answer=answer)
                else:
                    cur.execute("UPDATE questions SET question_text=%s,option_a=%s,option_b=%s,option_c=%s,option_d=%s,correct_answer=%s WHERE question_id=%s",
                                (question_text, *options, answer, question_id))
                    get_db().commit()
                    flash("Question updated.", "success")
                    return redirect(url_for("manage_questions", exam_id=question["exam_id"]))
        return render_template("edit_question.html", question=question)

    @app.post("/admin/exams/<int:exam_id>/publish")
    @login_required("admin")
    def publish_exam(exam_id):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT starts_at,ends_at FROM exams WHERE exam_id=%s", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                abort(404)
            cur.execute("SELECT COUNT(*) AS total FROM questions WHERE exam_id=%s", (exam_id,))
            question_count = cur.fetchone()["total"]
            if not question_count:
                flash("Add at least one question before publishing this examination.", "error")
                return redirect(url_for("manage_questions", exam_id=exam_id))
            if exam["starts_at"] and exam["ends_at"] and exam["ends_at"] <= exam["starts_at"]:
                flash("The end time must be after the start time.", "error")
                return redirect(url_for("manage_questions", exam_id=exam_id))
            if exam["ends_at"] and exam["ends_at"] <= now:
                flash("The end time has already passed. Update the schedule before publishing.", "error")
                return redirect(url_for("manage_questions", exam_id=exam_id))
            cur.execute("UPDATE exams SET is_published=1 WHERE exam_id=%s", (exam_id,))
        get_db().commit()
        flash("Examination published. Students can see it according to its schedule.", "success")
        return redirect(url_for("manage_questions", exam_id=exam_id))

    @app.post("/admin/exams/<int:exam_id>/publish-results")
    @login_required("admin")
    def publish_results(exam_id):
        with cursor() as cur:
            cur.execute("SELECT COUNT(*),COALESCE(SUM(is_published=0),0) FROM results WHERE exam_id=%s", (exam_id,))
            attempts, pending = cur.fetchone()
            if attempts == 0:
                flash("There are no submitted attempts to release yet.", "error")
                return redirect(url_for("admin_dashboard"))
            cur.execute("UPDATE results SET is_published=1 WHERE exam_id=%s", (exam_id,))
        get_db().commit()
        flash(f"{pending} result{'s' if pending != 1 else ''} published. Students can now view their scores.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/exams/<int:exam_id>/unpublish")
    @login_required("admin")
    def unpublish_exam(exam_id):
        with cursor() as cur:
            cur.execute("SELECT exam_id FROM exams WHERE exam_id=%s", (exam_id,))
            if not cur.fetchone():
                abort(404)
            cur.execute("UPDATE exams SET is_published=0 WHERE exam_id=%s", (exam_id,))
        get_db().commit()
        flash("Examination unpublished. Students can no longer start it.", "success")
        return redirect(url_for("manage_questions", exam_id=exam_id))

    @app.post("/admin/questions/<int:question_id>/delete")
    @login_required("admin")
    def delete_question(question_id):
        with cursor() as cur:
            cur.execute("SELECT q.exam_id,e.is_published FROM questions q JOIN exams e ON e.exam_id=q.exam_id WHERE q.question_id=%s", (question_id,))
            row = cur.fetchone()
            if not row:
                abort(404)
            exam_id = row[0]
            was_published = row[1]
            cur.execute("DELETE FROM questions WHERE question_id=%s", (question_id,))
            cur.execute("SELECT COUNT(*) FROM questions WHERE exam_id=%s", (exam_id,))
            auto_unpublished = cur.fetchone()[0] == 0 and bool(was_published)
            if auto_unpublished:
                cur.execute("UPDATE exams SET is_published=0 WHERE exam_id=%s", (exam_id,))
        get_db().commit()
        message = "Question removed. The empty examination was automatically unpublished." if auto_unpublished else "Question removed."
        flash(message, "success")
        return redirect(url_for("manage_questions", exam_id=exam_id))

    @app.post("/admin/exams/<int:exam_id>/delete")
    @login_required("admin")
    def delete_exam(exam_id):
        with cursor() as cur:
            cur.execute("DELETE FROM exams WHERE exam_id=%s", (exam_id,))
        get_db().commit()
        flash("Examination deleted.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.get("/student/dashboard")
    @login_required("student")
    def student_dashboard():
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT e.*,COUNT(q.question_id) question_count, r.result_id attempted, r.score, r.total_marks, r.is_published results_published FROM exams e LEFT JOIN questions q ON q.exam_id=e.exam_id LEFT JOIN results r ON r.exam_id=e.exam_id AND r.student_id=%s WHERE e.is_published=1 GROUP BY e.exam_id,r.result_id ORDER BY e.created_at DESC", (session["user_id"],))
            exams = cur.fetchall()
        for exam in exams:
            exam["status"] = schedule_state(exam)
        return render_template("student_dashboard.html", exams=exams)

    @app.get("/exams/<int:exam_id>")
    @login_required("student")
    def exam_details(exam_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT e.*,COUNT(q.question_id) question_count FROM exams e LEFT JOIN questions q ON q.exam_id=e.exam_id WHERE e.exam_id=%s AND e.is_published=1 GROUP BY e.exam_id", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                abort(404)
            cur.execute("SELECT result_id,score,total_marks,is_published results_published FROM results WHERE exam_id=%s AND student_id=%s", (exam_id, session["user_id"]))
            attempt = cur.fetchone()
        exam["status"] = schedule_state(exam)
        return render_template("exam_details.html", exam=exam, attempt=attempt,
                               starts_at=local_schedule_value(exam["starts_at"], app.config["APP_TIMEZONE"]),
                               ends_at=local_schedule_value(exam["ends_at"], app.config["APP_TIMEZONE"]),
                               timezone_name=app.config["APP_TIMEZONE"])

    @app.get("/student/analysis")
    @login_required("student")
    def score_analysis():
        with cursor(dictionary=True) as cur:
            cur.execute("""SELECT r.result_id,r.score,r.total_marks,r.submitted_at,e.exam_name
                FROM results r JOIN exams e ON e.exam_id=r.exam_id
                WHERE r.student_id=%s AND r.is_published=1 ORDER BY r.submitted_at DESC""", (session["user_id"],))
            results = cur.fetchall()
        results.reverse()
        percentages = [round((row["score"] / row["total_marks"] * 100) if row["total_marks"] else 0) for row in results]
        count = len(results)
        chart_rows = results[-12:]
        chart_scores = percentages[-12:]
        chart_coords = []
        chart_count = len(chart_rows)
        for index, score in enumerate(chart_scores):
            x = 300 if chart_count == 1 else round(40 + index * 520 / (chart_count - 1))
            y = round(170 - score * 1.3)
            chart_coords.append({"x": x, "y": y, "score": score, "name": chart_rows[index]["exam_name"]})
        chart_path = " ".join(("M" if i == 0 else "L") + f"{p['x']},{p['y']}" for i, p in enumerate(chart_coords))
        bands = [sum(score < 40 for score in percentages), sum(40 <= score < 60 for score in percentages),
                 sum(60 <= score < 80 for score in percentages), sum(score >= 80 for score in percentages)]
        stats = {
            "attempts": count,
            "average": round(sum(percentages) / count) if count else 0,
            "best": max(percentages, default=0),
            "passed": sum(score >= 60 for score in percentages),
        }
        return render_template("score_analysis.html", results=results, chart_coords=chart_coords,
                               chart_path=chart_path, stats=stats, bands=bands,
                               chart_labels=[row["submitted_at"].strftime("%b %d") for row in chart_rows])

    @app.route("/exam/<int:exam_id>", methods=["GET", "POST"])
    @login_required("student")
    def take_exam(exam_id):
        with cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM exams WHERE exam_id=%s", (exam_id,))
            exam = cur.fetchone()
            if not exam or not exam["is_published"]:
                abort(404)
            cur.execute("SELECT result_id FROM results WHERE exam_id=%s AND student_id=%s", (exam_id, session["user_id"]))
            if cur.fetchone():
                flash("You have already submitted this examination.", "error")
                return redirect(url_for("student_dashboard"))
            cur.execute("SELECT question_id,question_text,option_a,option_b,option_c,option_d FROM questions WHERE exam_id=%s ORDER BY question_id", (exam_id,))
            questions = cur.fetchall()
        if not questions:
            flash("This examination has no questions yet.", "error")
            return redirect(url_for("student_dashboard"))
        key = f"exam_started_{exam_id}"
        now = datetime.now(timezone.utc)
        starts_at = exam["starts_at"].replace(tzinfo=timezone.utc) if exam["starts_at"] else None
        ends_at = exam["ends_at"].replace(tzinfo=timezone.utc) if exam["ends_at"] else None
        if starts_at and now < starts_at:
            flash("This examination has not opened yet.", "error")
            return redirect(url_for("exam_details", exam_id=exam_id))
        if ends_at and now >= ends_at and key not in session:
            flash("The examination window has closed.", "error")
            return redirect(url_for("exam_details", exam_id=exam_id))
        if request.method == "GET":
            session.setdefault(key, datetime.now(timezone.utc).isoformat())
        else:
            try:
                started = datetime.fromisoformat(session[key])
            except (KeyError, ValueError):
                flash("Start the examination before submitting it.", "error")
                return redirect(url_for("take_exam", exam_id=exam_id))
            deadline = started + timedelta(minutes=exam["duration_minutes"])
            if ends_at and ends_at < deadline:
                deadline = ends_at
            if now > deadline + timedelta(seconds=15):
                answers = {}
            else:
                answers = {str(q["question_id"]): request.form.get(f"q_{q['question_id']}", "").upper() for q in questions}
            # Load answer keys only during the POST so they are never passed
            # to the examination template rendered for students.
            with cursor(dictionary=True) as cur:
                cur.execute("SELECT question_id,correct_answer FROM questions WHERE exam_id=%s ORDER BY question_id", (exam_id,))
                answer_key = cur.fetchall()
            score = calculate_score(answer_key, answers, exam["marks_per_question"])
            total = len(questions) * exam["marks_per_question"]
            try:
                with cursor() as cur:
                    cur.execute("INSERT INTO results (student_id,exam_id,score,total_marks) VALUES (%s,%s,%s,%s)",
                                (session["user_id"], exam_id, score, total))
                    result_id = cur.lastrowid
                    cur.executemany("INSERT INTO result_answers (result_id,question_id,selected_answer) VALUES (%s,%s,%s)", [
                        (result_id, question["question_id"], answers.get(str(question["question_id"])) or None)
                        for question in questions
                    ])
                get_db().commit()
            except Exception:
                get_db().rollback()
                flash("This examination has already been submitted.", "error")
                return redirect(url_for("student_dashboard"))
            session.pop(key, None)
            return redirect(url_for("result", result_id=result_id))
        started = datetime.fromisoformat(session[key])
        deadline = started + timedelta(minutes=exam["duration_minutes"])
        if ends_at and ends_at < deadline:
            deadline = ends_at
        deadline_seconds = max(0, int((deadline - now).total_seconds()))
        return render_template("examination.html", exam=exam, questions=questions, deadline_seconds=deadline_seconds)

    @app.get("/results/<int:result_id>")
    @login_required()
    def result(result_id):
        with cursor(dictionary=True) as cur:
            query = "SELECT r.*,e.exam_name FROM results r JOIN exams e ON e.exam_id=r.exam_id WHERE r.result_id=%s"
            params = (result_id,)
            if session["role"] == "student":
                query += " AND r.student_id=%s"
                params += (session["user_id"],)
            cur.execute(query, params)
            row = cur.fetchone()
        if not row:
            abort(404)
        if session["role"] == "student" and not row["is_published"]:
            flash("Your submission is recorded. The teacher has not published results yet.", "success")
            return redirect(url_for("student_dashboard"))
        return render_template("result.html", result=row)

    @app.cli.command("init-db")
    def init_db_command():
        from db import init_db
        init_db()
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_password:
            with cursor() as cur:
                cur.execute("INSERT IGNORE INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'admin')",
                            (os.getenv("ADMIN_NAME", "Administrator"), admin_email.lower(), generate_password_hash(admin_password)))
            get_db().commit()
        print("Database initialized.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
