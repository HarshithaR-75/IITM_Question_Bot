from sqlalchemy import JSON
from app import db

class Question(db.Model):
    __tablename__ = 'questions'  # You can choose an appropriate name here

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String, nullable=False)
    topic = db.Column(db.String, nullable=False)
    level = db.Column(db.String, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.ARRAY(db.String), nullable=False)  
    answer = db.Column(db.String, nullable=False)  
    solution = db.Column(db.Text, nullable=True)   

class TestResult(db.Model):
    __tablename__ = 'test_results'

    id = db.Column(db.Integer, primary_key=True)  # Test ID
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())
    results = db.Column(JSON, nullable=False)  # Store detailed results as JSON
