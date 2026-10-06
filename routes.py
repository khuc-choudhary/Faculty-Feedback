from datetime import datetime
from functools import wraps
from io import BytesIO

import pandas as pd
from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from models import QUESTIONS, RATING_LABELS, Feedback, Subject, User, db

main = Blueprint("main", __name__)


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------

@main.before_app_request
def load_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


@main.app_context_processor
def inject_globals():
    return {"current_user": g.get("user"), "QUESTIONS": QUESTIONS,
            "RATING_LABELS": RATING_LABELS}


def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("main.login", next=request.path))
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def home_for(user):
    return url_for({"admin": "main.admin_dashboard",
                    "faculty": "main.faculty_dashboard",
                    "student": "main.student_dashboard"}[user.role])


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

@main.route("/")
def index():
    if g.user:
        return redirect(home_for(g.user))
    return redirect(url_for("main.login"))


@main.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(home_for(g.user))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            flash(f"Welcome, {user.name}!", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(home_for(user))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@main.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


@main.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not g.user.check_password(current):
            flash("Current password is incorrect.", "danger")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        else:
            g.user.set_password(new)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(home_for(g.user))
    return render_template("change_password.html")


# --------------------------------------------------------------------------
# Admin: dashboard
# --------------------------------------------------------------------------

@main.route("/admin")
@login_required("admin")
def admin_dashboard():
    subjects = Subject.query.all()
    rated = [s for s in subjects if s.feedbacks]
    stats = {
        "faculty": User.query.filter_by(role="faculty").count(),
        "students": User.query.filter_by(role="student").count(),
        "subjects": len(subjects),
        "feedbacks": Feedback.query.count(),
        "overall": round(sum(s.average_rating() for s in rated) / len(rated), 2) if rated else None,
    }
    top = sorted(rated, key=lambda s: s.average_rating(), reverse=True)[:5]
    recent = Feedback.query.order_by(Feedback.submitted_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, top=top, recent=recent)


# --------------------------------------------------------------------------
# Admin: faculty & students (shared user management)
# --------------------------------------------------------------------------

def create_user_from_form(role):
    form = request.form
    name = form.get("name", "").strip()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    if not name or not username or not password:
        flash("Name, username and password are required.", "danger")
        return False
    if User.query.filter_by(username=username).first():
        flash(f"Username '{username}' already exists.", "danger")
        return False
    user = User(
        name=name,
        username=username,
        email=form.get("email", "").strip() or None,
        role=role,
        department=form.get("department", "").strip() or None,
        semester=to_int(form.get("semester")) if role == "student" else None,
        designation=(form.get("designation", "").strip() or None) if role == "faculty" else None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"{role.title()} '{name}' added.", "success")
    return True


@main.route("/admin/faculty", methods=["GET", "POST"])
@login_required("admin")
def admin_faculty():
    if request.method == "POST":
        create_user_from_form("faculty")
        return redirect(url_for("main.admin_faculty"))
    faculty = User.query.filter_by(role="faculty").order_by(User.name).all()
    return render_template("admin/faculty.html", faculty=faculty)


@main.route("/admin/students", methods=["GET", "POST"])
@login_required("admin")
def admin_students():
    if request.method == "POST":
        create_user_from_form("student")
        return redirect(url_for("main.admin_students"))
    query = User.query.filter_by(role="student")
    dept = request.args.get("department", "").strip()
    sem = to_int(request.args.get("semester"))
    if dept:
        query = query.filter_by(department=dept)
    if sem:
        query = query.filter_by(semester=sem)
    students = query.order_by(User.department, User.semester, User.username).all()
    departments = sorted({d for (d,) in db.session.query(User.department)
                          .filter(User.role == "student", User.department.isnot(None)).distinct()})
    return render_template("admin/students.html", students=students,
                           departments=departments, dept=dept, sem=sem)


@main.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def admin_edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        abort(404)
    if request.method == "POST":
        form = request.form
        username = form.get("username", "").strip()
        clash = User.query.filter(User.username == username, User.id != user.id).first()
        if not form.get("name", "").strip() or not username:
            flash("Name and username are required.", "danger")
        elif clash:
            flash(f"Username '{username}' already exists.", "danger")
        else:
            user.name = form["name"].strip()
            user.username = username
            user.email = form.get("email", "").strip() or None
            user.department = form.get("department", "").strip() or None
            if user.role == "student":
                user.semester = to_int(form.get("semester"))
            else:
                user.designation = form.get("designation", "").strip() or None
            if form.get("password"):
                user.set_password(form["password"])
            db.session.commit()
            flash("Details updated.", "success")
            return redirect(url_for("main.admin_faculty" if user.role == "faculty"
                                    else "main.admin_students"))
    return render_template("admin/edit_user.html", user=user)


@main.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        abort(403)
    role = user.role
    if role == "faculty":
        for subject in user.subjects:
            subject.faculty_id = None
    db.session.delete(user)
    db.session.commit()
    flash(f"{role.title()} '{user.name}' deleted.", "info")
    return redirect(url_for("main.admin_faculty" if role == "faculty" else "main.admin_students"))


@main.route("/admin/students/import", methods=["POST"])
@login_required("admin")
def admin_import_students():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please choose an Excel or CSV file.", "danger")
        return redirect(url_for("main.admin_students"))
    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str, engine="openpyxl")
    except Exception as exc:
        flash(f"Could not read file: {exc}", "danger")
        return redirect(url_for("main.admin_students"))

    df.columns = [str(c).strip().lower() for c in df.columns]
    required = {"name", "username", "password"}
    missing = required - set(df.columns)
    if missing:
        flash(f"Missing required column(s): {', '.join(sorted(missing))}", "danger")
        return redirect(url_for("main.admin_students"))

    df = df.fillna("")
    existing = {u for (u,) in db.session.query(User.username)}
    added, skipped = 0, 0
    for _, row in df.iterrows():
        username = str(row["username"]).strip()
        name = str(row["name"]).strip()
        password = str(row["password"]).strip()
        if not username or not name or not password or username in existing:
            skipped += 1
            continue
        student = User(
            name=name,
            username=username,
            email=str(row.get("email", "")).strip() or None,
            role="student",
            department=str(row.get("department", "")).strip() or None,
            semester=to_int(str(row.get("semester", "")).strip().split(".")[0]),
        )
        student.set_password(password)
        db.session.add(student)
        existing.add(username)
        added += 1
    db.session.commit()
    flash(f"Import complete: {added} student(s) added, {skipped} row(s) skipped.",
          "success" if added else "warning")
    return redirect(url_for("main.admin_students"))


@main.route("/admin/students/template")
@login_required("admin")
def admin_student_template():
    df = pd.DataFrame([
        {"name": "Asha Verma", "username": "CS2023001", "password": "pass123",
         "email": "asha@example.com", "department": "Computer Science", "semester": 3},
    ])
    return excel_response({"Students": df}, "student_import_template.xlsx")


# --------------------------------------------------------------------------
# Admin: subjects
# --------------------------------------------------------------------------

def apply_subject_form(subject):
    form = request.form
    code = form.get("code", "").strip().upper()
    name = form.get("name", "").strip()
    department = form.get("department", "").strip()
    semester = to_int(form.get("semester"))
    if not code or not name or not department or not semester:
        flash("Code, name, department and semester are required.", "danger")
        return False
    clash = Subject.query.filter(Subject.code == code, Subject.id != subject.id).first()
    if clash:
        flash(f"Subject code '{code}' already exists.", "danger")
        return False
    subject.code, subject.name = code, name
    subject.department, subject.semester = department, semester
    subject.faculty_id = to_int(form.get("faculty_id"))
    return True


@main.route("/admin/subjects", methods=["GET", "POST"])
@login_required("admin")
def admin_subjects():
    if request.method == "POST":
        subject = Subject()
        if apply_subject_form(subject):
            db.session.add(subject)
            db.session.commit()
            flash(f"Subject '{subject.name}' added.", "success")
        return redirect(url_for("main.admin_subjects"))
    subjects = Subject.query.order_by(Subject.department, Subject.semester, Subject.code).all()
    faculty = User.query.filter_by(role="faculty").order_by(User.name).all()
    return render_template("admin/subjects.html", subjects=subjects, faculty=faculty)


@main.route("/admin/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def admin_edit_subject(subject_id):
    subject = db.get_or_404(Subject, subject_id)
    if request.method == "POST" and apply_subject_form(subject):
        db.session.commit()
        flash("Subject updated.", "success")
        return redirect(url_for("main.admin_subjects"))
    faculty = User.query.filter_by(role="faculty").order_by(User.name).all()
    return render_template("admin/edit_subject.html", subject=subject, faculty=faculty)


@main.route("/admin/subjects/<int:subject_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_subject(subject_id):
    subject = db.get_or_404(Subject, subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash(f"Subject '{subject.name}' deleted.", "info")
    return redirect(url_for("main.admin_subjects"))


# --------------------------------------------------------------------------
# Admin: reports & Excel export
# --------------------------------------------------------------------------

@main.route("/admin/reports")
@login_required("admin")
def admin_reports():
    subjects = Subject.query.order_by(Subject.department, Subject.semester, Subject.code).all()
    rows = []
    for s in subjects:
        eligible = User.query.filter_by(role="student", department=s.department,
                                        semester=s.semester).count()
        rows.append({"subject": s, "responses": len(s.feedbacks), "eligible": eligible,
                     "average": s.average_rating()})
    return render_template("admin/reports.html", rows=rows)


@main.route("/admin/reports/<int:subject_id>")
@login_required("admin")
def admin_subject_report(subject_id):
    subject = db.get_or_404(Subject, subject_id)
    return render_template("admin/subject_report.html", subject=subject,
                           averages=subject.question_averages(),
                           distribution=rating_distribution(subject.feedbacks))


def rating_distribution(feedbacks):
    dist = {r: 0 for r in range(1, 6)}
    for f in feedbacks:
        for key, _ in QUESTIONS:
            dist[getattr(f, key)] += 1
    return dist


def excel_response(sheets, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            for column in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
                ws.column_dimensions[column[0].column_letter].width = min(width + 2, 60)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@main.route("/admin/export")
@login_required("admin")
def admin_export():
    subjects = Subject.query.order_by(Subject.department, Subject.semester, Subject.code).all()

    summary = []
    for s in subjects:
        row = {
            "Subject Code": s.code, "Subject": s.name, "Department": s.department,
            "Semester": s.semester, "Faculty": s.faculty.name if s.faculty else "Unassigned",
            "Responses": len(s.feedbacks),
        }
        averages = s.question_averages()
        for key, text in QUESTIONS:
            row[text] = averages[key]
        row["Overall Average"] = s.average_rating()
        summary.append(row)

    faculty_rows = []
    for f in User.query.filter_by(role="faculty").order_by(User.name):
        feedbacks = [fb for s in f.subjects for fb in s.feedbacks]
        faculty_rows.append({
            "Faculty": f.name, "Designation": f.designation, "Department": f.department,
            "Subjects": ", ".join(s.code for s in f.subjects),
            "Responses": len(feedbacks),
            "Overall Average": round(sum(fb.average() for fb in feedbacks) / len(feedbacks), 2)
            if feedbacks else None,
        })

    # Responses are exported anonymously (no student identity).
    responses = []
    for fb in Feedback.query.order_by(Feedback.submitted_at):
        row = {"Submitted At": fb.submitted_at.strftime("%Y-%m-%d %H:%M"),
               "Subject Code": fb.subject.code, "Subject": fb.subject.name,
               "Faculty": fb.subject.faculty.name if fb.subject.faculty else "Unassigned"}
        for key, text in QUESTIONS:
            row[text] = getattr(fb, key)
        row["Average"] = round(fb.average(), 2)
        row["Comments"] = fb.comments or ""
        responses.append(row)

    sheets = {
        "Subject Summary": pd.DataFrame(summary),
        "Faculty Summary": pd.DataFrame(faculty_rows),
        "All Responses": pd.DataFrame(responses),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return excel_response(sheets, f"faculty_feedback_report_{stamp}.xlsx")


# --------------------------------------------------------------------------
# Student
# --------------------------------------------------------------------------

def student_subjects(student):
    return (Subject.query
            .filter_by(department=student.department, semester=student.semester)
            .order_by(Subject.code).all())


@main.route("/student")
@login_required("student")
def student_dashboard():
    subjects = student_subjects(g.user)
    done = {f.subject_id for f in g.user.feedbacks}
    return render_template("student/dashboard.html", subjects=subjects, done=done)


@main.route("/student/feedback/<int:subject_id>", methods=["GET", "POST"])
@login_required("student")
def submit_feedback(subject_id):
    subject = db.get_or_404(Subject, subject_id)
    if subject not in student_subjects(g.user) or subject.faculty is None:
        abort(403)
    if Feedback.query.filter_by(student_id=g.user.id, subject_id=subject.id).first():
        flash("You have already submitted feedback for this subject.", "info")
        return redirect(url_for("main.student_dashboard"))

    if request.method == "POST":
        ratings = {key: to_int(request.form.get(key)) for key, _ in QUESTIONS}
        if any(r is None or not 1 <= r <= 5 for r in ratings.values()):
            flash("Please rate every question from 1 to 5.", "danger")
            return render_template("student/feedback_form.html", subject=subject,
                                   ratings=ratings, comments=request.form.get("comments", ""))
        feedback = Feedback(student_id=g.user.id, subject_id=subject.id,
                            comments=request.form.get("comments", "").strip() or None,
                            **ratings)
        db.session.add(feedback)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("You have already submitted feedback for this subject.", "info")
            return redirect(url_for("main.student_dashboard"))
        flash(f"Thank you! Feedback for {subject.name} submitted.", "success")
        return redirect(url_for("main.student_dashboard"))

    return render_template("student/feedback_form.html", subject=subject, ratings={}, comments="")


# --------------------------------------------------------------------------
# Faculty
# --------------------------------------------------------------------------

@main.route("/faculty")
@login_required("faculty")
def faculty_dashboard():
    subjects = sorted(g.user.subjects, key=lambda s: s.code)
    data = [{"subject": s, "averages": s.question_averages(), "average": s.average_rating(),
             "comments": [f.comments for f in s.feedbacks if f.comments]}
            for s in subjects]
    return render_template("faculty/dashboard.html", data=data)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

@main.app_errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403,
                           message="You do not have permission to access this page."), 403


@main.app_errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="Page not found."), 404
