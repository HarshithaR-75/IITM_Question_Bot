from flask import Blueprint, render_template, request, jsonify
from app.models import db, Question, TestResult

routes = Blueprint('routes', __name__)

@routes.route('/')
def index():
    return render_template('index.html')

@routes.route('/dashboard')
def dashboard():
    # Fetch all test results from the database
    all_tests = TestResult.query.order_by(TestResult.date.desc()).all()  # Order by latest test first
    return render_template('dashboard.html', tests=all_tests)



@routes.route('/generate_question', methods=['POST'])
def generate_question():
    try:
        data = request.get_json()
        print("Received Data:", data)  # Debugging statement

        subject = data.get('subject')
        topic = data.get('topic')
        level = data.get('level')
        num_questions = int(data.get('numQuestions', 1))

        print(f"Filtering Questions for Subject: {subject}, Topic: {topic}, Level: {level}")

        # Fetch questions from the database
        questions = Question.query.filter_by(subject=subject, topic=topic, level=level).limit(num_questions).all()
        print("Fetched Questions:", questions)  # Debugging

        if not questions:
            return jsonify({"error": f"No questions available for {level} level"}), 404

        questions_list = [{"id": q.id, "question": q.question_text, "options": q.options} for q in questions]

        return jsonify({"questions": questions_list})

    except Exception as e:
        print("Error in /generate_question:", e)  # Debugging
        return jsonify({"error": str(e)}), 500


@routes.route('/submit_test', methods=['POST'])
def submit_test():
    try:
        data = request.get_json()
        print("Received Data:", data)  # Debugging

        submitted_answers = data.get('answers')
        print("Submitted Answers:", submitted_answers)  # Debugging

        if not submitted_answers:
            return jsonify({"error": "No answers submitted"}), 400

        # Fetch correct answers from the database
        # Filter out invalid or non-integer question IDs
        question_ids = [int(qid) for qid in submitted_answers.keys() if qid.isdigit()]
        if not question_ids:
         return jsonify({"error": "No valid question IDs provided"}), 400

        print("Question IDs:", question_ids)  # Debugging

        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        print("Fetched Questions:", questions)  # Debugging

        score = 0
        total_questions = len(questions)
        results = []

        for question in questions:
            question_id = str(question.id)
            correct_answer = question.answer
            user_answer = submitted_answers.get(question_id)

            is_correct = user_answer == correct_answer
            if is_correct:
                score += 1

            results.append({
                "question": question.question_text,
                "user_answer": user_answer or "Not Answered",
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "solution": question.solution
            })

        print("Final Results:", results)  # Debugging
        print("Score:", score, "Total Questions:", total_questions)  # Debugging

        # Save test results in the database
        test_result = TestResult(score=score, total_questions=total_questions, results=results)
        db.session.add(test_result)
        db.session.commit()

        return jsonify({
            "message": "Test submitted successfully",
            "score": score,
            "total_questions": total_questions,
            "results": results
        })

    except Exception as e:
        print("Error in /submit_test:", e)  # Debugging
        return jsonify({"error": str(e)}), 500
    
@routes.route('/test_details/<int:test_id>')
def test_details(test_id):
    # Fetch the test result by its ID
    test_result = TestResult.query.get(test_id)

    # If no test is found, return a 404 error
    if not test_result:
        return render_template('404.html'), 404

    # Render the test analysis page
    return render_template('test_details.html', test=test_result)

