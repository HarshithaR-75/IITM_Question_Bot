import os
import json
from openai import OpenAI
from app.models import Question
from app import db

# OpenAI Azure Configuration
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ.get("GITHUB_TOKEN")  # Ensure you have set the GITHUB_TOKEN in your environment
)

# Fetch Question from DB
def get_question_from_db(subject, topic, level):
    print("get_question function called!")
    return Question.query.filter_by(subject=subject, topic=topic, level=level).first()

# Store Question in DB
def store_question_in_db(subject, topic, level, question_text, options, answer, solution):
    new_question = Question(
        subject=subject,
        topic=topic,
        level=level,
        question_text=question_text,
        options=json.dumps(options),  # Ensure options are stored as JSON
        answer=answer,
        solution=solution
    )
    db.session.add(new_question)
    db.session.commit()

# Call OpenAI via Azure
def get_question_from_chatgpt(subject, topic, level):
    prompt = f"""Generate a multiple-choice question for {subject},
    topic: {topic}, difficulty: {level}. Include 4 options, the correct answer, and a short solution.
    Respond in JSON format with keys: question, options, answer, solution."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=4096,
            top_p=1
        )

        response_text = response.choices[0].message.content.strip()
        data = json.loads(response_text)

        return data["question"], data["options"], data["answer"], data.get("solution", "")
    except Exception as e:
        return None, None, None, f"Error: {str(e)}"

# Main Function to Fetch or Generate Question
def get_question(subject, topic, level):
    question = get_question_from_db(subject, topic, level)
    
    if question:
        return question.question_text, json.loads(question.options), question.answer, question.solution

    # If not in DB, fetch from ChatGPT and store
    question_text, options, answer, solution = get_question_from_chatgpt(subject, topic, level)
    if question_text:
        store_question_in_db(subject, topic, level, question_text, options, answer, solution)

    return question_text, options, answer, solution