from sqlalchemy import JSON
from app import db
from sqlalchemy.dialects.postgresql import JSONB
from flask_login import UserMixin
from app import login_manager
from sqlalchemy import Integer, Sequence

# ✅ Table for Questions
class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(JSONB, nullable=False)  # JSON format: {"A": "...", "B": "...", "C": "...", "D": "..."}
    answer = db.Column(db.String(5), nullable=False)  
    solution = db.Column(db.Text, nullable=True)   

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "topic": self.topic,
            "level": self.level,
            "question_text": self.question_text,
            "options": self.options,
            "answer": self.answer,
            "solution": self.solution
        }

# ✅ Test Table (Stores assigned questions with full details)

class Test(db.Model):
    __tablename__ = 'test'

    test_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-incrementing Test ID
    student_id = db.Column(db.String(50), nullable=False)  # Assigned Student ID
    subject = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Pending")  # Test Status (Pending/Completed)
    questions = db.Column(db.JSON, nullable=False)  # Stores full question details in JSON format

    def to_dict(self):
        return {
            "id": self.id,
            "test_id": self.test_id,
            "student_id": self.student_id,
            "subject": self.subject,
            "status": self.status,
            "questions": self.questions  # Full question details
        }
    
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class UserRoles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'))

# ✅ User Table
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # Admin / Student

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ✅ Student Test Submission Table (Stores student responses + solutions)
class StudentTestSubmission(db.Model):
    __tablename__ = 'student_test_submission'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), nullable=False)
    test_id = db.Column(db.String(50), db.ForeignKey('test.test_id'), nullable=False)
    responses = db.Column(JSONB, nullable=False)  # Stores all questions, student answers, and solutions
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "test_id": self.test_id,
            "responses": self.responses,  # List of questions, correct answers, student answers, and solutions
            "score": self.score,
            "total_questions": self.total_questions,
            "date": self.date
        }
