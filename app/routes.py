from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_principal import Identity, identity_changed, AnonymousIdentity
from werkzeug.security import generate_password_hash, check_password_hash
from app.forms import RegistrationForm, LoginForm
from app.models import db, User, Question, Test, Role, StudentTestSubmission
import os
import openai
import json
import re

routes = Blueprint('routes', __name__, template_folder='templates')

@routes.route('/')
def home():
    return redirect(url_for('routes.login'))

@routes.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role_name = request.form.get('role')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('routes.register'))

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            flash('Invalid role selected.')
            return redirect(url_for('routes.register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        new_user = User(username=username, password=hashed_password, role=role_name)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful. Please log in.')
        return redirect(url_for('routes.login'))
    return render_template('register.html', form=form)

@routes.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data

        user = User.query.filter_by(username=username, role=role).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=form.remember.data)
            identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))

            return redirect(url_for('routes.dashboard')) if role == 'Student' else redirect(url_for('routes.admin'))
        else:
            flash('Invalid username, password, or role.')
    return render_template('login.html', form=form)

@routes.route('/logout')
@login_required
def logout():
    logout_user()
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    flash('You have been logged out.')
    return redirect(url_for('routes.login'))

@routes.route('/admin')
def admin():
    return render_template('index.html')

@routes.route('/dashboard')
def dashboard():
    all_tests = StudentTestSubmission.query.order_by(StudentTestSubmission.date.desc()).all()
    return render_template('dashboard.html', tests=all_tests)

client = openai.OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ.get("GITHUB_TOKEN"),
)

@routes.route('/generate_question', methods=['POST'])
def generate_question():
    data = request.get_json()
    student_id, subject, topic, level = data.get('studentId'), data.get('subject'), data.get('topic'), data.get('level')
    num_questions = int(data.get('numQuestions', 1))

    if not all([student_id, subject, topic, level, num_questions]):
        return jsonify({"error": "Missing required fields"}), 400

    with db.session.no_autoflush:  # Avoid premature commits
        # Find the highest existing test_id and increment it
        last_test = Test.query.order_by(Test.test_id.desc()).first()
        new_test_id = last_test.test_id + 1 if last_test else 1

        # Create a new test entry
        new_test = Test(test_id=new_test_id, student_id=student_id, subject=subject, status="Pending", questions=[])
        db.session.add(new_test)
        db.session.commit()

    # Fetch existing questions
    questions = Question.query.filter_by(subject=subject, topic=topic, level=level).limit(num_questions).all()
    question_list = [
        {"id": q.id, "question": q.question_text, "options": q.options, "correct_answer": q.answer}
        for q in questions
    ]

    # If not enough questions, generate more using OpenAI
    if len(questions) < num_questions:
        remaining_questions = num_questions - len(questions)
        prompt = f"Generate {remaining_questions} {level}-level questions on {topic} in {subject} with 4 options and answers in JSON format."
        
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an AI tutor helping generate questions."},
                {"role": "user", "content": prompt}
            ],
            model="gpt-4o-mini", temperature=1, max_tokens=1000, top_p=1
        )

        try:
            ai_response = json.loads(re.sub(r'```json|```', '', response.choices[0].message.content.strip()))
            if not isinstance(ai_response, list): ai_response = [ai_response]

            new_questions = []
            for q in ai_response:
                if not all(k in q for k in ("question", "options", "correct_answer")):
                    continue  # Skip invalid entries
                
                new_question = Question(
                    subject=subject, topic=topic, level=level, question_text=q["question"],
                    options=q.get("options", {}), answer=q["correct_answer"],
                    solution=q.get("detailed_solution", "No solution provided")
                )
                new_questions.append(new_question)
                question_list.append({
                    "id": None,  # ID will be assigned after commit
                    "question": new_question.question_text,
                    "options": new_question.options,
                    "correct_answer": new_question.answer
                })
            
            if new_questions:
                db.session.add_all(new_questions)
                db.session.commit()

                # Update with actual IDs
                for i, q in enumerate(new_questions):
                    question_list[len(questions) + i]["id"] = q.id

        except json.JSONDecodeError as e:
            return jsonify({"error": f"Error parsing AI response: {str(e)}"}), 500

    # Update test entry with generated questions
    new_test.questions = question_list
    db.session.commit()

    return jsonify({"test_id": new_test_id, "questions": question_list}), 201

@routes.route('/test_details/<int:test_id>')
def test_details(test_id):
    test_result = StudentTestSubmission.query.filter_by(test_id=test_id).first()
    if not test_result:
        return render_template('404.html'), 404
    return render_template('test_details.html', test=test_result)
