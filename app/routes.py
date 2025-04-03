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
        role_name = request.form.get('role')

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
       return render_template('index.html')

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
        new_test = Test(test_id=new_test_id, student_id=student_id, subject=subject, topic=topic, status="Pending", questions=[])
        db.session.add(new_test)
        db.session.commit()

    # Fetch existing questions
    questions = Question.query.filter_by(subject=subject, topic=topic, level=level).limit(num_questions).all()
    question_list = [
        {"id": q.id, "question": q.question_text, "options": q.options, "correct_answer": q.answer,  "solution": q.solution}
        for q in questions
    ]

    # If not enough questions exist, generate new ones using OpenAI
    if len(questions) < num_questions:
        remaining_questions = num_questions - len(questions)

        prompt = f"""
        Generate {remaining_questions} {level}-level multiple-choice questions on {topic} in {subject}.
        Each question must have exactly 4 options (A, B, C, D) and one correct answer and a detailed solution.
        Format the response strictly as a JSON array:
        [
          {{
            "question": "...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
            "correct_answer": "..."
            "solution":"...."
          }}
        ]
        """

        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an AI tutor helping generate structured questions."},
                    {"role": "user", "content": prompt}
                ],
                model="gpt-4o-mini", temperature=1, max_tokens=1000, top_p=1
            )

            raw_response = response.choices[0].message.content.strip()
            print("Raw AI Response:", raw_response)  # Debugging step

            if not raw_response:
                return jsonify({"error": "Empty response from OpenAI"}), 500

            # Remove Markdown JSON formatting if present
            raw_response = re.sub(r'```json|```', '', raw_response)

            # Parse the JSON response
            ai_response = json.loads(raw_response)

            if not isinstance(ai_response, list):
                ai_response = [ai_response]

            new_questions = []
            for q in ai_response:
                if not all(k in q for k in ("question", "options", "correct_answer", "solution")):
                    continue  # Skip invalid entries

                new_question = Question(
                    subject=subject, topic=topic, level=level, question_text=q["question"],
                    options=q.get("options", {}), answer=q["correct_answer"],
                    solution=q["solution"]
                )
                new_questions.append(new_question)

                question_list.append({
                    "id": None,  # ID will be assigned after commit
                    "question": new_question.question_text,
                    "options": new_question.options,
                    "correct_answer": new_question.answer,
                    "solution": new_question.solution
                })

            if new_questions:
                db.session.add_all(new_questions)
                db.session.commit()

                # Update with actual IDs
                for i, q in enumerate(new_questions):
                    question_list[len(questions) + i]["id"] = q.id

        except json.JSONDecodeError as e:
            return jsonify({"error": f"Error parsing AI response: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

    # Update test entry with generated questions
    question_objs = Question.query.filter(Question.id.in_([q["id"] for q in question_list if q["id"] is not None])).all()
    new_test.questions.extend(question_objs)
    db.session.commit()

    return jsonify({"test_id": new_test_id, "questions": question_list}), 201

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
