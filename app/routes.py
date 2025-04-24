from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_principal import Identity, identity_changed, AnonymousIdentity
from werkzeug.security import generate_password_hash, check_password_hash
from app.forms import RegistrationForm, LoginForm
from sqlalchemy.orm import subqueryload
from app.models import db, User, Question, Test, Role, StudentTestSubmission, test_questions
import os
import openai
import json
import re

routes = Blueprint('routes', __name__, template_folder='templates')

def calculate_score(questions, responses):
    score = 0
    for question, response in zip(questions, responses):
        if response['answer'] == question.answer:
            score += 1  # Add points for correct answers
    return score


@routes.route('/')
def home():
    return redirect(url_for('routes.login'))

@routes.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role_name = 'Student'

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('routes.register'))

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            flash('Invalid role selected.')
            return redirect(url_for('routes.register'))

        # ✅ Generate Student ID only for Students
        student_id = None
        if role_name.lower() == "student":
            last_student = User.query.filter(User.student_id.isnot(None)).order_by(User.student_id.desc()).first()
            if last_student and last_student.student_id.startswith("S"):
                last_id_num = int(last_student.student_id[1:])  # Extract number (e.g., 'S001' -> 1)
                student_id = f"S{last_id_num + 1:03d}"  # Format as S002, S003, ...
            else:
                student_id = "S001"

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        new_user = User(username=username, password=hashed_password, role=role_name, student_id=student_id)
        db.session.add(new_user)
        db.session.commit()

        if role_name.lower() == "student":
            flash(f'Registration successful! Your Student ID is {student_id}. Please use this to log in.')
        else:
            flash('Admin registered successfully! You can now log in.')

        return redirect(url_for('routes.login'))
    
    return render_template('register.html', form=form)

@routes.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        role = form.role.data

        # ✅ Handle different login methods for Student vs. Admin
        if role.lower() == "student":
            identifier = form.student_id.data.strip()  # Students log in with Student ID
            user = User.query.filter_by(student_id=identifier, role=role).first()
        else:
            identifier = form.username.data.strip()  # Admins log in with Username
            user = User.query.filter_by(username=identifier, role=role).first()

        # 🔹 Debugging: Print login attempt details
        print(f"Login Attempt - Identifier: {identifier}, Role: {role}")

        if user:
            print(f"User found: {user.username if role.lower() == 'admin' else user.student_id}")

            if check_password_hash(user.password, form.password.data):
                login_user(user, remember=form.remember.data)
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))

                return redirect(url_for('routes.my_tests')) if role.lower() == 'student' else redirect(url_for('routes.admin'))
            else:
                print("Password mismatch!")
                flash('Invalid password.')
        else:
            print("User not found!")
            flash('Invalid credentials. Please check your ID/username and role.')

    return render_template('login.html', form=form)

@routes.route('/logout')
@login_required
def logout():
    logout_user()
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    flash('You have been logged out.')
    return redirect(url_for('routes.login'))

@routes.route('/admin')
@login_required
def admin():
     if current_user.role != "Admin":
        flash("Access Denied.")
        return redirect(url_for('routes.login'))
     else:
       students = User.query.filter_by(role="Student").all()
       return render_template('index.html',students=students)

client = openai.OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ.get("GITHUB_TOKEN"),
)



@routes.route('/get_students', methods=['GET'])
def get_students(): 
    students = User.query.filter_by(role='Student').all() 
    student_list = [{"id": s.student_id, "name": s.username} for s in students]
    return jsonify({"students": student_list})

@routes.route('/get_filtered_questions', methods=['GET'])
def get_filtered_questions():
    subject = request.args.get('subject')
    topic = request.args.get('topic')
    level = request.args.get('level')

    if not all([subject, topic, level]):
        return jsonify({"error": "Missing required fields"}), 400

    questions = Question.query.filter_by(subject=subject, topic=topic, level=level).all()

    question_list = [{
        "id": q.id,
        "question": q.question_text,
        "options": q.options,
        "correct_answer": q.answer,
        "solution": q.solution
    } for q in questions]

    return jsonify({"questions": question_list})



@routes.route('/generate_question', methods=['POST'])
def generate_question():
    data = request.get_json()
    print(data) 
    student_ids = data.get('studentIds', [])
    subject = data.get('subject')
    topic = data.get('topic')
    level = data.get('level')
    time_limit = data.get('timeLimit')
    selected_question_ids = data.get('questionIds', [])

    if not all([student_ids, subject, topic, level, time_limit]) or not isinstance(student_ids, list):
        return jsonify({"error": "Missing required fields"}), 400

    existing_questions = Question.query.filter(Question.id.in_(selected_question_ids)).all()

    if len(existing_questions) < len(selected_question_ids):
        remaining_count = len(selected_question_ids) - len(existing_questions)
        
        prompt = f"""
        Generate {remaining_count} {level}-level multiple-choice questions on {topic} in {subject}.
        Each question must have exactly 4 options (A, B, C, D), one correct answer, and a detailed solution.
        Return a strict JSON array:
        [
            {{
                "question": "...",
                "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
                "correct_answer": "...",
                "solution": "..."
            }}
        ]
        """

        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an AI tutor generating structured questions."},
                    {"role": "user", "content": prompt}
                ],
                model="gpt-4o-mini", temperature=1, max_tokens=1000, top_p=1
            )

            raw_response = response.choices[0].message.content.strip()
            raw_response = re.sub(r'```json|```', '', raw_response)
            ai_response = json.loads(raw_response)

            if not isinstance(ai_response, list):
                ai_response = [ai_response]

            new_questions = []
            for q in ai_response:
                if not all(k in q for k in ("question", "options", "correct_answer", "solution")):
                    continue
                new_q = Question(
                    subject=subject,
                    topic=topic,
                    level=level,
                    question_text=q["question"],
                    options=q.get("options", {}),
                    answer=q["correct_answer"],
                    solution=q["solution"]
                )
                db.session.add(new_q)
                new_questions.append(new_q)

            db.session.commit()
            existing_questions.extend(new_questions)

        except json.JSONDecodeError as e:
            return jsonify({"error": f"JSON parse error from OpenAI: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"error": f"OpenAI error: {str(e)}"}), 500

    # Create tests for each student
    with db.session.no_autoflush:
        last_test = Test.query.order_by(Test.test_id.desc()).first()
        new_test_id = last_test.test_id + 1 if last_test else 1
        test_ids = []

        for student_id in student_ids:
            new_test = Test(
                test_id=new_test_id,
                student_id=student_id,
                subject=subject,
                topic=topic,
                status="Pending",
                questions=existing_questions,
                duration_minutes=time_limit
            )
            db.session.add(new_test)
            test_ids.append(new_test_id)
            new_test_id += 1

        db.session.commit()

    return jsonify({
        "message": f"Test assigned to {len(student_ids)} student(s)",
        "test_ids": test_ids
    }), 201

@routes.route('/fetch_questions', methods=['POST'])
def fetch_questions():
    subject = request.form.get('subject')
    topic = request.form.get('topic')
    level = request.form.get('level')

    if not all([subject, topic, level]):
        return jsonify({"error": "Missing parameters"}), 400

    questions = Question.query.filter_by(subject=subject, topic=topic, level=level).all()

    return jsonify([
        {
            "id": q.id,
            "question": q.question_text,
            "options": q.options,
            "answer": q.answer,
            "solution": q.solution
        }
        for q in questions
    ])

@routes.route('/my_tests')
@login_required
def my_tests():
    # Check if the user has the "Student" role
    if current_user.role != "Student":
        flash("Access Denied.")
        return redirect(url_for('routes.login'))

    # Get the student's tests
    student_tests_pending = Test.query.options(subqueryload(Test.questions))\
        .filter_by(student_id=current_user.student_id, status="Pending")\
        .order_by(Test.test_id.desc()).all()
    
    student_tests_completed = Test.query.options(subqueryload(Test.questions))\
        .filter_by(student_id=current_user.student_id, status="completed")\
        .order_by(Test.test_id.desc()).all()

    # Pass the tests as separate lists for pending and completed
    return render_template('my_tests.html', 
                           pending_tests=student_tests_pending, completed_tests=student_tests_completed)

@routes.route('/start_test/<int:test_id>', methods=['GET'])
@login_required
def start_test(test_id):
    test = Test.query.filter_by(test_id=test_id, student_id=current_user.student_id).first()

    if not test:
        flash("Test not found or access denied.")
        return redirect(url_for('routes.my_tests'))

    if not test.questions:
        flash("No questions found for this test.")
        return redirect(url_for('routes.my_tests'))

    return render_template('test_page.html', test=test)

@routes.route('/submit_test/<int:test_id>', methods=['POST'])
@login_required
def submit_test(test_id):
    test = Test.query.filter_by(test_id=test_id, student_id=current_user.student_id).first()

    if not test:
        return jsonify({"success": False, "message": "Test not found or access denied."})

    if not test.questions:
        return jsonify({"success": False, "message": "No questions found for this test."})

    # Get the student responses from the form
    responses = request.json.get('responses')

    # Calculate the score
    score = calculate_score(test.questions, responses)

    # Update the test status
    test.status = 'completed'
    db.session.commit()

    # Store the test submission
    submission = StudentTestSubmission(
        student_id=current_user.student_id,
        test_id=test.test_id,
        responses=responses,
        score=score,
        total_questions=len(test.questions)
    )
    db.session.add(submission)

    db.session.commit()

    return jsonify({"success": True, "message": "Test submitted successfully!"})


@routes.route('/view_analysis/<int:test_id>', methods=['GET'])
@login_required
def view_analysis(test_id):
    # Fetch submission for the test and student
    submission = StudentTestSubmission.query.filter_by(test_id=test_id, student_id=current_user.student_id).first()

    if not submission:
        flash("Test submission not found.")
        return redirect(url_for('routes.my_tests'))

    # Get the question IDs from the student's responses
    responses = submission.responses
    question_ids = [int(response['question_id']) for response in responses]  # Convert question_ids to integers

    # Fetch all corresponding questions from the Question table using question_ids
    questions = Question.query.filter(Question.id.in_(question_ids)).all()

    # Create a dictionary of questions with question_id as key and tuple (question_text, correct_answer, solution)
    question_dict = {
        q.id: {
            'question_text': q.question_text,
            'correct_answer': q.answer,
            'solution': q.solution,
            'options':  q.options if isinstance(q.options, dict) else json.loads(q.options)
        } for q in questions
    }

    # Debugging: Print out the question_dict to check its contents
    print(question_dict)
    print("Submission Details:")
    print(f"Student ID: {submission.student_id}")
    print(f"Test ID: {submission.test_id}")
    print(f"Responses: {submission.responses}")
    print(f"Question Dict: {question_dict}")

    return render_template('test_analysis.html', submission=submission, responses=responses, question_dict=question_dict)
