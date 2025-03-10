from flask import Blueprint, render_template, request, jsonify
from app.models import db, Question, TestResult
import os
import openai
import json
import re

routes = Blueprint('routes', __name__)

@routes.route('/')
def index():
    return render_template('index.html')

@routes.route('/dashboard')
def dashboard():
    # Fetch all test results from the database
    all_tests = TestResult.query.order_by(TestResult.date.desc()).all()
    return render_template('dashboard.html', tests=all_tests)

client = openai.OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ.get("GITHUB_TOKEN"),
)

@routes.route('/generate_question', methods=['POST'])
def generate_question():
    data = request.get_json()
    print("Received Data:", data)

    subject = data.get('subject')
    topic = data.get('topic')
    level = data.get('level')
    num_questions = int(data.get('numQuestions', 1))

    print(f"Filtering Questions for Subject: {subject}, Topic: {topic}, Level: {level}")

    # Fetch questions from the database
    questions = Question.query.filter_by(subject=subject, topic=topic, level=level).limit(num_questions).all()
    
    if questions:
        question_list = [
            {
                "id": q.id,
                "question": q.question_text,
                "options": list(q.options.values()) if isinstance(q.options, dict) else list(json.loads(q.options).values()),
                "correct_answer": q.answer,
                "detailed_solution": q.solution
            }
            for q in questions
        ]
        return jsonify(question_list), 200

    print("No questions found, generating using OpenAI...")
    prompt = (
        f"Generate {num_questions} {level}-level questions on {topic} in {subject} "
        f"with 4 options (A, B, C, D), an answer, and a detailed solution. "
        f"The response should be in JSON format as follows: \n"
        f"[{{\"question\": \"<question_text>\", \"options\": {{\"A\": \"<option_A>\", \"B\": \"<option_B>\", \"C\": \"<option_C>\", \"D\": \"<option_D>\"}}, "
        f"\"correct_answer\": \"<correct_option_letter>\", \"detailed_solution\": \"<solution_text>\"}}]"
    )

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an AI tutor helping generate questions."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-4o-mini",
        temperature=1,
        max_tokens=2500,
        top_p=1
    )

    generated_text = response.choices[0].message.content.strip()
    print("Generated Text:", generated_text)

    try:
        # Clean and parse the generated text
        generated_text = re.sub(r'```json|```', '', generated_text).strip()
        ai_response = json.loads(generated_text)

        # Ensure AI response is a **list**, not a single dictionary
        if not isinstance(ai_response, list):
            ai_response = [ai_response]

        new_questions = []
        for q in ai_response:
            question_text = q.get("question", "No question provided")
            options_dict = q.get("options", {})
            correct_answer = q.get("correct_answer", "No answer provided")
            detailed_solution = q.get("detailed_solution", "No solution provided")

            new_question = Question(
                subject=subject,
                topic=topic,
                level=level,
                question_text=question_text,
                options=options_dict,  # Store as JSON
                answer=correct_answer,
                solution=detailed_solution
            )
            db.session.add(new_question)
            db.session.commit()
            new_questions.append({
                "id": new_question.id,
                "question": new_question.question_text,
                "options": list(new_question.options.values()),
                "answer": new_question.answer
            })

        db.session.commit()
        return jsonify(new_questions), 200

    except json.JSONDecodeError as e:
        print("JSON parsing error:", e)
        return jsonify({"error": "Failed to parse AI response as JSON"}), 500
    except KeyError as e:
        print("KeyError:", e)
        return jsonify({"error": f"Missing key in AI response: {e}"}), 500
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


@routes.route('/submit_test', methods=['POST'])
def submit_test():
    try:
        data = request.get_json()
        print("Received Data:", data)

        submitted_answers = data.get('answers')
        print("Submitted Answers:", submitted_answers)

        if not isinstance(submitted_answers, dict):
            return jsonify({"error": "Invalid answer format. Expected a dictionary."}), 400

        # Ensure all question IDs are valid integers
        question_ids = [int(qid) for qid in submitted_answers.keys() if qid.isdigit()]
        if not question_ids:
            return jsonify({"error": "No valid question IDs provided"}), 400

        print("Question IDs:", question_ids)

        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        print("Fetched Questions:", questions)

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

        print("Final Results:", results)
        print("Score:", score, "Total Questions:", total_questions)

        # Save test results in the database
        test_result = TestResult(score=score, total_questions=total_questions, results=json.dumps(results))  # Store as JSON string
        db.session.add(test_result)
        db.session.commit()

        return jsonify({
            "message": "Test submitted successfully",
            "score": score,
            "total_questions": total_questions,
            "results": results
        })

    except Exception as e:
        print("Error in /submit_test:", e)
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
