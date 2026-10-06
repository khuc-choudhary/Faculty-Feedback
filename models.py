from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Feedback questions, each rated 1 (Poor) to 5 (Excellent).
QUESTIONS = [
    ("q1", "Clarity of explanation and teaching methodology"),
    ("q2", "Subject knowledge and command over the topic"),
    ("q3", "Punctuality and regularity in taking classes"),
    ("q4", "Interaction with students and doubt clearing"),
    ("q5", "Completion of syllabus on time"),
    ("q6", "Use of examples, practicals and teaching aids"),
    ("q7", "Fairness in evaluation of assignments and tests"),
    ("q8", "Overall effectiveness of the faculty"),
]

RATING_LABELS = {1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent"}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin | faculty | student
    department = db.Column(db.String(100))
    semester = db.Column(db.Integer)          # students only
    designation = db.Column(db.String(100))   # faculty only
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subjects = db.relationship("Subject", back_populates="faculty", lazy=True)
    feedbacks = db.relationship(
        "Feedback", back_populates="student", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    faculty = db.relationship("User", back_populates="subjects")
    feedbacks = db.relationship(
        "Feedback", back_populates="subject", lazy=True, cascade="all, delete-orphan"
    )

    def average_rating(self):
        if not self.feedbacks:
            return None
        return round(sum(f.average() for f in self.feedbacks) / len(self.feedbacks), 2)

    def question_averages(self):
        if not self.feedbacks:
            return {key: None for key, _ in QUESTIONS}
        n = len(self.feedbacks)
        return {
            key: round(sum(getattr(f, key) for f in self.feedbacks) / n, 2)
            for key, _ in QUESTIONS
        }


class Feedback(db.Model):
    __tablename__ = "feedbacks"
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    q1 = db.Column(db.Integer, nullable=False)
    q2 = db.Column(db.Integer, nullable=False)
    q3 = db.Column(db.Integer, nullable=False)
    q4 = db.Column(db.Integer, nullable=False)
    q5 = db.Column(db.Integer, nullable=False)
    q6 = db.Column(db.Integer, nullable=False)
    q7 = db.Column(db.Integer, nullable=False)
    q8 = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("User", back_populates="feedbacks")
    subject = db.relationship("Subject", back_populates="feedbacks")

    def average(self):
        return sum(getattr(self, key) for key, _ in QUESTIONS) / len(QUESTIONS)
