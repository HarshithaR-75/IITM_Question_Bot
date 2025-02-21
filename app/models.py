from sqlalchemy import JSON
from app import db
from sqlalchemy.dialects.postgresql import JSONB


class Question(db.Model):
    __tablename__ = 'questions'  # You can choose an appropriate name here

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String, nullable=False)
    topic = db.Column(db.String, nullable=False)
    level = db.Column(db.String, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(JSONB, nullable=False) 
    answer = db.Column(db.String, nullable=False)  
    solution = db.Column(db.Text, nullable=True)   

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "topic": self.topic,
            "level": self.level,
            "question_text": self.question_text,
            "options": self.options,  # Will return as a dictionary
            "answer": self.answer,
            "solution": self.solution
        }

class TestResult(db.Model):
    __tablename__ = 'test_results'

    id = db.Column(db.Integer, primary_key=True)  # Test ID
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())
    results = db.Column(JSON, nullable=False)  # Store detailed results as JSON
