// Handle subject change and dynamically update topic options
document.getElementById('subject').addEventListener('change', function () {
    const topicSelect = document.getElementById('topic');
    topicSelect.innerHTML = '<option value="" disabled selected>Select a topic</option>';

    const selectedSubject = this.value;
    let topics = [];

    if (selectedSubject === 'Mathematics') {
        topics = ['Circles', 'Linear Equations', 'Probability'];
    } else if (selectedSubject === 'Physics') {
        topics = ['Optics', 'Thermodynamics', 'Electromagnetism'];
    } else if (selectedSubject === 'Chemistry') {
        topics = ['Chemical Reactions', 'Periodic Table', 'Organic Chemistry'];
    }

    topics.forEach(topic => {
        const option = document.createElement('option');
        option.value = topic;
        option.textContent = topic;
        topicSelect.appendChild(option);
    });
});

// Generate questions and display them
function getQuestion() {
    const subject = document.getElementById('subject').value;
    const topic = document.getElementById('topic').value;
    const level = document.getElementById('level').value;
    const numQuestions = parseInt(document.getElementById('num-questions').value, 10);

    if (!subject || !topic || !level || numQuestions < 1) {
        alert("Please fill all the fields correctly.");
        return;
    }

    fetch('/get_question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, topic, level, numQuestions })
    })
    .then(response => response.json())
    .then(data => {
        const questionsContainer = document.getElementById('questions-container');
        questionsContainer.innerHTML = ''; // Clear previous questions
        document.getElementById('question-section').style.display = 'block';

        if (data.error) {
            alert("Error: " + data.error);
            return;
        }

        if (data.questions.length === 0) {
            questionsContainer.innerHTML = '<p>No questions available for the selected criteria.</p>';
            return;
        }

        data.questions.forEach((q, index) => {
            // Create question block
            const questionDiv = document.createElement('div');
            questionDiv.classList.add('question-block');
            questionDiv.setAttribute('data-question-id', q.id);

            // Question text
            const questionText = document.createElement('p');
            questionText.innerText = `${index + 1}. ${q.question}`;
            questionDiv.appendChild(questionText);

            // Options
            const optionsContainer = document.createElement('div');
            optionsContainer.classList.add('options-container');

            q.options.forEach((option, optionIndex) => {
                const optionDiv = document.createElement('div');
                const input = document.createElement('input');
                input.type = 'radio';
                input.name = `question-${q.id}`;
                input.value = option;
                input.id = `question-${q.id}-option-${optionIndex}`;

                const label = document.createElement('label');
                label.htmlFor = input.id;
                label.textContent = option;

                optionDiv.appendChild(input);
                optionDiv.appendChild(label);
                optionsContainer.appendChild(optionDiv);
            });

            questionDiv.appendChild(optionsContainer);
            questionsContainer.appendChild(questionDiv);
        });
    })
    .catch(error => {
        console.error("Error generating questions:", error);
        alert("An error occurred while fetching questions. Please try again.");
    });
}

// Submit the test and handle results
function submitTest() {
    const answers = {};
    const questionBlocks = document.querySelectorAll('.question-block');

    // Collect answers with validation
    questionBlocks.forEach(block => {
        const questionId = block.getAttribute('data-question-id');
        const selectedOption = block.querySelector('input[type="radio"]:checked');

        // Ensure only valid question IDs and answers are collected
        if (questionId && questionId !== "null" && selectedOption) {
            answers[questionId] = selectedOption.value;
        }
    });

    fetch('/submit_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(`Error: ${data.error}`);
            return;
        }

        // Display only the score
        const resultsSection = document.getElementById('results-section');
        resultsSection.style.display = 'block';
        resultsSection.innerHTML = `
            <h3>RESULTS</h3>
            <p>You scored ${data.score} out of ${data.total_questions}</p>
            <div style="text-align: right; margin-top: 20px;">
                <button onclick="window.location.href='/dashboard'" style="background: #f0ad4e; color: white; border: none; padding: 10px; cursor: pointer;">
                    Go to Dashboard
                </button>
            </div>
        `;
    })
    .catch(error => {
        console.error("Error submitting test:", error);
        alert("An error occurred while submitting the test.");
    });
}

// Attach event listeners to buttons
document.getElementById('generate-button').addEventListener('click', getQuestion);
document.getElementById('submit-button').addEventListener('click', submitTest);
